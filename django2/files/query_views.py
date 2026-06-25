import gzip
import mimetypes
import os
import tarfile
from io import TextIOWrapper

from django.http import FileResponse
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation
from files.services.accession_context import classify_file_scope, get_context_genome_file, get_context_organism
from files.services.file_relation_service import (
    get_files_for_accession,
    get_files_for_annotation,
    get_files_for_assembly,
)
from files.services.data_overview_service import (
    build_data_overview_files_payload,
    build_data_overview_payload,
)
from files.views import _adapt_annotation_file_service_result, _adapt_overview_file_service_result, _has_path_traversal


TRANSCRIPTOME_SUFFIXES = ("all", "leaf", "panicles", "shoot", "stem", "root")


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
    if scope == "annotation" and annotation:
        service_files = get_files_for_annotation(annotation.id, file_role=file_role)
    else:
        if assembly:
            service_files = get_files_for_assembly(assembly.id, file_role=file_role)
        if not service_files and accession_obj:
            service_files = get_files_for_accession(accession_obj.id, file_role=file_role)

    return organism, accession_obj, assembly, annotation, _existing_service_file(service_files)


def _open_text_handle(file_path):
    if file_path.endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf-8")
    return open(file_path, "r", encoding="utf-8")


def _parse_attributes(raw_attributes):
    attributes = {}
    for item in (raw_attributes or "").split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
            attributes[key.strip()] = value.strip()
        elif " " in item:
            key, value = item.split(" ", 1)
            attributes[key.strip()] = value.strip().strip('"')
    return attributes


def _parse_gff_lines(lines, chromosome=None, feature_type=None):
    results = []
    for line_number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        seqid = parts[0]
        feature = parts[2]
        if chromosome and seqid != chromosome:
            continue
        if feature_type and feature != feature_type:
            continue
        start = int(parts[3])
        end = int(parts[4])
        results.append(
            {
                "seqid": seqid,
                "source": parts[1],
                "feature": feature,
                "start": start,
                "end": end,
                "length": end - start + 1,
                "score": None if parts[5] == "." else parts[5],
                "strand": parts[6],
                "phase": None if parts[7] == "." else parts[7],
                "attributes": _parse_attributes(parts[8]),
                "line_number": line_number,
                "sequence_ontology": feature,
                "name": _parse_attributes(parts[8]).get("Name") or _parse_attributes(parts[8]).get("ID"),
            }
        )
    return results


def _parse_bed_lines(lines, chromosome=None):
    results = []
    for index, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        seqid = parts[0]
        if chromosome and seqid != chromosome:
            continue
        start = int(parts[1])
        end = int(parts[2])
        name = parts[3] if len(parts) > 3 else None
        score = parts[4] if len(parts) > 4 else None
        strand = parts[5] if len(parts) > 5 else None
        results.append(
            {
                "id": f"{seqid}:{start}-{end}:{index}",
                "seqid": seqid,
                "start": start,
                "end": end,
                "length": max(end - start, 0),
                "name": name,
                "score": score,
                "strand": strand,
                "phase": None,
                "attributes": {},
            }
        )
    return results


