"""Read-only query helpers for the unified Accession workbench."""

from collections import defaultdict

from django.db.models import Q

from files.models import Accession, DataFile, DatasetAccession, FileRelation


def _display_size(value):
    size = int(value or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}" if index else f"{size} B"


def _paginate(items, page, page_size):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    total = len(items)
    start = (page - 1) * page_size
    return {
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        "results": items[start:start + page_size],
    }


def get_accession_or_none(accession_code):
    return (
        Accession.objects.select_related("species")
        .filter(accession=accession_code)
        .first()
    )


def _related_file_queryset(accession):
    assembly_ids = list(accession.assemblies.values_list("id", flat=True))
    annotation_ids = list(
        accession.assemblies.values_list("annotations__id", flat=True)
    )
    relation_filter = Q(related_type="accession", related_id=str(accession.id))
    if assembly_ids:
        relation_filter |= Q(related_type="assembly", related_id__in=[str(item) for item in assembly_ids])
    if annotation_ids:
        relation_filter |= Q(related_type="annotation", related_id__in=[str(item) for item in annotation_ids if item])

    file_ids = FileRelation.objects.filter(relation_filter).values_list("file_id", flat=True)
    return DataFile.objects.filter(id__in=file_ids).select_related("dataset", "file_type").distinct()


def _file_rows(accession):
    files = list(_related_file_queryset(accession).order_by("file_name", "id"))
    relations = FileRelation.objects.filter(file__in=files).order_by("file_id", "id")
    relation_map = defaultdict(list)
    for relation in relations:
        relation_map[relation.file_id].append({
            "related_type": relation.related_type,
            "related_id": relation.related_id,
            "related_code": relation.related_code,
            "file_role": relation.file_role,
            "is_primary": relation.is_primary,
        })

    rows = []
    for file_obj in files:
        file_relations = relation_map[file_obj.id]
        first_relation = file_relations[0] if file_relations else {}
        rows.append({
            "id": file_obj.id,
            "file_code": file_obj.file_code,
            "file_name": file_obj.file_name,
            "file_path": file_obj.file_path,
            "file_size": file_obj.file_size,
            "size_display": _display_size(file_obj.file_size),
            "md5": file_obj.md5,
            "file_type": file_obj.file_type.name if file_obj.file_type else "-",
            "dataset_id": file_obj.dataset_id,
            "dataset_code": file_obj.dataset.dataset_code if file_obj.dataset else None,
            "file_role": first_relation.get("file_role") or "-",
            "related_type": first_relation.get("related_type") or "-",
            "related_id": first_relation.get("related_id") or "-",
            "related_code": first_relation.get("related_code") or "-",
            "relations": file_relations,
            "source": "new_relation",
            "datafile_download_url": f"/gd/api/files/data-files/{file_obj.id}/download/",
        })
    return rows


def _assembly_rows(accession):
    rows = []
    for assembly in accession.assemblies.all().order_by("-is_default", "name", "id"):
        rows.append({
            "id": assembly.id,
            "name": assembly.name,
            "assembly_code": assembly.assembly_code,
            "assembly_name": assembly.assembly_name or assembly.display_name or assembly.name,
            "assembly_accession": assembly.assembly_accession or assembly.standard_id,
            "assembly_level": assembly.assembly_level,
            "display_name": assembly.display_name,
            "standard_id": assembly.standard_id,
            "bio_project": assembly.bio_project,
            "reference": assembly.reference,
            "source_database": assembly.source_database,
            "external_project": assembly.external_project,
            "file_name": assembly.file_name,
            "file_type": assembly.file_type,
            "description": assembly.description,
            "is_default": assembly.is_default,
        })
    return rows


def _annotation_rows(accession):
    rows = []
    for assembly in accession.assemblies.all().order_by("-is_default", "name", "id"):
        for annotation in assembly.annotations.all().order_by("-is_default", "name", "id"):
            rows.append({
                "id": annotation.id,
                "name": annotation.name,
                "annotation_code": annotation.annotation_code,
                "annotation_name": annotation.annotation_name or annotation.display_name or annotation.name,
                "annotation_version": annotation.annotation_version or annotation.release_version,
                "display_name": annotation.display_name,
                "standard_id": annotation.standard_id,
                "source_name": annotation.source_name,
                "release_version": annotation.release_version,
                "source_database": annotation.source_database,
                "external_project": annotation.external_project,
                "file_name": annotation.file_name,
                "file_type": annotation.file_type,
                "description": annotation.description,
                "is_default": annotation.is_default,
                "assembly_id": assembly.id,
                "assembly_name": assembly.display_name or assembly.name,
            })
    return rows


