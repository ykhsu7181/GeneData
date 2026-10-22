"""Tool-neutral external DataFile catalog with fail-closed visibility."""

from collections import defaultdict
from pathlib import Path
import unicodedata

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Sample,
)
from files.services.datafile_access_service import (
    ACTION_METADATA,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)
from files.services.external_file_discovery_service import datafile_format
from files.services.external_file_urls import external_content_url


MAX_PAGE_SIZE = 500


def list_external_files(
    *,
    principal=None,
    file_name=None,
    name_contains=None,
    accession=None,
    assembly=None,
    dataset=None,
    role=None,
    file_format=None,
    page=1,
    page_size=100,
):
    """Return only released, authorized, physically available DataFiles."""
    page = _positive_integer(page, "page")
    page_size = min(_positive_integer(page_size, "page_size"), MAX_PAGE_SIZE)
    collected = collect_external_files(
        principal=principal,
        file_name=file_name,
        name_contains=name_contains,
        accession=accession,
        assembly=assembly,
        dataset=dataset,
        role=role,
        file_format=file_format,
    )
    results = [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in collected
    ]
    total = len(results)
    start = (page - 1) * page_size
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": results[start:start + page_size],
    }


def collect_external_files(
    *,
    principal=None,
    action=ACTION_METADATA,
    file_name=None,
    name_contains=None,
    accession=None,
    assembly=None,
    dataset=None,
    role=None,
    file_format=None,
):
    """Return the complete authorized catalog for server-side batch resolution."""
    filters = {
        "file_name": normalize_file_name(file_name),
        "name_contains": normalize_file_name(name_contains),
        "accession": normalize_file_name(accession),
        "assembly": normalize_file_name(assembly),
        "dataset": normalize_file_name(dataset),
        "role": normalize_file_name(role),
        "format": normalize_file_name(file_format),
    }

    queryset = (
        DataFile.objects.select_related("file_type", "dataset")
        .filter(
            is_current=True,
            publication_status=DataFile.PUBLICATION_RELEASED,
        )
        .order_by("file_code", "id")
    )
    files = list(queryset)
    relations = list(
        FileRelation.objects.filter(file_id__in=[item.id for item in files])
        .order_by("file_id", "-is_primary", "id")
    )
    relation_map = defaultdict(list)
    for relation in relations:
        relation_map[relation.file_id].append(relation)
    context = _build_context(relations, files)

    results = []
    for data_file in files:
        decision = resolve_datafile_access(
            data_file,
            principal=principal,
            action=action,
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

        item = _serialize_file(
            data_file,
            relation_map[data_file.id],
            context,
            stat,
        )
        if not _matches_filters(item, filters):
            continue
        results.append(item)

    results.sort(
        key=lambda item: (
            normalize_file_name(item["file_name"]),
            normalize_file_name(item["file_code"]),
        )
    )
    return results


def _serialize_file(data_file, relations, context, stat):
    roles = list(dict.fromkeys(item.file_role for item in relations))
    accessions = set()
    assemblies = set()
    assembly_aliases = set()
    dataset_ids = set()

    if data_file.dataset_id:
        dataset_ids.add(data_file.dataset_id)

    for relation in relations:
        try:
            related_id = int(relation.related_id)
        except (TypeError, ValueError):
            continue
        if relation.related_type == "accession":
            value = context["accessions"].get(related_id)
            if value:
                accessions.add(value)
        elif relation.related_type == "assembly":
            value = context["assemblies"].get(related_id)
            if value:
                assemblies.add(value["code"])
                assembly_aliases.update(value["aliases"])
                if value["accession"]:
                    accessions.add(value["accession"])
        elif relation.related_type == "annotation":
            value = context["annotations"].get(related_id)
            if value:
                assemblies.add(value["code"])
                assembly_aliases.update(value["aliases"])
                if value["accession"]:
                    accessions.add(value["accession"])
        elif relation.related_type == "sample":
            value = context["samples"].get(related_id)
            if value:
                accessions.add(value)
        elif relation.related_type == "dataset":
            dataset_ids.add(related_id)

    datasets = []
    dataset_aliases = set()
    for dataset_id in sorted(dataset_ids):
        value = context["datasets"].get(dataset_id)
        if not value:
            continue
        datasets.append(value["code"])
        dataset_aliases.update(value["aliases"])
        accessions.update(context["dataset_accessions"].get(dataset_id, ()))

    accessions = sorted(accessions, key=normalize_file_name)
    assemblies = sorted(assemblies, key=normalize_file_name)
    datasets = sorted(set(datasets), key=normalize_file_name)
    return {
        "id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "format": datafile_format(data_file),
        "role": roles[0] if roles else None,
        "roles": roles,
        "size": stat.st_size,
        "sha256": data_file.sha256.lower(),
        "md5": data_file.md5,
        "content_version": data_file.content_version,
        "accession": accessions[0] if len(accessions) == 1 else None,
        "accessions": accessions,
        "assembly": assemblies[0] if len(assemblies) == 1 else None,
        "assemblies": assemblies,
        "dataset": datasets[0] if len(datasets) == 1 else None,
        "datasets": datasets,
        "content_url": external_content_url(data_file.file_code),
        "_assembly_aliases": sorted(assembly_aliases),
        "_dataset_aliases": sorted(dataset_aliases),
    }


def _matches_filters(item, filters):
    if filters["file_name"] and filters["file_name"] != normalize_file_name(item["file_name"]):
        return False
    if filters["name_contains"] and filters["name_contains"] not in normalize_file_name(item["file_name"]):
        return False
    if filters["accession"] and not _matches(filters["accession"], item["accessions"]):
        return False
    if filters["assembly"] and not _matches(
        filters["assembly"],
        list(item["assemblies"]) + list(item["_assembly_aliases"]),
    ):
        return False
    if filters["dataset"] and not _matches(
        filters["dataset"],
        list(item["datasets"]) + list(item["_dataset_aliases"]),
    ):
        return False
    if filters["role"] and not _matches(filters["role"], item["roles"]):
        return False
    if filters["format"] and filters["format"] != normalize_file_name(item["format"]):
        return False
    return True


def _build_context(relations, files):
    related_ids = defaultdict(set)
    dataset_ids = {item.dataset_id for item in files if item.dataset_id}
    for relation in relations:
        try:
            related_id = int(relation.related_id)
        except (TypeError, ValueError):
            continue
        related_ids[relation.related_type].add(related_id)
        if relation.related_type == "dataset":
            dataset_ids.add(related_id)

    accessions = dict(
        Accession.objects.filter(id__in=related_ids["accession"])
        .values_list("id", "accession")
    )
    assemblies = {}
    for item in Assembly.objects.select_related("accession").filter(
        id__in=related_ids["assembly"]
    ):
        assemblies[item.id] = _assembly_context(item)
    annotations = {}
    for item in Annotation.objects.select_related("assembly__accession").filter(
        id__in=related_ids["annotation"]
    ):
        annotations[item.id] = _assembly_context(item.assembly)
    samples = dict(
        Sample.objects.filter(
            id__in=related_ids["sample"],
            accession__isnull=False,
        ).values_list("id", "accession__accession")
    )
    datasets = {}
    for item in Dataset.objects.filter(id__in=dataset_ids):
        aliases = {item.dataset_code}
        if item.bioproject_accession:
            aliases.add(item.bioproject_accession)
        datasets[item.id] = {
            "code": item.dataset_code,
            "aliases": sorted(aliases, key=normalize_file_name),
        }
    dataset_accessions = defaultdict(set)
    for dataset_id, accession in DatasetAccession.objects.filter(
        dataset_id__in=dataset_ids
    ).values_list("dataset_id", "accession__accession"):
        dataset_accessions[dataset_id].add(accession)
    return {
        "accessions": accessions,
        "assemblies": assemblies,
        "annotations": annotations,
        "samples": samples,
        "datasets": datasets,
        "dataset_accessions": dataset_accessions,
    }


def _assembly_context(assembly):
    code = assembly.assembly_code or assembly.assembly_accession or str(assembly.id)
    aliases = {
        value
        for value in (
            assembly.assembly_code,
            assembly.assembly_accession,
            assembly.name,
            assembly.assembly_name,
        )
        if value
    }
    return {
        "code": code,
        "aliases": sorted(aliases, key=normalize_file_name),
        "accession": assembly.accession.accession if assembly.accession_id else None,
    }


def _matches(expected, values):
    return any(expected == normalize_file_name(value) for value in values)


def normalize_file_name(value):
    return unicodedata.normalize("NFC", str(value or "").strip()).casefold()


def _positive_integer(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed
