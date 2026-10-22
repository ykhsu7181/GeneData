"""Dataset manifests for external workflow engines."""

from collections import defaultdict
from pathlib import Path

from django.db.models import Q

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
    ACTION_MANIFEST,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)
from files.services.external_file_discovery_service import datafile_format


def find_public_datasets(identifier):
    try:
        exact = Dataset.objects.get(dataset_code=identifier)
    except Dataset.DoesNotExist:
        queryset = Dataset.objects.filter(visibility="public", status="released")
        return list(
            queryset.filter(bioproject_accession=identifier).order_by("dataset_code", "id")
        )
    if exact.visibility != "public" or exact.status != "released":
        return []
    return [exact]


def build_dataset_manifest(identifier, datasets, *, principal):
    dataset_ids = {dataset.id for dataset in datasets}
    dataset_relation_file_ids = FileRelation.objects.filter(
        related_type="dataset",
        related_id__in=[str(item) for item in dataset_ids],
    ).values_list("file_id", flat=True)
    files = list(
        DataFile.objects.select_related("file_type", "dataset")
        .filter(
            Q(dataset_id__in=dataset_ids) | Q(id__in=dataset_relation_file_ids),
            is_current=True,
            publication_status=DataFile.PUBLICATION_RELEASED,
        )
        .distinct()
        .order_by("file_code", "id")
    )
    relations = list(
        FileRelation.objects.filter(file_id__in=[item.id for item in files])
        .order_by("file_id", "-is_primary", "id")
    )
    relation_map = defaultdict(list)
    for relation in relations:
        relation_map[relation.file_id].append(relation)

    context_maps = _context_accession_maps(relations)
    dataset_accessions = _dataset_accession_map(dataset_ids)
    rows = []
    for data_file in files:
        decision = resolve_datafile_access(
            data_file,
            principal=principal,
            action=ACTION_MANIFEST,
        )
        if (
            not decision.allowed
            or decision.effective_access_level != DataFile.ACCESS_LEVEL_PUBLIC
        ):
            continue
        location = resolve_protected_datafile_path(data_file)
        if not location.allowed:
            continue
        try:
            size = Path(location.resolved_path).stat().st_size
        except OSError:
            continue

        file_relations = relation_map[data_file.id]
        file_dataset_ids = _file_dataset_ids(data_file, file_relations, dataset_ids)
        accessions = _file_accessions(
            file_relations,
            context_maps,
            file_dataset_ids,
            dataset_accessions,
        )
        roles = list(dict.fromkeys(relation.file_role for relation in file_relations))
        rows.append({
            "id": data_file.id,
            "accession": accessions[0] if len(accessions) == 1 else None,
            "accessions": accessions,
            "role": roles[0] if roles else None,
            "file_name": data_file.file_name,
            "format": datafile_format(data_file),
            "size": size,
            "sha256": data_file.sha256.lower(),
            "md5": data_file.md5,
            "content_version": data_file.content_version,
            "content_url": f"/gd/api/v1/files/{data_file.id}/content/",
        })

    return {
        "dataset": identifier,
        "dataset_codes": [item.dataset_code for item in datasets],
        "count": len(rows),
        "files": rows,
    }


def _file_dataset_ids(data_file, relations, allowed_ids):
    ids = set()
    if data_file.dataset_id in allowed_ids:
        ids.add(data_file.dataset_id)
    for relation in relations:
        if relation.related_type != "dataset":
            continue
        try:
            dataset_id = int(relation.related_id)
        except (TypeError, ValueError):
            continue
        if dataset_id in allowed_ids:
            ids.add(dataset_id)
    return ids


def _context_accession_maps(relations):
    ids = defaultdict(set)
    for relation in relations:
        if relation.related_type in {"accession", "assembly", "annotation", "sample"}:
            try:
                ids[relation.related_type].add(int(relation.related_id))
            except (TypeError, ValueError):
                continue
    return {
        "accession": dict(
            Accession.objects.filter(id__in=ids["accession"])
            .values_list("id", "accession")
        ),
        "assembly": dict(
            Assembly.objects.filter(id__in=ids["assembly"])
            .values_list("id", "accession__accession")
        ),
        "annotation": dict(
            Annotation.objects.filter(id__in=ids["annotation"])
            .values_list("id", "assembly__accession__accession")
        ),
        "sample": dict(
            Sample.objects.filter(id__in=ids["sample"], accession__isnull=False)
            .values_list("id", "accession__accession")
        ),
    }


def _dataset_accession_map(dataset_ids):
    result = defaultdict(set)
    for dataset_id, accession in DatasetAccession.objects.filter(
        dataset_id__in=dataset_ids
    ).values_list("dataset_id", "accession__accession"):
        result[dataset_id].add(accession)
    return result


def _file_accessions(relations, context_maps, dataset_ids, dataset_accessions):
    accessions = set()
    for relation in relations:
        mapping = context_maps.get(relation.related_type)
        if mapping is None:
            continue
        try:
            value = mapping.get(int(relation.related_id))
        except (TypeError, ValueError):
            continue
        if value:
            accessions.add(value)
    if not accessions:
        for dataset_id in dataset_ids:
            accessions.update(dataset_accessions.get(dataset_id, ()))
    return sorted(accessions)
