import mimetypes
import os
from functools import wraps

from django.http import FileResponse
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Accession, FileRelation
from files.parsers.archive import parse_feature_file as _parse_feature_file
from files.parsers.codon import load_payload as _load_codon_payload
from files.parsers.fasta import (
    build_sequence_aliases as _build_fasta_sequence_aliases,
    list_sequence_ids,
    sequence_length,
)
from files.services.accession_context import (
    AmbiguousContextError,
    classify_file_scope,
    get_context_genome_file,
    get_context_organism,
    resolve_preferred_annotation,
    resolve_preferred_assembly,
)
from files.services.file_relation_service import (
    get_files_for_accession,
    get_files_for_annotation,
    get_files_for_assembly,
)
from files.services.query_view_helpers import (
    adapt_annotation_file as _adapt_annotation_file_service_result,
    adapt_overview_file as _adapt_overview_file_service_result,
    has_path_traversal as _has_path_traversal,
)
from files.services.query_service import (
    get_data_overview_files_payload,
    get_data_overview_payload,
    get_genome_files_payload,
    get_genome_list_payload,
    get_raw_data_payload,
    get_transcriptome_files_payload,
    get_transcriptome_list_payload,
)
TRANSCRIPTOME_SUFFIXES = ("all", "leaf", "panicles", "shoot", "stem", "root")


def reject_ambiguous_context(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except AmbiguousContextError as exc:
            return Response(
                {
                    "error": str(exc),
                    "code": exc.code,
                    "related_type": exc.related_type,
                    "parent": exc.parent_code,
                },
                status=status.HTTP_409_CONFLICT,
            )

    return wrapped


def _request_params(request):
    return getattr(request, "query_params", request.GET)


def _get_page_params(params, default_page_size=20):
    page = int(params.get("page", 1))
    page_size = int(params.get("page_size", default_page_size))
    return max(page, 1), max(page_size, 1)


def _normalize_sub_population(value):
    return value.strip() if value and value.strip() else "Unknown"


def _build_download_url(file_id):
    if not file_id:
        return None
    return f"/gd/api/files/data-files/{file_id}/download/"


def _paginate_rows(rows, page, page_size):
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "count": total,
        "next": f"?page={page + 1}&page_size={page_size}" if end < total else None,
        "previous": f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        "results": rows[start:end],
    }


def _existing_service_file(service_files):
    for service_file in service_files:
        file_path = service_file.get("file_path")
        if file_path and os.path.exists(file_path):
            return service_file
    return None


def _resolve_service_file(request, file_role):
    params = _request_params(request)
    organism, accession_obj, assembly, annotation = get_context_organism(
        annotation_id=params.get("annotation_id"),
        assembly_id=params.get("assembly_id"),
        accession=params.get("accession"),
        organism=params.get("organism"),
    )

    service_files = []
    scope = classify_file_scope(file_role)
    if scope == "annotation":
        if annotation:
            service_files = get_files_for_annotation(annotation.id, file_role=file_role)
    elif assembly:
        service_files = get_files_for_assembly(assembly.id, file_role=file_role)
        if not service_files and scope == "compatibility_assembly" and accession_obj:
            service_files = get_files_for_accession(accession_obj.id, file_role=file_role)
    elif accession_obj:
        service_files = get_files_for_accession(accession_obj.id, file_role=file_role)

    return organism, accession_obj, assembly, annotation, _existing_service_file(service_files)


def _build_context_chromosome_aliases(accession_obj=None, assembly=None, organism=None):
    """Build aliases from the exact genome file selected for this request context."""
    accession = accession_obj.accession if accession_obj else organism
    _, _, genome_file = get_context_genome_file(
        assembly_id=assembly.id if assembly else None,
        accession=accession,
        organism=organism,
    )
    return _build_fasta_sequence_aliases(genome_file.file_path) if genome_file else {}


def _transcriptome_service_file(accession_obj, transcriptome_type):
    file_role = f"transcriptome.{transcriptome_type}"
    service_files = get_files_for_accession(accession_obj.id, file_role=file_role)
    if service_files:
        return _existing_service_file(service_files)

    assembly = resolve_preferred_assembly(accession_obj)
    if assembly:
        return _existing_service_file(get_files_for_assembly(assembly.id, file_role=file_role))
    return None


