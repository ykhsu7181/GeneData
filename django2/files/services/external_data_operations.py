"""Operational readiness checks for external DataFile access."""

from dataclasses import dataclass
from pathlib import Path

from files.models import DataFile, FileRelation
from files.services.datafile_access_service import (
    resolve_datafile_access_level,
    resolve_protected_datafile_path,
)


GENOME_FASTA_ROLES = ("genome", "genome_fasta")
FASTA_INDEX_ROLES = ("genome_index", "fai")


@dataclass(frozen=True)
class DataFileReadiness:
    ready: bool
    issues: tuple
    effective_access_level: str
    policy_reason: str
    path_reason: str
    fasta_index_status: str


def inspect_datafile_readiness(data_file, *, access_level=None, require_checksum=True, roots=None):
    """Return deterministic publication readiness without mutating database state."""
    issues = []
    if not data_file.is_current:
        issues.append("file_not_current")

    location = resolve_protected_datafile_path(data_file, roots=roots)
    if not location.allowed:
        issues.append(location.reason)

    if require_checksum and data_file.content_version is None:
        issues.append("file_checksum_unverified")

    effective_level, policy_reason = resolve_datafile_access_level(
        data_file,
        access_level=access_level,
    )
    if effective_level == DataFile.ACCESS_LEVEL_PRIVATE:
        issues.append(policy_reason)

    fasta_index_status = inspect_fasta_index_status(data_file)
    if fasta_index_status != "not_required" and fasta_index_status != "ready":
        issues.append(f"fasta_index_{fasta_index_status}")

    return DataFileReadiness(
        ready=not issues,
        issues=tuple(dict.fromkeys(issues)),
        effective_access_level=effective_level,
        policy_reason=policy_reason,
        path_reason=location.reason,
        fasta_index_status=fasta_index_status,
    )


def inspect_fasta_index_status(data_file):
    """Classify each genome FASTA relation; all contexts need a fresh registered FAI."""
    relations = list(
        data_file.relations.filter(file_role__in=GENOME_FASTA_ROLES).order_by("id")
    )
    if not relations:
        return "not_required"
    if not data_file.file_path:
        return "missing"
    try:
        fasta_path = Path(data_file.file_path)
        if not fasta_path.is_file():
            return "missing"
        fasta_mtime = fasta_path.stat().st_mtime_ns
    except OSError:
        return "missing"
    saw_missing = False
    saw_stale = False
    expected_name = f"{data_file.file_name}.fai"
    expected_basename = f"{Path(data_file.file_path).name}.fai"

    for relation in relations:
        candidates = FileRelation.objects.select_related("file").filter(
            related_type=relation.related_type,
            related_id=str(relation.related_id),
            file__is_current=True,
            file_role__in=FASTA_INDEX_ROLES,
        ).exclude(file_id=data_file.id)
        matching = [
            item.file
            for item in candidates
            if item.file.file_path.lower().endswith(".fai")
            and item.file.file_name in {expected_name, expected_basename}
        ]
        if not matching:
            saw_missing = True
            continue
        context_ready = False
        for index_file in matching:
            index_path = Path(index_file.file_path)
            try:
                index_exists = index_path.is_file()
                index_mtime = index_path.stat().st_mtime_ns if index_exists else None
            except OSError:
                index_exists = False
                index_mtime = None
            if not index_exists:
                saw_missing = True
                continue
            if index_mtime < fasta_mtime:
                saw_stale = True
                continue
            context_ready = True
            break
        if not context_ready and not saw_missing:
            saw_stale = True

    if saw_missing:
        return "missing"
    if saw_stale:
        return "stale"
    return "ready"
