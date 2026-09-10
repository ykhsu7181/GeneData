from django.db.models import Q

from files.models import Accession, Assembly, FileRelation, Sample, Species
from files.services.accession_context import resolve_preferred_assembly
from files.services.data_overview_service import datafile_download_url, file_role_display, format_size


TRANSCRIPTOME_SAMPLE_TYPES = ("all", "leaf", "root", "stem", "panicles", "shoot")
TRANSCRIPTOME_ROLE_TOKENS = (
    "transcriptome",
    "expression",
    "tpm",
    "fpkm",
    "counts",
    "deg",
    "enrichment",
    "rnaseq",
    "rna_seq",
    "rna-seq",
)
TRANSCRIPTOME_ROLE_DISPLAY = {
    "rnaseq_raw_r1": "RNA-seq 原始数据 R1",
    "rnaseq_raw_r2": "RNA-seq 原始数据 R2",
    "expression_matrix": "表达矩阵",
    "tpm_matrix": "TPM 矩阵",
    "fpkm_matrix": "FPKM 矩阵",
    "counts_matrix": "Counts 矩阵",
    "deg_result": "差异表达结果",
    "enrichment_result": "富集分析结果",
    "transcriptome.all": "全部转录组",
    "transcriptome.leaf": "叶片转录组",
    "transcriptome.root": "根转录组",
    "transcriptome.stem": "茎转录组",
    "transcriptome.panicles": "穗转录组",
    "transcriptome.shoot": "幼苗转录组",
}


def _param(params, key, default=""):
    value = params.get(key, default)
    return value.strip() if isinstance(value, str) else value


def _page_params(params):
    page = int(params.get("page", 1) or 1)
    page_size = int(params.get("page_size", 20) or 20)
    return max(page, 1), max(page_size, 1)


def _species_name(species):
    if not species:
        return "未归属物种"
    return species.chinese_name or species.common_name or species.scientific_name or species.species_code


def _latin_name(species):
    if not species:
        return "-"
    return species.scientific_name or species.common_name or species.species_code or "-"


def _assembly_name(assembly):
    if not assembly:
        return "-"
    return assembly.display_name or assembly.name or assembly.standard_id or "-"


def _role_display(file_role):
    normalized = (file_role or "").strip()
    lower = normalized.lower()
    return TRANSCRIPTOME_ROLE_DISPLAY.get(lower) or file_role_display(normalized)


def _file_type_display(data_file):
    file_type = data_file.file_type
    if not file_type:
        return "-"
    return file_type.name or file_type.format or file_type.extension or "-"


def _transcriptome_role_query():
    query = Q()
    for token in TRANSCRIPTOME_ROLE_TOKENS:
        query |= Q(file_role__icontains=token)
    return query


def _transcriptome_relations():
    return (
        FileRelation.objects.select_related("file", "file__file_type")
        .filter(_transcriptome_role_query())
        .order_by("file_id", "related_type", "id")
    )


def _parse_sample_type(file_role):
    value = (file_role or "").strip().lower()
    for sample_type in TRANSCRIPTOME_SAMPLE_TYPES:
        if value == sample_type or value.endswith(f".{sample_type}") or f"_{sample_type}" in value:
            return sample_type
    return ""


def _collect_relation_contexts(relations):
    sample_ids = {
        int(relation.related_id)
        for relation in relations
        if relation.related_type == "sample" and str(relation.related_id).isdigit()
    }
    assembly_ids = {
        int(relation.related_id)
        for relation in relations
        if relation.related_type == "assembly" and str(relation.related_id).isdigit()
    }
    accession_ids = {
        int(relation.related_id)
        for relation in relations
        if relation.related_type == "accession" and str(relation.related_id).isdigit()
    }
    samples = {
        sample.id: sample
        for sample in Sample.objects.select_related("species", "accession", "accession__species").filter(id__in=sample_ids)
    }
    assemblies = {
        assembly.id: assembly
        for assembly in Assembly.objects.select_related("accession", "accession__species").filter(id__in=assembly_ids)
    }
    accessions = {
        accession.id: accession
        for accession in Accession.objects.select_related("species").filter(id__in=accession_ids)
    }
    return samples, assemblies, accessions


def _resolve_context(file_relations, samples, assemblies, accessions):
    sample = None
    assembly = None
    accession = None
    sample_type = ""

    for relation in file_relations:
        if relation.related_type == "sample" and str(relation.related_id).isdigit():
            sample = samples.get(int(relation.related_id))
            if sample:
                accession = sample.accession or accession
                sample_type = sample.tissue or sample.data_type or sample_type
                break

    for relation in file_relations:
        if relation.related_type == "assembly" and str(relation.related_id).isdigit():
            assembly = assemblies.get(int(relation.related_id))
            if assembly:
                accession = assembly.accession or accession
                break

    for relation in file_relations:
        if relation.related_type == "accession" and str(relation.related_id).isdigit():
            accession = accessions.get(int(relation.related_id)) or accession
            break

    if accession and not assembly:
        assembly = resolve_preferred_assembly(accession)
    if assembly and not accession:
        accession = assembly.accession
    if not sample_type:
        for relation in file_relations:
            sample_type = _parse_sample_type(relation.file_role)
            if sample_type:
                break
    return sample, accession, assembly, sample_type or "-"