def _parse_feature_file(file_path, chromosome=None, feature_type=None):
    lower_path = file_path.lower()
    if lower_path.endswith((".gff", ".gff3", ".gff.gz", ".gff3.gz")):
        with _open_text_handle(file_path) as handle:
            return _parse_gff_lines(handle, chromosome=chromosome, feature_type=feature_type)

    if lower_path.endswith((".bed", ".bed.gz", ".txt", ".tsv")):
        with _open_text_handle(file_path) as handle:
            return _parse_bed_lines(handle, chromosome=chromosome)

    if lower_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(file_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                member_name = member.name.lower()
                if member_name.endswith((".gff", ".gff3")):
                    extracted = archive.extractfile(member)
                    if not extracted:
                        continue
                    return _parse_gff_lines(
                        TextIOWrapper(extracted, encoding="utf-8"),
                        chromosome=chromosome,
                        feature_type=feature_type,
                    )
                if member_name.endswith((".bed", ".txt", ".tsv")):
                    extracted = archive.extractfile(member)
                    if not extracted:
                        continue
                    return _parse_bed_lines(
                        TextIOWrapper(extracted, encoding="utf-8"),
                        chromosome=chromosome,
                    )
    return []


def _format_codon_usage_data(codon_usage):
    codon_to_amino_acid = {
        "GCU": "Ala", "GCC": "Ala", "GCA": "Ala", "GCG": "Ala",
        "CGU": "Arg", "CGC": "Arg", "CGA": "Arg", "CGG": "Arg", "AGA": "Arg", "AGG": "Arg",
        "AAU": "Asn", "AAC": "Asn",
        "GAU": "Asp", "GAC": "Asp",
        "UGU": "Cys", "UGC": "Cys",
        "GAA": "Glu", "GAG": "Glu",
        "CAA": "Gln", "CAG": "Gln",
        "GGU": "Gly", "GGC": "Gly", "GGA": "Gly", "GGG": "Gly",
        "CAU": "His", "CAC": "His",
        "AUU": "Ile", "AUC": "Ile", "AUA": "Ile",
        "UUA": "Leu", "UUG": "Leu", "CUU": "Leu", "CUC": "Leu", "CUA": "Leu", "CUG": "Leu",
        "AAA": "Lys", "AAG": "Lys",
        "AUG": "Met",
        "UUU": "Phe", "UUC": "Phe",
        "CCU": "Pro", "CCC": "Pro", "CCA": "Pro", "CCG": "Pro",
        "UCU": "Ser", "UCC": "Ser", "UCA": "Ser", "UCG": "Ser", "AGU": "Ser", "AGC": "Ser",
        "ACU": "Thr", "ACC": "Thr", "ACA": "Thr", "ACG": "Thr",
        "UGG": "Trp",
        "UAU": "Tyr", "UAC": "Tyr",
        "GUU": "Val", "GUC": "Val", "GUA": "Val", "GUG": "Val",
        "UAA": "TER", "UAG": "TER", "UGA": "TER",
    }
    total_codons = sum(item["count"] for item in codon_usage.values())
    formatted = {}
    for codon, item in codon_usage.items():
        count = item["count"]
        formatted[codon] = {
            "amino_acid": codon_to_amino_acid.get(codon, "Unknown"),
            "codon": codon,
            "count": count,
            "frequency": item["rscu"],
            "global_frequency": count / total_codons if total_codons else 0,
            "relative_frequency": item["rscu"],
        }
    return formatted


def _group_by_amino_acid(codon_usage):
    amino_acids = {}
    for codon, data in codon_usage.items():
        name = data["amino_acid"]
        bucket = amino_acids.setdefault(name, {"name": name, "codons": [], "total_count": 0})
        bucket["codons"].append(data)
        bucket["total_count"] += data["count"]
    for bucket in amino_acids.values():
        total = bucket["total_count"]
        for codon in bucket["codons"]:
            codon["relative_frequency"] = codon["count"] / total if total else 0
    return amino_acids


def _calculate_nucleotide_composition(codon_usage):
    counts = {"A": 0, "T": 0, "G": 0, "C": 0}
    total = 0
    for codon, item in codon_usage.items():
        count = item["count"]
        dna_codon = codon.replace("U", "T")
        for nucleotide in dna_codon:
            if nucleotide in counts:
                counts[nucleotide] += count
                total += count
    if not total:
        return counts
    return {key: (value / total) * 100 for key, value in counts.items()}


def _parse_blk_content(content):
    import re

    matches = re.findall(r"([AUGC]{3})(\d+)\s+([\d.]+)", content)
    codon_usage = {}
    for codon, count_str, rscu_str in matches:
        codon_usage[codon] = {
            "count": int(count_str),
            "rscu": float(rscu_str),
        }
    return codon_usage


def _parse_codon_statistics_content(content):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    headers = lines[0].split("\t")
    values = lines[1].split("\t")
    if len(headers) != len(values):
        return None
    result = {}
    for index, header in enumerate(headers):
        value = values[index]
        try:
            result[header] = float(value) if "." in value else int(value)
        except ValueError:
            result[header] = value
    return result


def _load_codon_payload(file_path, organism_name):
    blk_content = None
    stats_content = None
    lower_path = file_path.lower()

    if lower_path.endswith(".blk"):
        with open(file_path, "r", encoding="utf-8") as handle:
            blk_content = handle.read()
    elif lower_path.endswith((".txt", ".out")):
        with open(file_path, "r", encoding="utf-8") as handle:
            stats_content = handle.read()
    elif lower_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(file_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if not extracted:
                    continue
                content = extracted.read().decode("utf-8", errors="ignore")
                member_name = member.name.lower()
                if blk_content is None and member_name.endswith(".blk"):
                    blk_content = content
                elif stats_content is None and member_name.endswith((".txt", ".out")):
                    stats_content = content

    if not blk_content:
        return None

    codon_usage = _parse_blk_content(blk_content)
    if not codon_usage:
        return None

    formatted = _format_codon_usage_data(codon_usage)
    payload = {
        "organism": organism_name,
        "codon_usage": formatted,
        "amino_acids": _group_by_amino_acid(formatted),
        "total_codons": sum(item["count"] for item in codon_usage.values()),
        "nucleotide_composition": _calculate_nucleotide_composition(codon_usage),
    }
    statistics = _parse_codon_statistics_content(stats_content) if stats_content else None
    if statistics:
        payload["statistics"] = statistics
    return payload


def _transcriptome_service_file(accession_obj, transcriptome_type):
    file_role = f"transcriptome.{transcriptome_type}"
    service_files = get_files_for_accession(accession_obj.id, file_role=file_role)
    if service_files:
        return _existing_service_file(service_files)

    assembly = accession_obj.default_assembly or accession_obj.assemblies.first()
    if assembly:
        return _existing_service_file(get_files_for_assembly(assembly.id, file_role=file_role))
    return None


def _interval_response_for_role(request, file_role):
    params = _request_params(request)
    chromosome = params.get("chromosome")
    feature_type = params.get("feature_type")
    organism, _, _, _, service_file = _resolve_service_file(request, file_role)
    if not organism:
        return Response({"error": "缺少必要的参数: organism"}, status=status.HTTP_400_BAD_REQUEST)
    if not service_file:
        return Response({"error": f"未找到 {organism} 的 {file_role} 文件"}, status=status.HTTP_404_NOT_FOUND)
    rows = _parse_feature_file(service_file["file_path"], chromosome=chromosome, feature_type=feature_type)
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
        default_assembly = next((assembly for assembly in assemblies if assembly.is_default), None) or (assemblies[0] if assemblies else None)
        default_annotations = list(default_assembly.annotations.all()) if default_assembly else []
        default_annotation = next((annotation for annotation in default_annotations if annotation.is_default), None) or (default_annotations[0] if default_annotations else None)

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
def query_data_overview(request):
    return Response(build_data_overview_payload(_request_params(request)))


@api_view(["GET"])
@permission_classes([AllowAny])
def query_data_overview_files(request):
    payload = build_data_overview_files_payload(_request_params(request))
    if payload is None:
        return Response({"error": "accession not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)


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
def query_annotation_data(request):
    params = _request_params(request)
    organism, _, _, annotation = get_context_organism(
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

    all_rows = _parse_feature_file(
        service_file["file_path"],
        chromosome=chromosome,
        feature_type=None if feature_type == "all" else feature_type,
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

    chromosomes = []
    with _open_text_handle(genome_file.file_path) as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(">"):
                chromosomes.append(line[1:].split()[0])
    return Response(chromosomes)


@api_view(["GET"])
@permission_classes([AllowAny])
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

    current_id = None
    current_length = 0
    with _open_text_handle(genome_file.file_path) as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(">"):
                if current_id == chromosome:
                    return Response({"length": current_length})
                current_id = line[1:].split()[0]
                current_length = 0
            elif current_id:
                current_length += len(line)
    if current_id == chromosome:
        return Response({"length": current_length})
    return Response({"error": f"在基因组文件中未找到染色体 {chromosome}"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def query_tes(request):
    return _interval_response_for_role(request, "TEs")


@api_view(["GET"])
@permission_classes([AllowAny])
def query_centromere(request):
    return _interval_response_for_role(request, "centromere")


@api_view(["GET"])
@permission_classes([AllowAny])
def query_coreblocks(request):
    return _interval_response_for_role(request, "coreBlocks")


@api_view(["GET"])
@permission_classes([AllowAny])
def query_variableblocks(request):
    return _interval_response_for_role(request, "variableBlocks")


@api_view(["GET"])
@permission_classes([AllowAny])
def query_rna_data(request):
    params = _request_params(request)
    rna_type = params.get("type")
    if rna_type not in {"rRNA", "miRNA", "tRNA"}:
        return Response({"error": "缺少必要的参数: type"}, status=status.HTTP_400_BAD_REQUEST)
    return _interval_response_for_role(request, rna_type)


@api_view(["GET"])
@permission_classes([AllowAny])
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
