"""Read-only inventory of what External Data API v1 can expose."""

from collections import Counter

from django.db.models import Q

from files.models import Accession, Assembly, DataAccessToken, DataFile, Dataset, FileRelation
from files.services.assembly_visibility import public_assembly_list_queryset
from files.services.datafile_access_service import (
    ACTION_CONTENT,
    ACTION_METADATA,
    resolve_datafile_access,
    resolve_datafile_access_level,
    resolve_protected_datafile_path,
)
from files.services.external_dataset_manifest_service import build_dataset_manifest
from files.services.external_sequence_service import inspect_public_fasta_index


def build_external_api_readiness_report():
    principal = DataAccessToken(
        name="readiness-audit",
        scopes=sorted(DataAccessToken.ALLOWED_SCOPES),
        access_tier=DataAccessToken.ACCESS_TIER_PUBLIC,
    )
    files = list(
        DataFile.objects.select_related("dataset", "file_type")
        .prefetch_related("relations")
        .order_by("file_code", "id")
    )
    file_rows = [_file_row(data_file, principal) for data_file in files]
    file_statuses = {row["file_code"]: row["status"] for row in file_rows}

    datasets = list(Dataset.objects.order_by("dataset_code", "id"))
    dataset_rows = [
        _dataset_row(dataset, principal, file_statuses) for dataset in datasets
    ]
    assemblies = list(
        Assembly.objects.select_related("accession").order_by("assembly_code", "id")
    )
    assembly_rows = [_assembly_row(assembly) for assembly in assemblies]
    accession_rows = [_accession_row(accession) for accession in Accession.objects.order_by("accession", "id")]

    summary_rows = []
    for object_type, rows in (
        ("accession", accession_rows),
        ("assembly", assembly_rows),
        ("dataset", dataset_rows),
        ("file", file_rows),
    ):
        counts = Counter(row["status"] for row in rows)
        summary_rows.append({"object_type": object_type, "status": "TOTAL", "count": len(rows)})
        summary_rows.extend(
            {"object_type": object_type, "status": status, "count": count}
            for status, count in sorted(counts.items())
        )
    return {
        "summary": summary_rows,
        "accessions": accession_rows,
        "assemblies": assembly_rows,
        "datasets": dataset_rows,
        "files": file_rows,
    }


def _file_row(data_file, principal):
    relations = list(data_file.relations.all())
    level, policy_reason = resolve_datafile_access_level(data_file)
    metadata = resolve_datafile_access(data_file, principal=None, action=ACTION_METADATA)
    content = resolve_datafile_access(data_file, principal=principal, action=ACTION_CONTENT)
    location = resolve_protected_datafile_path(data_file)
    issues = []
    if (
        not data_file.is_current
        or data_file.publication_status != DataFile.PUBLICATION_RELEASED
        or data_file.published_at is None
        or data_file.content_version is None
    ):
        status = "NOT_RELEASED"
        issues.append(metadata.reason)
    elif level != DataFile.ACCESS_LEVEL_PUBLIC:
        status = "INTERNAL_ONLY"
        issues.append(policy_reason)
    elif not relations:
        status = "MISSING_RELATION"
        issues.append("no_file_relation")
    elif not location.allowed:
        status = "MISSING_FILE"
        issues.append(location.reason)
    else:
        status = "READY"
    return {
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "status": status,
        "issues": ",".join(filter(None, issues)),
        "publication_status": data_file.publication_status,
        "configured_access_level": data_file.access_level,
        "effective_access_level": level,
        "is_current": _bool(data_file.is_current),
        "relation_count": len(relations),
        "roles": ",".join(sorted({item.file_role for item in relations})),
        "anonymous_metadata": _bool(metadata.allowed and location.allowed),
        "token_download": _bool(content.allowed and location.allowed),
        "sha256": (data_file.sha256 or "").lower(),
        "content_version": data_file.content_version or "",
    }


def _dataset_row(dataset, principal, file_statuses):
    relation_ids = []
    for value in FileRelation.objects.filter(
        related_type="dataset", related_id=str(dataset.id)
    ).values_list("file_id", flat=True):
        relation_ids.append(value)
    linked_files = list(
        DataFile.objects.filter(Q(dataset=dataset) | Q(id__in=relation_ids))
        .distinct()
        .order_by("file_code", "id")
    )
    if dataset.visibility == "lab_internal":
        status, issues = "INTERNAL_ONLY", ["dataset_lab_internal"]
        manifest_count = 0
    elif dataset.visibility != "public" or dataset.status != "released":
        status, issues = "NOT_RELEASED", ["dataset_not_publicly_released"]
        manifest_count = 0
    elif not linked_files:
        status, issues = "MISSING_RELATION", ["dataset_has_no_files"]
        manifest_count = 0
    else:
        payload = build_dataset_manifest(dataset.dataset_code, [dataset], principal=principal)
        manifest_count = payload["count"]
        blocked = [
            item.file_code
            for item in linked_files
            if file_statuses.get(item.file_code) != "READY"
        ]
        if not manifest_count:
            status, issues = "MISSING_FILE", ["manifest_has_no_exposable_files"]
        elif blocked:
            status, issues = "PARTIAL", ["blocked_files=" + ",".join(blocked)]
        else:
            status, issues = "READY", []
    return {
        "dataset_code": dataset.dataset_code,
        "bioproject_accession": dataset.bioproject_accession or "",
        "status": status,
        "issues": ",".join(issues),
        "visibility": dataset.visibility,
        "dataset_status": dataset.status,
        "linked_file_count": len(linked_files),
        "manifest_file_count": manifest_count,
        "manifest_exposed": _bool(status in {"READY", "PARTIAL"}),
        "accessions": ",".join(
            dataset.accession_links.order_by("accession__accession")
            .values_list("accession__accession", flat=True)
        ),
    }


def _assembly_row(assembly):
    if not (assembly.assembly_code or "").strip():
        status = "AMBIGUOUS"
        result = {"status": "AMBIGUOUS", "detail": "assembly_code_missing"}
    else:
        result = inspect_public_fasta_index(assembly)
        if result["status"] == "PASS":
            status = "READY"
        elif "ambiguous" in result["detail"]:
            status = "AMBIGUOUS"
        else:
            status = result["status"]
    return {
        "accession": assembly.accession.accession,
        "assembly_code": assembly.assembly_code or "",
        "assembly_accession": assembly.assembly_accession or "",
        "status": status,
        "issues": result["detail"],
        "region_exposed": _bool(status == "READY"),
        "genome_file_id": result.get("genome_file_id", ""),
        "index_file_id": result.get("index_file_id", ""),
        "sequence_count": result.get("sequence_count", ""),
    }


def _accession_row(accession):
    assemblies = public_assembly_list_queryset(accession.assemblies.all())
    relation_filter = Q(related_type="accession", related_id=str(accession.id))
    assembly_ids = list(assemblies.values_list("id", flat=True))
    if assembly_ids:
        relation_filter |= Q(
            related_type="assembly",
            related_id__in=[str(value) for value in assembly_ids],
        )
    files = DataFile.objects.filter(relations__in=FileRelation.objects.filter(relation_filter)).distinct()
    return {
        "accession": accession.accession,
        "status": "READY",
        "anonymous_metadata": "yes",
        "public_assembly_count": assemblies.count(),
        "related_file_count": files.count(),
    }


def _bool(value):
    return "yes" if value else "no"