def _file_payload(relation):
    data_file = relation.file
    return {
        "file_id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "file_path": data_file.file_path,
        "file_role": relation.file_role,
        "file_role_display": _role_display(relation.file_role),
        "file_type": _file_type_display(data_file),
        "file_size": data_file.file_size,
        "file_size_display": format_size(data_file.file_size),
        "md5": data_file.md5 or "-",
        "download_url": datafile_download_url(data_file.id),
    }


def _build_rows(params, include_files=False):
    keyword = (_param(params, "keyword") or _param(params, "search") or "").lower()
    species_id = _param(params, "species_id")
    accession_id = _param(params, "accession_id")
    assembly_id = _param(params, "assembly_id")
    sample_type_filter = (_param(params, "sample_type") or "").lower()

    relations = list(_transcriptome_relations())
    samples, assemblies, accessions = _collect_relation_contexts(relations)

    relations_by_file = {}
    for relation in relations:
        relations_by_file.setdefault(relation.file_id, []).append(relation)

    grouped = {}
    sample_types = set()
    for file_id, file_relations in relations_by_file.items():
        sample, accession, assembly, sample_type = _resolve_context(file_relations, samples, assemblies, accessions)
        species = (accession.species if accession else None) or (sample.species if sample else None)
        sample_type_normalized = (sample_type or "-").lower()
        sample_types.add(sample_type)

        if species_id and str(species.id if species else "") != str(species_id):
            continue
        if accession_id and str(accession.id if accession else "") != str(accession_id):
            continue
        if assembly_id and str(assembly.id if assembly else "") != str(assembly_id):
            continue
        if sample_type_filter and sample_type_normalized != sample_type_filter:
            continue

        searchable = " ".join(
            str(value or "")
            for value in (
                _species_name(species),
                _latin_name(species),
                accession.accession if accession else "",
                _assembly_name(assembly),
                sample_type,
            )
        ).lower()
        if keyword and keyword not in searchable:
            continue

        key = (
            accession.id if accession else None,
            assembly.id if assembly else None,
            sample_type,
        )
        row = grouped.setdefault(
            key,
            {
                "species_id": species.id if species else None,
                "species_name": _species_name(species),
                "latin_name": _latin_name(species),
                "accession_id": accession.id if accession else None,
                "accession": accession.accession if accession else "-",
                "assembly_id": assembly.id if assembly else None,
                "assembly_name": _assembly_name(assembly),
                "sample_type": sample_type,
                "file_ids": set(),
                "total_size": 0,
                "files": [],
            },
        )
        data_file = file_relations[0].file
        if data_file.id not in row["file_ids"]:
            row["file_ids"].add(data_file.id)
            row["total_size"] += data_file.file_size or 0
            if include_files:
                row["files"].append(_file_payload(file_relations[0]))

    rows = []
    for row in grouped.values():
        file_count = len(row.pop("file_ids"))
        row["file_count"] = file_count
        row["total_size_display"] = format_size(row["total_size"])
        if not include_files:
            row.pop("files", None)
        rows.append(row)
    rows.sort(key=lambda item: (item.get("species_name") or "", item.get("accession") or "", item.get("sample_type") or ""))
    return rows, sorted(sample_type for sample_type in sample_types if sample_type)


def build_transcriptome_list_payload(params):
    page, page_size = _page_params(params)
    rows, sample_types = _build_rows(params)
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "results": rows[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        "filters": {
            "species": [
                {
                    "id": species.id,
                    "label": _species_name(species),
                    "latin_name": _latin_name(species),
                }
                for species in Species.objects.all().order_by("species_code")
            ],
            "accessions": [
                {
                    "id": accession.id,
                    "label": accession.accession,
                    "species_id": accession.species_id,
                }
                for accession in Accession.objects.all().order_by("accession")
            ],
            "assemblies": [
                {
                    "id": assembly.id,
                    "label": _assembly_name(assembly),
                    "accession_id": assembly.accession_id,
                }
                for assembly in Assembly.objects.all().order_by("accession__accession", "name")
            ],
            "sample_types": sample_types or list(TRANSCRIPTOME_SAMPLE_TYPES),
        },
    }


def build_transcriptome_files_payload(params):
    rows, _ = _build_rows(params, include_files=True)
    row = rows[0] if rows else None
    if not row:
        return {
            "accession": "-",
            "assembly_name": "-",
            "sample_type": "-",
            "title": "Transcriptome 文件列表",
            "files": [],
        }
    title = f"{row['accession']} / {row['sample_type']} / Transcriptome 文件列表"
    return {
        "accession_id": row["accession_id"],
        "accession": row["accession"],
        "assembly_id": row["assembly_id"],
        "assembly_name": row["assembly_name"],
        "sample_type": row["sample_type"],
        "title": title,
        "files": row.get("files", []),
    }