def _accession_dataset_links(accession):
    """Return explicit DatasetAccession links, supplemented by file-owned datasets."""
    rows = {}
    links = (
        DatasetAccession.objects.filter(accession=accession)
        .select_related("dataset")
        .order_by("dataset__dataset_code", "id")
    )
    for link in links:
        rows[link.dataset_id] = {
            "dataset": link.dataset,
            "relation_role": link.relation_role,
            "relation_source": link.source or "-",
        }

    # Preserve pre-existing Dataset assignments on files while manifests are
    # progressively migrated to the explicit DatasetAccession relationship.
    for file_obj in _related_file_queryset(accession):
        if file_obj.dataset_id:
            rows.setdefault(file_obj.dataset_id, {
                "dataset": file_obj.dataset,
                "relation_role": "-",
                "relation_source": "DataFile.dataset",
            })
    return sorted(rows.values(), key=lambda item: item["dataset"].dataset_code)


def get_accession_summary(accession):
    files = _file_rows(accession)
    assemblies = _assembly_rows(accession)
    annotations = _annotation_rows(accession)
    datasets = _accession_dataset_links(accession)
    mappings = list(accession.external_mappings.all())
    roles = {item["file_role"].lower() for item in files}

    def has_role(*keywords):
        return any(any(keyword in role for keyword in keywords) for role in roles)

    species = accession.species
    return {
        "accession": {
            "id": accession.id,
            "accession": accession.accession,
            "genetic_stock_id": accession.genetic_stock_id,
            "sub_population": accession.sub_population,
            "country": accession.country,
            "region": accession.region,
            "longitude": accession.longitude,
            "latitude": accession.latitude,
            "description": accession.description,
            "external_link": accession.seq_data,
            "species": {
                "id": species.id,
                "species_code": species.species_code,
                "scientific_name": species.scientific_name,
                "chinese_name": species.chinese_name,
                "common_name": species.common_name,
            } if species else None,
        },
        "summary": {
            "sample_count": accession.samples.count(),
            "dataset_count": len(datasets),
            "assembly_count": len(assemblies),
            "annotation_count": len(annotations),
            "file_count": len(files),
            "total_size": sum(item["file_size"] or 0 for item in files),
            "total_size_display": _display_size(sum(item["file_size"] or 0 for item in files)),
        },
        "external_identifiers": {
            "ena_studies": sorted({item.external_study_accession for item in mappings if item.external_study_accession}),
            "biosample_count": len({item.biosample_accession for item in mappings if item.biosample_accession}),
            "experiment_count": len({item.experiment_accession for item in mappings if item.experiment_accession}),
            "run_count": len({item.run_accession for item in mappings if item.run_accession}),
        },
        "geography": {
            "latitude": accession.latitude,
            "longitude": accession.longitude,
            "has_point": accession.latitude is not None and accession.longitude is not None,
        },
        "relationship_overview": {
            "assemblies": assemblies,
            "annotations": annotations,
        },
        "data_status": {
            "genome": "ready" if has_role("genome", "fasta") else "unavailable",
            "annotation": "ready" if has_role("annotation", "gff", "gtf") else "unavailable",
            "transcriptome": "ready" if has_role("transcriptome", "rna", "expression") else "unavailable",
        },
    }


def get_accession_datasets(accession, page=1, page_size=20):
    mappings = list(accession.external_mappings.all())
    external_databases = sorted({item.external_database for item in mappings if item.external_database})
    run_count = len({item.run_accession for item in mappings if item.run_accession})
    rows = []
    for link in _accession_dataset_links(accession):
        dataset = link["dataset"]
        rows.append({
            "id": dataset.id,
            "dataset_code": dataset.dataset_code,
            "dataset_name": dataset.dataset_name,
            "dataset_type": dataset.dataset_type,
            "bioproject_accession": dataset.bioproject_accession,
            "version": dataset.version,
            "status": dataset.status,
            "external_database": ", ".join(external_databases) or "-",
            "run_count": run_count,
            "relation_role": link["relation_role"],
            "relation_source": link["relation_source"],
        })
    return _paginate(rows, page, page_size)


def get_accession_samples(accession, page=1, page_size=20):
    rows = [{
        "id": sample.id,
        "sample_name": sample.sample_name or "-",
        "sample_code": sample.sample_code,
        "biosample_accession": sample.biosample_accession or "-",
        "experiment_accession": sample.experiment_accession or "-",
        "tissue": sample.tissue or "-",
        "data_type": sample.data_type or "-",
        "treatment": sample.treatment or "-",
    } for sample in accession.samples.all().order_by("sample_name", "sample_code")]
    return _paginate(rows, page, page_size)


def get_accession_assemblies(accession, page=1, page_size=20):
    return _paginate(_assembly_rows(accession), page, page_size)


def get_accession_annotations(accession, page=1, page_size=20):
    return _paginate(_annotation_rows(accession), page, page_size)


def get_accession_files(accession, page=1, page_size=20):
    return _paginate(_file_rows(accession), page, page_size)