def _interval_response_for_role(request, file_role):
    params = _request_params(request)
    chromosome = params.get("chromosome")
    feature_type = params.get("feature_type")
    organism, accession_obj, assembly, _, service_file = _resolve_service_file(request, file_role)
    if not organism:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)
    if not service_file:
        return Response({"error": f"未找到 {organism} 的 {file_role} 文件"}, status=status.HTTP_404_NOT_FOUND)
    chromosome_aliases = _build_context_chromosome_aliases(
        accession_obj=accession_obj,
        assembly=assembly,
        organism=organism,
    )
    rows = _parse_feature_file(
        service_file["file_path"],
        chromosome=chromosome,
        feature_type=feature_type,
        chromosome_aliases=chromosome_aliases,
    )
    return Response(rows)


@api_view(["GET"])
@permission_classes([AllowAny])
def query_organisms(request):
    params = _request_params(request)
    search = (params.get("search") or "").strip()
    queryset = Accession.objects.all().order_by("accession")
    if search:
        queryset = queryset.filter(accession__icontains=search)
    return Response(list(queryset.values_list("accession", flat=True)))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_annotation_organisms(request):
    annotation_ids = (
        FileRelation.objects.filter(related_type="annotation", file_role="annotation")
        .values_list("related_id", flat=True)
    )
    accessions = (
        Accession.objects.filter(assemblies__annotations__id__in=annotation_ids)
        .distinct()
        .order_by("accession")
        .values_list("accession", flat=True)
    )
    return Response(list(accessions))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_sub_populations(request):
    values = set()
    has_unknown = False
    for sub_population in Accession.objects.values_list("sub_population", flat=True):
        if sub_population and sub_population.strip():
            values.add(sub_population.strip())
        else:
            has_unknown = True
    result = sorted(values)
    if has_unknown:
        result.append("Unknown")
    return Response(result)


