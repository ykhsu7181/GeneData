from pathlib import Path

from django.db.models import Q

from files.models import DataFile, Dataset, FileRelation
from files.services.datafile_access_service import (
    ACTION_METADATA,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)


def discover_accession_files(
    accession,
    *,
    principal=None,
    role=None,
    category=None,
    dataset=None,
    file_format=None,
    page=1,
    page_size=100,
):
    page = _positive_integer(page, "page")
    page_size = min(_positive_integer(page_size, "page_size"), 500)
    filters = {
        "role": _normalize_filter(role),
        "category": _normalize_filter(category),
        "dataset": _normalize_filter(dataset),
        "format": _normalize_filter(file_format),
    }
    context_filter = accession_relation_filter(accession)
    relation_rows = list(
        FileRelation.objects.filter(context_filter)
        .select_related("file")
        .order_by("file_id", "-is_primary", "id")
    )
    relation_map = {}
    for relation in relation_rows:
        relation_map.setdefault(relation.file_id, []).append(relation)

    files = (
        DataFile.objects.select_related("file_type", "dataset")
        .filter(
            id__in=relation_map,
            is_current=True,
            publication_status=DataFile.PUBLICATION_RELEASED,
        )
        .prefetch_related("relations")
        .order_by("file_code", "id")
    )
    results = []
    for data_file in files:
        decision = resolve_datafile_access(
            data_file,
            principal=principal,
            action=ACTION_METADATA,
        )
        if not decision.allowed:
            continue
        location = resolve_protected_datafile_path(data_file)
        if not location.allowed:
            continue
        try:
            stat = Path(location.resolved_path).stat()
        except OSError:
            continue

        context_relations = relation_map[data_file.id]
        roles = list(dict.fromkeys(item.file_role for item in context_relations))
        primary_role = roles[0] if roles else None
        format_value = datafile_format(data_file)
        category_value = datafile_category(data_file, roles)
        dataset_codes, dataset_aliases = datafile_datasets(data_file)
        if filters["role"] and not _matches_any(filters["role"], roles):
            continue
        if filters["category"] and filters["category"] != category_value.lower():
            continue
        if filters["format"] and filters["format"] != str(format_value or "").lower():
            continue
        if filters["dataset"] and filters["dataset"] not in dataset_aliases:
            continue

        results.append({
            "id": data_file.id,
            "file_code": data_file.file_code,
            "file_name": data_file.file_name,
            "role": primary_role,
            "format": format_value,
            "size": stat.st_size,
            "sha256": data_file.sha256.lower(),
            "md5": data_file.md5,
            "content_version": data_file.content_version,
            "dataset": dataset_codes[0] if len(dataset_codes) == 1 else None,
            "content_url": f"/gd/api/v1/files/{data_file.id}/content/",
        })

    total = len(results)
    start = (page - 1) * page_size
    return {
        "accession": accession.accession,
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": results[start:start + page_size],
    }


def accession_relation_filter(accession):
    assembly_ids = list(accession.assemblies.values_list("id", flat=True))
    annotation_ids = list(
        accession.assemblies.values_list("annotations__id", flat=True)
    )
    relation_filter = Q(related_type="accession", related_id=str(accession.id))
    if assembly_ids:
        relation_filter |= Q(
            related_type="assembly",
            related_id__in=[str(item) for item in assembly_ids],
        )
    if annotation_ids:
        relation_filter |= Q(
            related_type="annotation",
            related_id__in=[str(item) for item in annotation_ids if item],
        )
    return relation_filter


def datafile_format(data_file):
    if data_file.file_type_id:
        file_type = data_file.file_type
        value = file_type.format or file_type.code or file_type.name or file_type.extension
        if value:
            return value
    suffix = Path(data_file.file_name).suffix.lstrip(".")
    return suffix.upper() or None


def datafile_category(data_file, roles):
    if data_file.file_type_id and data_file.file_type.category:
        return data_file.file_type.category.lower()
    normalized_roles = " ".join(roles).lower()
    if any(value in normalized_roles for value in ("annotation", "gff", "gtf")):
        return "annotation"
    if any(value in normalized_roles for value in ("genome", "fasta", "fai")):
        return "genome"
    if any(value in normalized_roles for value in ("transcript", "rna", "expression")):
        return "transcriptome"
    return "other"


def datafile_datasets(data_file):
    ids = set()
    if data_file.dataset_id:
        ids.add(data_file.dataset_id)
    for value in data_file.relations.filter(related_type="dataset").values_list(
        "related_id", flat=True
    ):
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    datasets = list(Dataset.objects.filter(id__in=ids).order_by("dataset_code"))
    codes = [item.dataset_code for item in datasets]
    aliases = {
        value.lower()
        for item in datasets
        for value in (item.dataset_code, item.bioproject_accession)
        if value
    }
    return codes, aliases


def _normalize_filter(value):
    return str(value or "").strip().lower()


def _matches_any(expected, values):
    return any(expected == str(value or "").lower() for value in values)


def _positive_integer(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed
