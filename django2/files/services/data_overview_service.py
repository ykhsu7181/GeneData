from collections import OrderedDict

from django.db.models import Q

from files.models import Accession, DataFile, FileRelation, Species


DATA_CATEGORIES = [
    ("raw_data", "原始数据", "Raw Data"),
    ("genome", "基因组", "Genome"),
    ("annotation", "注释", "Annotation"),
    ("transcriptome", "转录组", "Transcriptome"),
    ("population", "群体遗传", "Population"),
    ("codon", "密码子", "Codon"),
    ("centromere", "着丝粒", "Centromere"),
    ("tes", "转座子", "TEs"),
    ("coreblocks", "核心可变区块", "CoreBlocks"),
    ("ncrna", "ncRNA", "ncRNA"),
]

CATEGORY_LABELS = {key: zh for key, zh, _ in DATA_CATEGORIES}

FILE_ROLE_DISPLAY = {
    "genome": "参考基因组序列",
    "genome_fasta": "参考基因组序列",
    "genome_index": "基因组索引",
    "annotation": "基因注释文件",
    "annotation_gff3": "基因注释 GFF3",
    "annotation_gff": "基因注释 GFF",
    "annotation_gtf": "基因注释 GTF",
    "transcriptome": "转录组文件",
    "transcriptome_matrix": "表达矩阵",
    "raw_data": "原始测序数据",
    "raw_reads": "原始测序数据",
    "codon": "密码子文件",
    "centromere": "着丝粒文件",
    "te": "转座子文件",
    "tes": "转座子文件",
    "coreblocks": "核心可变区块",
    "core_blocks": "核心可变区块",
    "mirna": "miRNA",
    "trna": "tRNA",
    "rrna": "rRNA",
    "ncrna": "ncRNA",
    "checksum": "校验文件",
}


def file_role_display(file_role):
    normalized = (file_role or "").strip()
    lower = normalized.lower()
    return FILE_ROLE_DISPLAY.get(lower) or FILE_ROLE_DISPLAY.get(normalized) or "其他文件"


def categorize_file_role(file_role):
    value = (file_role or "").strip().lower()
    if not value:
        return "other"
    if any(token in value for token in ("raw", "reads", "fastq", "seqdata")):
        return "raw_data"
    if "annotation" in value or value in {"gff", "gff3", "gtf"}:
        return "annotation"
    if "transcriptome" in value or "expression" in value or "rna_seq" in value:
        return "transcriptome"
    if "population" in value or "variant" in value:
        return "population"
    if "codon" in value:
        return "codon"
    if "centromere" in value:
        return "centromere"
    if value in {"te", "tes"} or "transposable" in value:
        return "tes"
    if "coreblock" in value or "core_block" in value or "variableblock" in value:
        return "coreblocks"
    if value in {"mirna", "trna", "rrna", "ncrna"} or "mirna" in value or "trna" in value or "rrna" in value:
        return "ncrna"
    if "genome" in value or "assembly" in value or value in {"fasta", "fa", "fai"}:
        return "genome"
    return "other"