@api_view(["GET"])
@permission_classes([AllowAny])
def query_supplementary_data(request):
    payload = {}
    for accession in Accession.objects.all().order_by("accession"):
        payload[accession.accession] = {
            "sub_population": accession.sub_population,
            "seq_data": accession.seq_data,
            "country": accession.country,
            "region": accession.region,
            "longitude": accession.longitude,
            "latitude": accession.latitude,
        }
    return Response(payload)


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_paginated_overview(request):
    params = _request_params(request)
    page, page_size = _get_page_params(params)
    search = (params.get("search") or "").strip()
    sub_populations = (params.get("sub_populations") or "").strip()

    accessions = Accession.objects.all().prefetch_related("assemblies__annotations").order_by("accession")
    if search:
        accessions = accessions.filter(
            Q(accession__icontains=search)
            | Q(species__species_code__icontains=search)
            | Q(species__scientific_name__icontains=search)
            | Q(species__chinese_name__icontains=search)
            | Q(species__common_name__icontains=search)
        ).distinct()

    rows = []
    for accession_obj in accessions:
        normalized_sub_population = _normalize_sub_population(accession_obj.sub_population)
        if sub_populations:
            if sub_populations == "NONE":
                continue
            selected = {item.strip() for item in sub_populations.split(",") if item.strip()}
            if normalized_sub_population not in selected:
                continue

        assemblies = list(accession_obj.assemblies.all())
        default_assembly = resolve_preferred_assembly(accession_obj)
        default_annotation = resolve_preferred_annotation(default_assembly)

        overview_files = [_adapt_overview_file_service_result(item) for item in get_files_for_accession(accession_obj.id)]
        assembly_files = [item for item in overview_files if item.get("category") != "annotation"]
        annotation_files = [item for item in overview_files if item.get("category") == "annotation"]

        def first_file(category, items):
            for item in items:
                if item.get("category") == category:
                    return item
            return None

        rows.append(
            {
                "accession": accession_obj.accession,
                "genome": first_file("genome", assembly_files),
                "annotation": first_file("annotation", annotation_files),
                "hasTranscriptome": any((item.get("category") or "").startswith("transcriptome.") for item in assembly_files),
                "codon": first_file("codon", assembly_files),
                "centromere": first_file("centromere", assembly_files),
                "TEs": first_file("TEs", assembly_files),
                "coreBlocks": first_file("coreBlocks", assembly_files),
                "miRNA": first_file("miRNA", assembly_files),
                "tRNA": first_file("tRNA", assembly_files),
                "rRNA": first_file("rRNA", assembly_files),
                "subPopulation": normalized_sub_population,
                "seqData": accession_obj.seq_data,
                "longitude": accession_obj.longitude,
                "latitude": accession_obj.latitude,
                "assembly_count": len(assemblies),
                "annotation_count": sum(len(list(assembly.annotations.all())) for assembly in assemblies),
                "default_assembly_id": default_assembly.id if default_assembly else None,
                "default_annotation_id": default_annotation.id if default_annotation else None,
            }
        )

    return Response(_paginate_rows(rows, page, page_size))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_data_overview(request):
    return Response(get_data_overview_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_data_overview_files(request):
    payload = get_data_overview_files_payload(_request_params(request))
    if payload is None:
        return Response({"error": "accession not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)


@api_view(["GET"])
@permission_classes([AllowAny])
def query_raw_data(request):
    return Response(get_raw_data_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_genome_list(request):
    return Response(get_genome_list_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_genome_files(request):
    return Response(get_genome_files_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_transcriptome_list(request):
    return Response(get_transcriptome_list_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_transcriptome_files(request):
    return Response(get_transcriptome_files_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_paginated_transcriptome_overview(request):
    params = _request_params(request)
    page, page_size = _get_page_params(params)
    search = (params.get("search") or "").strip()

    accessions = Accession.objects.all().order_by("accession")
    if search:
        accessions = accessions.filter(accession__icontains=search)

    rows = []
    for accession_obj in accessions:
        accession_files = get_files_for_accession(accession_obj.id)
        transcriptome_types = []
        transcriptome_downloads = {}
        for suffix in TRANSCRIPTOME_SUFFIXES:
            file_role = f"transcriptome.{suffix}"
            matched = next((item for item in accession_files if item.get("file_role") == file_role), None)
            if matched:
                transcriptome_types.append(suffix)
                transcriptome_downloads[suffix] = _build_download_url(matched.get("file_id"))
        rows.append(
            {
                "accession": accession_obj.accession,
                "transcriptomeTypes": transcriptome_types,
                "transcriptomeDownloads": transcriptome_downloads,
            }
        )

    return Response(_paginate_rows(rows, page, page_size))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_download_transcriptome(request):
    params = _request_params(request)
    accession_code = (params.get("accession") or params.get("organism") or "").strip()
    transcriptome_type = (params.get("type") or "").strip()
    if not accession_code or transcriptome_type not in TRANSCRIPTOME_SUFFIXES:
        return Response({"error": "缺少必要参数 accession/type"}, status=status.HTTP_400_BAD_REQUEST)

    accession_obj = Accession.objects.filter(accession=accession_code).first()
    if not accession_obj:
        return Response({"error": "未找到对应 accession"}, status=status.HTTP_404_NOT_FOUND)

    service_file = _transcriptome_service_file(accession_obj, transcriptome_type)
    if not service_file:
        return Response({"error": "未找到对应 transcriptome 文件"}, status=status.HTTP_404_NOT_FOUND)

    file_path = service_file.get("file_path")
    if not file_path or _has_path_traversal(file_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    normalized_path = os.path.abspath(os.path.normpath(file_path))
    if not os.path.isfile(normalized_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    content_type, _ = mimetypes.guess_type(normalized_path)
    if content_type is None:
        content_type = "application/octet-stream"
    response = FileResponse(open(normalized_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(service_file.get("file_name") or normalized_path)}"'
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_annotation_data(request):
    params = _request_params(request)
    organism, accession_obj, assembly, annotation = get_context_organism(
        annotation_id=params.get("annotation_id"),
        assembly_id=params.get("assembly_id"),
        accession=params.get("accession"),
        organism=params.get("organism"),
    )
    if not organism:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)

    page, page_size = _get_page_params(params, default_page_size=50)
    chromosome = params.get("chromosome")
    feature_type = params.get("feature_type", "all")

    service_file = _existing_service_file(get_files_for_annotation(annotation.id, file_role="annotation")) if annotation else None
    if not service_file:
        return Response({"error": f"未找到 {organism} 的注释文件"}, status=status.HTTP_404_NOT_FOUND)

    chromosome_aliases = _build_context_chromosome_aliases(
        accession_obj=accession_obj,
        assembly=assembly,
        organism=organism,
    )
    all_rows = _parse_feature_file(
        service_file["file_path"],
        chromosome=chromosome,
        feature_type=None if feature_type == "all" else feature_type,
        chromosome_aliases=chromosome_aliases,
    )
    chromosomes = sorted({row["seqid"] for row in all_rows})
    feature_types = sorted({row["feature"] for row in all_rows if row.get("feature")})
    return Response(
        {
            "results": all_rows[(page - 1) * page_size: page * page_size],
            "count": len(all_rows),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(all_rows) + page_size - 1) // page_size,
            "annotation_file": _adapt_annotation_file_service_result(service_file),
            "statistics": {
                "chromosomes": chromosomes,
                "feature_types": feature_types,
                "total_features": len(all_rows),
            },
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_chromosomes(request):
    params = _request_params(request)
    organism = params.get("organism")
    accession = params.get("accession")
    assembly_id = params.get("assembly_id")
    if not organism and not accession and not assembly_id:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)

    _, _, genome_file = get_context_genome_file(
        assembly_id=assembly_id,
        accession=accession,
        organism=organism,
    )
    if not genome_file:
        return Response({"error": f"未找到 {organism or accession or assembly_id} 的基因组文件"}, status=status.HTTP_404_NOT_FOUND)

    return Response(list_sequence_ids(genome_file.file_path))


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_chromosome_length(request):
    params = _request_params(request)
    organism = params.get("organism")
    accession = params.get("accession")
    assembly_id = params.get("assembly_id")
    chromosome = params.get("chromosome")
    if not organism and not accession and not assembly_id:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)
    if not chromosome:
        return Response({"error": "缺少必要的参数: chromosome"}, status=status.HTTP_400_BAD_REQUEST)

    _, _, genome_file = get_context_genome_file(
        assembly_id=assembly_id,
        accession=accession,
        organism=organism,
    )
    if not genome_file:
        return Response({"error": f"未找到 {organism or accession or assembly_id} 的基因组文件"}, status=status.HTTP_404_NOT_FOUND)

    length = sequence_length(genome_file.file_path, chromosome)
    if length is not None:
        return Response({"length": length})
    return Response({"error": f"在基因组文件中未找到染色体 {chromosome}"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_tes(request):
    return _interval_response_for_role(request, "TEs")


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_centromere(request):
    return _interval_response_for_role(request, "centromere")


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_coreblocks(request):
    return _interval_response_for_role(request, "coreBlocks")


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_variableblocks(request):
    return _interval_response_for_role(request, "variableBlocks")


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_rna_data(request):
    params = _request_params(request)
    rna_type = params.get("type")
    if rna_type not in {"rRNA", "miRNA", "tRNA"}:
        return Response({"error": "缺少必要的参数: type"}, status=status.HTTP_400_BAD_REQUEST)
    return _interval_response_for_role(request, rna_type)


@api_view(["GET"])
@permission_classes([AllowAny])
@reject_ambiguous_context
def query_codon_data(request):
    organism, _, _, _, service_file = _resolve_service_file(request, "codon")
    if not organism:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)
    if not service_file:
        return Response({"error": f"未找到 {organism} 的 codon 文件"}, status=status.HTTP_404_NOT_FOUND)
    payload = _load_codon_payload(service_file["file_path"], organism)
    if not payload:
        return Response({"error": f"无法解析 {organism} 的 codon 文件"}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)
