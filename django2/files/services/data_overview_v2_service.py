"""File-level data overview query service.

The public overview deliberately exposes logical file metadata only. Storage
paths are internal implementation details and must never be serialized here.
"""

import json
from collections import OrderedDict

from django.db.models import Q, Sum

from files.models import (
    Accession,
    AccessionExternalMapping,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    Sample,
    Species,
)
from files.services.data_overview_service import (
    CATEGORY_LABELS,
    DATA_CATEGORIES,
    categorize_file_role,
    datafile_download_url,
    file_role_display,
    format_size,
)


SCHEMA_VERSION = 2
MAX_PAGE_SIZE = 100


def _value(params, key, default=""):
    value = params.get(key, default)
    return value.strip() if isinstance(value, str) else value


def _page_params(params):
    try:
        page = max(int(params.get("page", 1) or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = max(int(params.get("page_size", 20) or 20), 1)
    except (TypeError, ValueError):
        page_size = 20
    return page, min(page_size, MAX_PAGE_SIZE)


def _numeric_ids(values):
    return [int(value) for value in values if str(value).isdigit()]


def _relation_context_q(accession_ids):
    """Return relation predicates for every object owned by accessions."""
    accession_ids = list(accession_ids)
    if not accession_ids:
        return Q(pk__in=[])
    assembly_ids = list(
        Assembly.objects.filter(accession_id__in=accession_ids).values_list("id", flat=True)
    )
    annotation_ids = list(
        Annotation.objects.filter(
            Q(accession_id__in=accession_ids) | Q(assembly__accession_id__in=accession_ids)
        ).values_list("id", flat=True)
    )
    sample_ids = list(
        Sample.objects.filter(accession_id__in=accession_ids).values_list("id", flat=True)
    )
    dataset_ids = list(
        Dataset.objects.filter(accession_links__accession_id__in=accession_ids)
        .values_list("id", flat=True)
        .distinct()
    )
    relation_q = Q(related_type="accession", related_id__in=[str(pk) for pk in accession_ids])
    for related_type, ids in (
        ("assembly", assembly_ids),
        ("annotation", annotation_ids),
        ("sample", sample_ids),
        ("dataset", dataset_ids),
    ):
        if ids:
            relation_q |= Q(related_type=related_type, related_id__in=[str(pk) for pk in ids])
    return relation_q


def _file_ids_for_accessions(accession_ids):
    return FileRelation.objects.filter(_relation_context_q(accession_ids)).values("file_id")


def _category_roles(category):
    roles = FileRelation.objects.values_list("file_role", flat=True).distinct()
    return [role for role in roles if categorize_file_role(role) == category]


def _filtered_queryset(params):
    queryset = DataFile.objects.filter(is_current=True, relations__isnull=False).distinct()
    category = _value(params, "category") or _value(params, "data_category")
    species = _value(params, "species")
    accession = _value(params, "accession")
    dataset = _value(params, "dataset")
    search = _value(params, "search")

    if category:
        queryset = queryset.filter(relations__file_role__in=_category_roles(category))
    if dataset:
        dataset_q = Q(dataset__dataset_code=dataset)
        if str(dataset).isdigit():
            dataset_q |= Q(dataset__id=int(dataset))
        queryset = queryset.filter(dataset_q)
    if species:
        species_ids = Species.objects.filter(
            Q(species_code=species)
            | Q(scientific_name=species)
            | Q(chinese_name=species)
            | Q(common_name=species)
        ).values_list("id", flat=True)
        accession_ids = Accession.objects.filter(species_id__in=species_ids).values_list("id", flat=True)
        queryset = queryset.filter(
            Q(dataset__species_id__in=species_ids) | Q(id__in=_file_ids_for_accessions(accession_ids))
        )
    if accession:
        accession_ids = Accession.objects.filter(accession=accession).values_list("id", flat=True)
        queryset = queryset.filter(id__in=_file_ids_for_accessions(accession_ids))
    if search:
        accession_ids = Accession.objects.filter(
            Q(accession__icontains=search)
            | Q(species__species_code__icontains=search)
            | Q(species__scientific_name__icontains=search)
            | Q(species__chinese_name__icontains=search)
            | Q(species__common_name__icontains=search)
        ).values_list("id", flat=True)
        queryset = queryset.filter(
            Q(file_code__icontains=search)
            | Q(file_name__icontains=search)
            | Q(original_name__icontains=search)
            | Q(description__icontains=search)
            | Q(md5__icontains=search)
            | Q(dataset__dataset_code__icontains=search)
            | Q(dataset__dataset_name__icontains=search)
            | Q(relations__related_code__icontains=search)
            | Q(id__in=_file_ids_for_accessions(accession_ids))
        ).distinct()
    return queryset.order_by("file_name", "id")


def _batch_context(files):
    relation_ids = {key: set() for key in ("accession", "assembly", "annotation", "sample", "dataset")}
    for data_file in files:
        for relation in data_file.relations.all():
            if relation.related_type in relation_ids and str(relation.related_id).isdigit():
                relation_ids[relation.related_type].add(int(relation.related_id))

    accessions = {
        item.id: item
        for item in Accession.objects.filter(id__in=relation_ids["accession"]).select_related("species")
    }
    assemblies = {
        item.id: item
        for item in Assembly.objects.filter(id__in=relation_ids["assembly"]).select_related(
            "accession", "accession__species"
        )
    }
    annotations = {
        item.id: item
        for item in Annotation.objects.filter(id__in=relation_ids["annotation"]).select_related(
            "accession", "accession__species", "assembly", "assembly__accession", "assembly__accession__species"
        )
    }
    samples = {
        item.id: item
        for item in Sample.objects.filter(id__in=relation_ids["sample"]).select_related(
            "accession", "accession__species", "species"
        )
    }
    dataset_ids = relation_ids["dataset"] | {item.dataset_id for item in files if item.dataset_id}
    datasets = {
        item.id: item
        for item in Dataset.objects.filter(id__in=dataset_ids)
        .select_related("species", "project")
        .prefetch_related("accession_links__accession__species")
    }
    context_accession_ids = set(accessions)
    context_accession_ids.update(item.accession_id for item in assemblies.values())
    context_accession_ids.update(
        (item.accession_id or item.assembly.accession_id) for item in annotations.values()
    )
    context_accession_ids.update(item.accession_id for item in samples.values() if item.accession_id)
    for dataset in datasets.values():
        context_accession_ids.update(link.accession_id for link in dataset.accession_links.all())
    external_sources = {}
    for accession_id, source in AccessionExternalMapping.objects.filter(
        accession_id__in=context_accession_ids
    ).values_list("accession_id", "external_database"):
        if source and accession_id not in external_sources:
            external_sources[accession_id] = source
    return {
        "accession": accessions,
        "assembly": assemblies,
        "annotation": annotations,
        "sample": samples,
        "dataset": datasets,
        "external_sources": external_sources,
    }


def _append_unique(items, value):
    if value and value not in items:
        items.append(value)


def _file_context(data_file, context):
    accession_objects = OrderedDict()
    source_groups = {
        "annotation_name": [],
        "annotation_database": [],
        "assembly_database": [],
        "dataset": [],
    }
    relations = sorted(data_file.relations.all(), key=lambda item: (not item.is_primary, item.id))
    for relation in relations:
        obj = context.get(relation.related_type, {}).get(
            int(relation.related_id) if str(relation.related_id).isdigit() else None
        )
        accession_obj = None
        if relation.related_type == "accession":
            accession_obj = obj
        elif relation.related_type == "assembly" and obj:
            accession_obj = obj.accession
            _append_unique(source_groups["assembly_database"], obj.source_database)
        elif relation.related_type == "annotation" and obj:
            accession_obj = obj.accession or obj.assembly.accession
            _append_unique(source_groups["annotation_name"], obj.source_name)
            _append_unique(source_groups["annotation_database"], obj.source_database)
        elif relation.related_type == "sample" and obj:
            accession_obj = obj.accession
        elif relation.related_type == "dataset" and obj:
            for link in obj.accession_links.all():
                accession_objects[link.accession_id] = link.accession
                _append_unique(source_groups["dataset"], link.source)
        if accession_obj:
            accession_objects[accession_obj.id] = accession_obj

    dataset = context["dataset"].get(data_file.dataset_id)
    if dataset:
        for link in dataset.accession_links.all():
            accession_objects[link.accession_id] = link.accession
            _append_unique(source_groups["dataset"], link.source)
    accessions = list(accession_objects.values())
    species = OrderedDict()
    if dataset and dataset.species:
        species[dataset.species.id] = dataset.species
    for accession in accessions:
        if accession.species:
            species[accession.species.id] = accession.species
    ordered_sources = []
    for key in ("annotation_name", "annotation_database", "assembly_database", "dataset"):
        for source in source_groups[key]:
            _append_unique(ordered_sources, source)
    for accession_obj in accessions:
        _append_unique(ordered_sources, context["external_sources"].get(accession_obj.id))
    return relations, accessions, list(species.values()), ordered_sources, dataset


def _category_for_relations(relations):
    for relation in relations:
        category = categorize_file_role(relation.file_role)
        if category != "other":
            return category, relation
    return ("other", relations[0] if relations else None)


def _serialize_file(data_file, context):
    relations, accessions, species, sources, dataset = _file_context(data_file, context)
    category, primary_relation = _category_for_relations(relations)
    file_type = data_file.file_type
    species_rows = [
        {
            "code": item.species_code,
            "name": item.chinese_name or item.common_name or item.scientific_name or item.species_code,
            "scientific_name": item.scientific_name,
        }
        for item in species
    ]
    accession_codes = [item.accession for item in accessions]
    return {
        "file_id": data_file.id,
        "file_code": data_file.file_code,
        "category": category,
        "category_display": CATEGORY_LABELS.get(category, "其他"),
        "file_name": data_file.file_name,
        "original_name": data_file.original_name,
        "species": species_rows,
        "species_code": species_rows[0]["code"] if len(species_rows) == 1 else ("Multiple" if species_rows else None),
        "species_name": species_rows[0]["name"] if len(species_rows) == 1 else ("Multiple" if species_rows else None),
        "accession": accession_codes[0] if len(accession_codes) == 1 else ("Multiple" if accession_codes else None),
        "accessions": accession_codes,
        "dataset_id": dataset.id if dataset else None,
        "dataset_code": dataset.dataset_code if dataset else None,
        "dataset_name": dataset.dataset_name if dataset else None,
        "data_source": sources[0] if sources else "-",
        "data_sources": sources,
        "file_type": (file_type.format or file_type.extension or file_type.name) if file_type else None,
        "file_size": data_file.file_size,
        "file_size_display": format_size(data_file.file_size),
        "md5": data_file.md5,
        "description": description_display(data_file.description),
        "file_role": primary_relation.file_role if primary_relation else None,
        "file_role_display": file_role_display(primary_relation.file_role) if primary_relation else None,
        "download_url": datafile_download_url(data_file.id),
        "updated_at": data_file.updated_at.isoformat() if data_file.updated_at else None,
    }


def description_display(value):
    """Return a short public description without leaking serialized internals."""
    if not value:
        return "-"
    if not isinstance(value, str):
        return str(value)
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return value
    if not isinstance(payload, dict):
        return "-"
    raw_data = payload.get("raw_data")
    if isinstance(raw_data, dict):
        return raw_data.get("remark") or raw_data.get("raw_data_type") or "-"
    return payload.get("remark") or payload.get("description") or "-"


def build_datafile_detail_payload(file_id):
    data_file = (
        DataFile.objects.filter(id=file_id, is_current=True)
        .select_related("dataset", "file_type")
        .prefetch_related("relations")
        .first()
    )
    if not data_file:
        return None
    context = _batch_context([data_file])
    row = _serialize_file(data_file, context)
    relations, accessions, species, _, dataset = _file_context(data_file, context)
    return {
        **row,
        "description": description_display(data_file.description),
        "is_current": data_file.is_current,
        "dataset": {
            "dataset_id": dataset.id,
            "dataset_code": dataset.dataset_code,
            "dataset_name": dataset.dataset_name,
            "dataset_type": dataset.dataset_type,
        } if dataset else None,
        "accessions": [item.accession for item in accessions],
        "species": [
            item.scientific_name or item.common_name or item.chinese_name or item.species_code
            for item in species
        ],
        "relations": [
            {
                "related_type": relation.related_type,
                "related_code": relation.related_code,
                "file_role": relation.file_role,
                "file_role_display": file_role_display(relation.file_role),
                "is_primary": relation.is_primary,
            }
            for relation in relations
        ],
        "created_at": data_file.created_at.isoformat() if data_file.created_at else None,
    }


def _summary_payload():
    files = DataFile.objects.filter(is_current=True, relations__isnull=False).distinct()
    aggregation = files.aggregate(total_size=Sum("file_size"))
    latest = files.order_by("-updated_at").values_list("updated_at", flat=True).first()
    geo_count = (
        Accession.objects.filter(longitude__isnull=False, latitude__isnull=False)
        .values("longitude", "latitude")
        .distinct()
        .count()
    )
    return {
        "accession_count": Accession.objects.count(),
        "assembly_count": Assembly.objects.count(),
        "dataset_count": Dataset.objects.count(),
        "datafile_count": files.count(),
        "total_size": aggregation["total_size"] or 0,
        "total_size_display": format_size(aggregation["total_size"] or 0),
        "geo_location_count": geo_count,
        "latest_update": latest.date().isoformat() if latest else None,
    }


def _filters_payload():
    return {
        "data_categories": [
            {"key": key, "label": zh, "en_label": en} for key, zh, en in DATA_CATEGORIES
        ],
        "species": [
            {
                "key": item.species_code,
                "label": item.chinese_name or item.common_name or item.scientific_name or item.species_code,
                "latin_name": item.scientific_name,
            }
            for item in Species.objects.order_by("species_code")
        ],
        "accessions": [
            {"key": code, "label": code}
            for code in Accession.objects.order_by("accession").values_list("accession", flat=True)
        ],
        "datasets": [
            {
                "key": item.dataset_code,
                "label": f"{item.dataset_code} · {item.dataset_name}" if item.dataset_name else item.dataset_code,
            }
            for item in Dataset.objects.order_by("dataset_code")
        ],
    }


def build_data_overview_payload(params):
    page, page_size = _page_params(params)
    queryset = _filtered_queryset(params)
    count = queryset.count()
    start = (page - 1) * page_size
    files = list(
        queryset.select_related("dataset", "file_type").prefetch_related("relations")[start : start + page_size]
    )
    context = _batch_context(files)
    return {
        "schema_version": SCHEMA_VERSION,
        "count": count,
        "page": page,
        "page_size": page_size,
        "next": f"?page={page + 1}&page_size={page_size}" if start + page_size < count else None,
        "previous": f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        "summary": _summary_payload(),
        "filters": _filters_payload(),
        "results": [_serialize_file(data_file, context) for data_file in files],
    }