def format_size(size):
    if not size:
        return "-"
    size = int(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{size} B"
    return f"{value:.2f}".rstrip("0").rstrip(".") + f" {units[unit_index]}"


def datafile_download_url(file_id):
    return f"/gd/api/files/data-files/{file_id}/download/" if file_id else None


def _params_get(params, key, default=""):
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
        return None
    return species.scientific_name or species.common_name or species.species_code


def _normalize_sub_population(value):
    return value.strip() if value and value.strip() else "Unknown"


def _accessions_queryset(params):
    search = _params_get(params, "search")
    species_filter = _params_get(params, "species")
    sub_populations = _params_get(params, "sub_populations")
    location = _params_get(params, "location")

    queryset = Accession.objects.select_related("species").prefetch_related("assemblies__annotations").order_by("accession")
    if search:
        queryset = queryset.filter(
            Q(accession__icontains=search)
            | Q(species__species_code__icontains=search)
            | Q(species__scientific_name__icontains=search)
            | Q(species__chinese_name__icontains=search)
            | Q(species__common_name__icontains=search)
            | Q(country__icontains=search)
            | Q(region__icontains=search)
        ).distinct()
    if species_filter:
        queryset = queryset.filter(
            Q(species__species_code=species_filter)
            | Q(species__scientific_name=species_filter)
            | Q(species__chinese_name=species_filter)
            | Q(species__common_name=species_filter)
        )
    if location:
        queryset = queryset.filter(Q(country__icontains=location) | Q(region__icontains=location))

    accessions = list(queryset)
    if sub_populations:
        if sub_populations == "NONE":
            return []
        selected = {item.strip() for item in sub_populations.split(",") if item.strip()}
        accessions = [
            accession
            for accession in accessions
            if _normalize_sub_population(accession.sub_population) in selected
        ]
    return accessions


def _default_assembly(accession):
    assemblies = list(accession.assemblies.all())
    return next((assembly for assembly in assemblies if assembly.is_default), None) or (assemblies[0] if assemblies else None)


def _default_annotation(assembly):
    annotations = list(assembly.annotations.all()) if assembly else []
    return next((annotation for annotation in annotations if annotation.is_default), None) or (annotations[0] if annotations else None)


def _relation_filter_for_accession(accession):
    assemblies = list(accession.assemblies.all())
    assembly_ids = [str(assembly.id) for assembly in assemblies]
    annotation_ids = [
        str(annotation.id)
        for assembly in assemblies
        for annotation in assembly.annotations.all()
    ]
    relation_filter = Q(related_type="accession", related_id=str(accession.id))
    if assembly_ids:
        relation_filter |= Q(related_type="assembly", related_id__in=assembly_ids)
    if annotation_ids:
        relation_filter |= Q(related_type="annotation", related_id__in=annotation_ids)
    return relation_filter


def _file_record(relation):
    data_file = relation.file
    file_type = data_file.file_type
    return {
        "file_id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "file_path": data_file.file_path,
        "file_role": relation.file_role,
        "file_role_display": file_role_display(relation.file_role),
        "file_type": (file_type.format or file_type.extension or file_type.name) if file_type else "",
        "file_size": data_file.file_size,
        "file_size_display": format_size(data_file.file_size),
        "md5": data_file.md5,
        "download_url": datafile_download_url(data_file.id),
        "dataset_id": data_file.dataset_id,
        "dataset_code": data_file.dataset.dataset_code if data_file.dataset else None,
        "dataset_name": data_file.dataset.dataset_name if data_file.dataset else None,
        "dataset_type": data_file.dataset.dataset_type if data_file.dataset else None,
        "updated_at": data_file.updated_at,
        "source": "new_relation",
    }


def _files_for_accession(accession, params):
    dataset_type = _params_get(params, "dataset_type")
    category_filter = _params_get(params, "category") or _params_get(params, "data_category")
    file_role = _params_get(params, "file_role")
    relations = (
        FileRelation.objects.filter(_relation_filter_for_accession(accession))
        .select_related("file", "file__dataset", "file__file_type")
        .order_by("file_role", "file_id")
    )
    files_by_category = OrderedDict((key, OrderedDict()) for key, _, _ in DATA_CATEGORIES)
    all_files = OrderedDict()
    for relation in relations:
        record = _file_record(relation)
        if dataset_type and record["dataset_type"] != dataset_type:
            continue
        if file_role and relation.file_role != file_role:
            continue
        category = categorize_file_role(relation.file_role)
        if category_filter and category != category_filter:
            continue
        all_files.setdefault(record["file_id"], record)
        if category in files_by_category:
            files_by_category[category].setdefault(record["file_id"], record)
    return files_by_category, all_files


def _cell_payload(category, files):
    file_list = list(files.values())
    if category == "population" and not file_list:
        return {
            "category": category,
            "status": "coming_soon",
            "file_count": 0,
            "total_size": 0,
            "total_size_display": "-",
            "display": "建设中",
            "file_ids": [],
        }
    total_size = sum((item["file_size"] or 0) for item in file_list)
    return {
        "category": category,
        "status": "available" if file_list else "empty",
        "file_count": len(file_list),
        "total_size": total_size,
        "total_size_display": format_size(total_size),
        "display": f"{len(file_list)} / {format_size(total_size)}" if file_list else "-",
        "file_ids": [item["file_id"] for item in file_list],
    }


def _matrix_row(accession, files_by_category):
    assembly = _default_assembly(accession)
    annotation = _default_annotation(assembly)
    cells = {
        key: _cell_payload(key, files_by_category[key])
        for key, _, _ in DATA_CATEGORIES
    }
    return {
        "accession_id": accession.id,
        "accession": accession.accession,
        "species_name": _species_name(accession.species),
        "species_latin_name": _latin_name(accession.species),
        "sub_population": _normalize_sub_population(accession.sub_population),
        "sample_count": accession.samples.count(),
        "country": accession.country,
        "region": accession.region,
        "location_display": ", ".join([item for item in [accession.region, accession.country] if item]) or "-",
        "longitude": accession.longitude,
        "latitude": accession.latitude,
        "default_assembly_id": assembly.id if assembly else None,
        "default_assembly_name": assembly.name if assembly else None,
        "default_annotation_id": annotation.id if annotation else None,
        "default_annotation_name": annotation.name if annotation else None,
        "cells": cells,
    }


def _detail_rows(accession, files_by_category):
    assembly = _default_assembly(accession)
    annotation = _default_annotation(assembly)
    rows = []
    for category, zh_label, en_label in DATA_CATEGORIES:
        files = list(files_by_category[category].values())
        if not files:
            continue
        total_size = sum((item["file_size"] or 0) for item in files)
        updated_at = max((item["updated_at"] for item in files if item["updated_at"]), default=None)
        dataset_names = [item["dataset_name"] for item in files if item.get("dataset_name")]
        rows.append(
            {
                "accession_id": accession.id,
                "accession": accession.accession,
                "species_name": _species_name(accession.species),
                "category": category,
                "category_display": f"{zh_label} ({en_label})",
                "dataset_name": dataset_names[0] if dataset_names else "-",
                "assembly_name": assembly.name if assembly else "-",
                "annotation_name": annotation.name if annotation and category in {"annotation", "transcriptome"} else "-",
                "file_count": len(files),
                "total_size": total_size,
                "total_size_display": format_size(total_size),
                "updated_at": updated_at.isoformat() if updated_at else None,
                "status": "available",
            }
        )
    return rows


def _summary(accessions, row_file_maps):
    unique_files = OrderedDict()
    dataset_ids = set()
    latest_update = None
    for file_map in row_file_maps:
        for file_id, record in file_map.items():
            unique_files.setdefault(file_id, record)
            if record.get("dataset_id"):
                dataset_ids.add(record["dataset_id"])
            if record.get("updated_at") and (latest_update is None or record["updated_at"] > latest_update):
                latest_update = record["updated_at"]
    total_size = sum((item["file_size"] or 0) for item in unique_files.values())
    geo_location_count = len(
        {
            accession.id
            for accession in accessions
            if accession.longitude is not None and accession.latitude is not None
        }
    )
    return {
        "accession_count": len(accessions),
        "dataset_count": len(dataset_ids),
        "datafile_count": len(unique_files),
        "total_size": total_size,
        "total_size_display": format_size(total_size),
        "geo_location_count": geo_location_count,
        "latest_update": latest_update.date().isoformat() if latest_update else None,
    }


def _filters_payload():
    species_options = [
        {
            "key": species.species_code,
            "label": _species_name(species),
            "latin_name": _latin_name(species),
        }
        for species in Species.objects.order_by("species_code")
    ]
    sub_populations = [
        _normalize_sub_population(value)
        for value in Accession.objects.values_list("sub_population", flat=True).distinct()
    ]
    locations = []
    for country, region in Accession.objects.values_list("country", "region").distinct():
        label = ", ".join([item for item in [region, country] if item])
        if label:
            locations.append(label)
    return {
        "species": species_options,
        "sub_populations": sorted(set(sub_populations)),
        "locations": sorted(set(locations)),
        "data_categories": [
            {"key": key, "label": zh, "en_label": en}
            for key, zh, en in DATA_CATEGORIES
        ],
        "file_roles": [
            {"key": role, "label": file_role_display(role)}
            for role in FileRelation.objects.values_list("file_role", flat=True).distinct().order_by("file_role")
            if role
        ],
    }


def build_data_overview_payload(params):
    page, page_size = _page_params(params)
    accessions = _accessions_queryset(params)
    matrix_rows = []
    detail_rows = []
    row_file_maps = []
    selected_accessions = []
    for accession in accessions:
        files_by_category, all_files = _files_for_accession(accession, params)
        has_file_filter = bool(
            _params_get(params, "dataset_type")
            or _params_get(params, "file_role")
            or _params_get(params, "category")
            or _params_get(params, "data_category")
        )
        if has_file_filter and not all_files:
            continue
        selected_accessions.append(accession)
        matrix_rows.append(_matrix_row(accession, files_by_category))
        detail_rows.extend(_detail_rows(accession, files_by_category))
        row_file_maps.append(all_files)

    total = len(matrix_rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = matrix_rows[start:end]
    page_accession_ids = {row["accession_id"] for row in page_rows}
    page_detail_rows = [row for row in detail_rows if row["accession_id"] in page_accession_ids]
    return {
        "count": total,
        "next": f"?page={page + 1}&page_size={page_size}" if end < total else None,
        "previous": f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        "page": page,
        "page_size": page_size,
        "summary": _summary(selected_accessions, row_file_maps),
        "filters": _filters_payload(),
        "matrix_rows": page_rows,
        "detail_rows": page_detail_rows,
    }


def build_data_overview_files_payload(params):
    accession_code = _params_get(params, "accession")
    accession_id = _params_get(params, "accession_id")
    category = _params_get(params, "category")
    queryset = Accession.objects.select_related("species").prefetch_related("assemblies__annotations")
    if accession_id:
        accession = queryset.filter(id=accession_id).first()
    else:
        accession = queryset.filter(accession=accession_code).first()
    if not accession:
        return None

    files_by_category, _ = _files_for_accession(accession, params)
    categories = [category] if category else [key for key, _, _ in DATA_CATEGORIES]
    files = OrderedDict()
    for key in categories:
        if key in files_by_category:
            for file_id, record in files_by_category[key].items():
                files.setdefault(file_id, record)

    assembly = _default_assembly(accession)
    annotation = _default_annotation(assembly)
    label = CATEGORY_LABELS.get(category, "全部文件")
    return {
        "title": f"{accession.accession} / {label} 文件列表",
        "category": category,
        "relation_overview": {
            "accession": accession.accession,
            "assembly": assembly.name if assembly else None,
            "annotation": annotation.name if annotation else None,
        },
        "files": list(files.values()),
    }
