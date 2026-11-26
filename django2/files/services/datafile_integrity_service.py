import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from files.models import DataFile
from files.services.datafile_access_service import resolve_protected_datafile_path


@dataclass(frozen=True)
class DataFileIntegrityResult:
    available: bool
    status: str
    reason: str


def verify_and_mark_datafile_available(*, data_file: DataFile, roots=None) -> DataFileIntegrityResult:
    """Verify protected location, size, and SHA-256 before marking a file available."""
    if data_file.pk is None:
        raise ValueError("A persisted DataFile is required.")

    with transaction.atomic():
        locked = DataFile.objects.select_for_update().get(pk=data_file.pk)
        location = resolve_protected_datafile_path(locked, roots=roots)
        if not location.allowed:
            status = (
                DataFile.AVAILABILITY_MISSING
                if location.reason in {"file_missing", "file_path_missing", "not_a_file"}
                else DataFile.AVAILABILITY_BLOCKED
            )
            return _set_result(locked, status=status, reason=location.reason)

        expected_digest = (locked.sha256 or "").strip().lower()
        if locked.file_size is None or locked.file_size < 0:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_BLOCKED,
                reason="file_size_missing",
            )
        if re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_BLOCKED,
                reason="sha256_missing_or_invalid",
            )

        path = Path(location.resolved_path)
        try:
            actual_size = path.stat().st_size
        except OSError:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_MISSING,
                reason="file_became_unreadable",
            )
        if actual_size != locked.file_size:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_QUARANTINED,
                reason="file_size_mismatch",
            )
        try:
            actual_digest = _sha256_file(path)
        except OSError:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_MISSING,
                reason="file_became_unreadable",
            )
        if actual_digest != expected_digest:
            return _set_result(
                locked,
                status=DataFile.AVAILABILITY_QUARANTINED,
                reason="sha256_mismatch",
            )
        return _set_result(
            locked,
            status=DataFile.AVAILABILITY_AVAILABLE,
            reason="integrity_verified",
        )


def mark_datafile_unavailable(*, data_file: DataFile, status: str) -> DataFileIntegrityResult:
    allowed = {
        DataFile.AVAILABILITY_QUARANTINED,
        DataFile.AVAILABILITY_BLOCKED,
        DataFile.AVAILABILITY_MISSING,
    }
    if status not in allowed:
        raise ValueError("This operation can only set a fail-closed availability status.")
    if data_file.pk is None:
        raise ValueError("A persisted DataFile is required.")
    with transaction.atomic():
        locked = DataFile.objects.select_for_update().get(pk=data_file.pk)
        return _set_result(locked, status=status, reason="explicitly_marked_unavailable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_result(data_file: DataFile, *, status: str, reason: str) -> DataFileIntegrityResult:
    if data_file.availability_status != status:
        data_file.availability_status = status
        data_file.save(update_fields=["availability_status", "updated_at"])
    return DataFileIntegrityResult(
        available=status == DataFile.AVAILABILITY_AVAILABLE,
        status=status,
        reason=reason,
    )
