"""Durable archive jobs built exclusively from immutable batch snapshots."""

import csv
import gzip
import hashlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import tarfile
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import http_date

from files.models import ExternalFileArchive
from files.services.datafile_access_service import (
    ACTION_ARCHIVE,
    ACTION_ARCHIVE_DOWNLOAD,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)
from files.services.external_file_batch_service import batch_payload, snapshot_is_stale
from files.services.protected_asset_service import content_disposition


logger = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024


class ArchiveRequestError(ValueError):
    def __init__(self, code, detail, *, status_code=400):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class ArchiveBuildError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def queue_archive(batch, *, principal, payload, idempotency_key=None):
    if not isinstance(payload, dict):
        raise ArchiveRequestError("invalid_request", "The request body must be a JSON object.")
    unknown = set(payload) - {"format"}
    if unknown:
        raise ArchiveRequestError("invalid_request", f"Unsupported request fields: {sorted(unknown)}.")
    archive_format = str(payload.get("format") or ExternalFileArchive.FORMAT_ZIP).strip().lower()
    allowed_formats = {item[0] for item in ExternalFileArchive.FORMAT_CHOICES}
    if archive_format not in allowed_formats:
        raise ArchiveRequestError("invalid_archive_format", "format must be zip or tar.gz.")
    if batch.created_by_token_id != principal.pk:
        raise ArchiveRequestError("not_found", "Not found.", status_code=404)
    if batch.expires_at <= timezone.now():
        raise ArchiveRequestError("batch_expired", "The source batch has expired.", status_code=410)
    if snapshot_is_stale(batch):
        raise ArchiveRequestError(
            "snapshot_stale",
            "A source file no longer matches the immutable batch snapshot.",
            status_code=409,
        )
    max_input_bytes = getattr(settings, "GENEDATA_ARCHIVE_MAX_INPUT_BYTES", 500 * 1024 ** 3)
    if batch.total_size > max_input_bytes:
        raise ArchiveRequestError(
            "archive_input_too_large",
            f"Archive input exceeds the configured {max_input_bytes}-byte limit.",
            status_code=413,
        )

    request_value = {
        "batch_id": batch.batch_id,
        "snapshot_sha256": batch.snapshot_sha256,
        "format": archive_format,
    }
    request_fingerprint = _digest_json(request_value)
    idempotency_hash = None
    if idempotency_key is not None:
        key = str(idempotency_key).strip()
        if not key or len(key) > 255:
            raise ArchiveRequestError(
                "invalid_idempotency_key",
                "Idempotency-Key must contain 1 to 255 characters.",
            )
        idempotency_hash = hashlib.sha256(f"{principal.pk}:{key}".encode()).hexdigest()
        existing = ExternalFileArchive.objects.filter(idempotency_hash=idempotency_hash).first()
        if existing:
            if existing.request_fingerprint != request_fingerprint:
                raise ArchiveRequestError(
                    "idempotency_conflict",
                    "This Idempotency-Key was already used with a different archive request.",
                    status_code=409,
                )
            return existing, False

    archive_id = _new_archive_id()
    archive_name = f"{batch.batch_id}.{archive_format}"
    expires_at = timezone.now() + timedelta(
        hours=getattr(settings, "GENEDATA_ARCHIVE_TTL_HOURS", 24)
    )
    try:
        with transaction.atomic():
            type(principal).objects.select_for_update().get(pk=principal.pk)
            type(batch).objects.select_for_update().get(pk=batch.pk)
            active_statuses = [
                ExternalFileArchive.STATUS_QUEUED,
                ExternalFileArchive.STATUS_RUNNING,
            ]
            token_active = ExternalFileArchive.objects.filter(
                created_by_token=principal,
                status__in=active_statuses,
            ).count()
            batch_active = ExternalFileArchive.objects.filter(
                batch=batch,
                status__in=active_statuses,
            ).count()
            if token_active >= getattr(settings, "GENEDATA_ARCHIVE_MAX_ACTIVE_PER_TOKEN", 3):
                raise ArchiveRequestError(
                    "archive_queue_limit",
                    "The token already has the maximum number of active archive jobs.",
                    status_code=429,
                )
            if batch_active >= getattr(settings, "GENEDATA_ARCHIVE_MAX_ACTIVE_PER_BATCH", 2):
                raise ArchiveRequestError(
                    "archive_queue_limit",
                    "The batch already has the maximum number of active archive jobs.",
                    status_code=429,
                )
            archive = ExternalFileArchive.objects.create(
                archive_id=archive_id,
                batch=batch,
                created_by_token=principal,
                token_prefix_snapshot=principal.token_prefix,
                archive_format=archive_format,
                status=ExternalFileArchive.STATUS_QUEUED,
                request_fingerprint=request_fingerprint,
                idempotency_hash=idempotency_hash,
                archive_name=archive_name,
                file_count=batch.file_count,
                total_input_size=batch.total_size,
                expires_at=expires_at,
            )
    except IntegrityError:
        if idempotency_hash:
            existing = ExternalFileArchive.objects.filter(idempotency_hash=idempotency_hash).first()
            if existing and existing.request_fingerprint == request_fingerprint:
                return existing, False
        raise
    return archive, True


def archive_payload(archive):
    effective_status = archive.status
    if archive.expires_at <= timezone.now():
        effective_status = ExternalFileArchive.STATUS_EXPIRED
    payload = {
        "archive_id": archive.archive_id,
        "batch_id": archive.batch.batch_id,
        "format": archive.archive_format,
        "status": effective_status,
        "file_count": archive.file_count,
        "total_input_size": archive.total_input_size,
        "archive_size": archive.archive_size,
        "archive_sha256": archive.archive_sha256 or None,
        "attempt_count": archive.attempt_count,
        "queued_at": archive.queued_at.isoformat(),
        "started_at": archive.started_at.isoformat() if archive.started_at else None,
        "completed_at": archive.completed_at.isoformat() if archive.completed_at else None,
        "expires_at": archive.expires_at.isoformat(),
        "status_url": f"/gd/api/v1/file-archives/{archive.archive_id}/",
        "download_url": None,
        "error": None,
    }
    if effective_status == ExternalFileArchive.STATUS_READY:
        payload["download_url"] = f"/gd/api/v1/file-archives/{archive.archive_id}/content/"
    if effective_status == ExternalFileArchive.STATUS_FAILED:
        payload["error"] = {
            "code": archive.error_code or "archive_build_failed",
            "detail": archive.error_detail or "Archive generation failed.",
        }
    return payload


def archive_sources_authorized(archive, *, principal, action=ACTION_ARCHIVE_DOWNLOAD):
    if principal is None or not principal.is_active:
        return False
    for item in archive.batch.items.select_related("data_file"):
        decision = resolve_datafile_access(
            item.data_file,
            principal=principal,
            action=action,
        )
        if not decision.allowed:
            return False
    return True


def claim_next_archive():
    with transaction.atomic():
        archive = (
            ExternalFileArchive.objects.select_for_update()
            .filter(status=ExternalFileArchive.STATUS_QUEUED)
            .order_by("queued_at", "id")
            .first()
        )
        if archive is None:
            return None
        archive.status = ExternalFileArchive.STATUS_RUNNING
        archive.started_at = timezone.now()
        archive.attempt_count += 1
        archive.error_code = ""
        archive.error_detail = ""
        archive.save(update_fields=[
            "status", "started_at", "attempt_count", "error_code", "error_detail", "updated_at",
        ])
        return archive.archive_id


def process_archive(archive_id):
    archive = (
        ExternalFileArchive.objects.select_related("batch")
        .prefetch_related("batch__items__data_file")
        .get(archive_id=archive_id)
    )
    if archive.status != ExternalFileArchive.STATUS_RUNNING:
        raise ArchiveBuildError("invalid_job_state", "Archive job is not running.")

    temporary_path = None
    try:
        if archive.expires_at <= timezone.now():
            raise ArchiveBuildError("archive_expired", "Archive job expired before it was processed.")
        if archive.batch.expires_at <= timezone.now():
            raise ArchiveBuildError("batch_expired", "The source batch expired before the job was processed.")
        if not archive_sources_authorized(
            archive,
            principal=archive.created_by_token,
            action=ACTION_ARCHIVE,
        ):
            raise ArchiveBuildError(
                "archive_access_revoked",
                "Archive access was revoked before the job was processed.",
            )
        if snapshot_is_stale(archive.batch):
            raise ArchiveBuildError(
                "snapshot_stale",
                "A source file no longer matches the immutable batch snapshot.",
            )
        root = archive_root(create=True)
        required_free = archive.total_input_size + getattr(
            settings, "GENEDATA_ARCHIVE_MIN_FREE_BYTES", 10 * 1024 ** 3
        )
        if shutil.disk_usage(root).free < required_free:
            raise ArchiveBuildError(
                "insufficient_archive_storage",
                "Archive storage does not have enough free space.",
            )

        destination_directory = root / archive.archive_id
        destination_directory.mkdir(mode=0o750, parents=False, exist_ok=True)
        final_path = destination_directory / archive.archive_name
        with tempfile.NamedTemporaryFile(
            dir=root,
            prefix=f".{archive.archive_id}-",
            suffix=".partial",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

        if archive.archive_format == ExternalFileArchive.FORMAT_ZIP:
            _build_zip(archive, temporary_path)
        elif archive.archive_format == ExternalFileArchive.FORMAT_TAR_GZ:
            _build_tar_gz(archive, temporary_path)
        else:
            raise ArchiveBuildError("invalid_archive_format", "Archive format is unsupported.")

        archive_sha256 = _sha256_file(temporary_path)
        archive_size = temporary_path.stat().st_size
        os.replace(str(temporary_path), str(final_path))
        temporary_path = None
        relative_path = final_path.relative_to(root).as_posix()
        now = timezone.now()
        ExternalFileArchive.objects.filter(pk=archive.pk).update(
            status=ExternalFileArchive.STATUS_READY,
            output_relative_path=relative_path,
            archive_size=archive_size,
            archive_sha256=archive_sha256,
            completed_at=now,
            error_code="",
            error_detail="",
            updated_at=now,
        )
    except ArchiveBuildError as exc:
        _mark_failed(archive, exc.code, exc.detail)
    except Exception:
        logger.exception("Unexpected external archive build failure: %s", archive.archive_id)
        _mark_failed(archive, "archive_build_failed", "Archive generation failed.")
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove partial archive for %s", archive.archive_id)
    return ExternalFileArchive.objects.get(pk=archive.pk)


def recover_stale_jobs(*, stale_minutes=60):
    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    max_attempts = getattr(settings, "GENEDATA_ARCHIVE_WORKER_MAX_ATTEMPTS", 2)
    recoverable = ExternalFileArchive.objects.filter(
        status=ExternalFileArchive.STATUS_RUNNING,
        updated_at__lt=cutoff,
        attempt_count__lt=max_attempts,
    ).update(
        status=ExternalFileArchive.STATUS_QUEUED,
        started_at=None,
        error_code="worker_interrupted",
        error_detail="The prior worker stopped; the job was queued again.",
        updated_at=timezone.now(),
    )
    failed = ExternalFileArchive.objects.filter(
        status=ExternalFileArchive.STATUS_RUNNING,
        updated_at__lt=cutoff,
        attempt_count__gte=max_attempts,
    ).update(
        status=ExternalFileArchive.STATUS_FAILED,
        error_code="worker_attempts_exhausted",
        error_detail="Archive worker retry limit was reached.",
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )
    return recoverable, failed


def cleanup_expired_archives(*, now=None):
    now = now or timezone.now()
    archives = list(
        ExternalFileArchive.objects.filter(
            expires_at__lte=now,
            status__in=[
                ExternalFileArchive.STATUS_QUEUED,
                ExternalFileArchive.STATUS_READY,
                ExternalFileArchive.STATUS_FAILED,
            ],
        )
    )
    removed = 0
    for archive in archives:
        location = resolve_archive_path(archive)
        if location is not None:
            try:
                location.unlink()
                removed += 1
            except OSError:
                logger.exception("Could not remove expired archive: %s", archive.archive_id)
                continue
        directory = archive_root(create=False) / archive.archive_id
        try:
            directory.rmdir()
        except OSError:
            pass
        archive.status = ExternalFileArchive.STATUS_EXPIRED
        archive.output_relative_path = ""
        archive.save(update_fields=["status", "output_relative_path", "updated_at"])
    return len(archives), removed


def resolve_archive_path(archive):
    if not archive.output_relative_path:
        return None
    try:
        root = archive_root(create=False).resolve(strict=True)
        candidate = (root / archive.output_relative_path).resolve(strict=True)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def build_archive_response(archive):
    path = resolve_archive_path(archive)
    if path is None:
        return None
    root = archive_root(create=False).resolve(strict=True)
    relative_path = path.relative_to(root).as_posix()
    internal_prefix = str(
        getattr(settings, "GENEDATA_EXTERNAL_ARCHIVE_INTERNAL_URI", "")
    ).strip()
    if not internal_prefix.startswith("/"):
        return None
    stat = path.stat()
    content_type = (
        "application/zip"
        if archive.archive_format == ExternalFileArchive.FORMAT_ZIP
        else "application/gzip"
    )
    response = HttpResponse(status=200, content_type=content_type)
    response["X-Accel-Redirect"] = (
        f"{internal_prefix.rstrip('/')}/{quote(relative_path, safe='/')}"
    )
    response["Content-Disposition"] = content_disposition(archive.archive_name, "attachment")
    response["Content-Length"] = str(stat.st_size)
    response["Last-Modified"] = http_date(stat.st_mtime)
    response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    response["ETag"] = f'"sha256-{archive.archive_sha256}"'
    response["X-Archive-SHA256"] = archive.archive_sha256
    return response


def archive_root(*, create):
    root = Path(getattr(settings, "GENEDATA_EXTERNAL_ARCHIVE_ROOT"))
    if create:
        root.mkdir(mode=0o750, parents=True, exist_ok=True)
    return root


def _build_zip(archive, output_path):
    manifest_json, manifest_tsv = _manifest_bytes(archive)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as target:
        _zip_bytes(target, "manifest.json", manifest_json)
        _zip_bytes(target, "manifest.tsv", manifest_tsv)
        for item in archive.batch.items.all():
            source = _verified_source(item)
            info = _zip_info(_member_name(item))
            digest = hashlib.sha256()
            with source.open("rb") as reader, target.open(info, mode="w", force_zip64=True) as writer:
                _copy_and_hash(reader, writer, digest)
            if digest.hexdigest() != item.sha256:
                raise ArchiveBuildError("source_checksum_mismatch", "A source file checksum changed during archiving.")


def _build_tar_gz(archive, output_path):
    manifest_json, manifest_tsv = _manifest_bytes(archive)
    with output_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                _tar_bytes(target, "manifest.json", manifest_json)
                _tar_bytes(target, "manifest.tsv", manifest_tsv)
                for item in archive.batch.items.all():
                    source = _verified_source(item)
                    info = tarfile.TarInfo(_member_name(item))
                    info.size = item.size
                    info.mode = 0o640
                    info.mtime = int(archive.batch.created_at.timestamp())
                    with source.open("rb") as reader:
                        hashing_reader = _HashingReader(reader)
                        target.addfile(info, hashing_reader)
                    if hashing_reader.hexdigest() != item.sha256:
                        raise ArchiveBuildError("source_checksum_mismatch", "A source file checksum changed during archiving.")


def _verified_source(item):
    location = resolve_protected_datafile_path(item.data_file)
    if not location.allowed:
        raise ArchiveBuildError("source_unavailable", "A source file is unavailable.")
    source = Path(location.resolved_path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ArchiveBuildError("source_unavailable", "A source file is unavailable.") from exc
    if size != item.size or item.data_file.content_version != item.content_version:
        raise ArchiveBuildError("snapshot_stale", "A source file no longer matches the immutable batch snapshot.")
    return source


def _manifest_bytes(archive):
    payload = batch_payload(archive.batch)
    payload["archive_id"] = archive.archive_id
    payload["archive_format"] = archive.archive_format
    json_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    output = io.StringIO(newline="")
    writer = csv.writer(output, dialect="excel-tab", lineterminator="\n")
    writer.writerow([
        "position", "file_code", "file_name", "role", "format", "accession",
        "assembly", "dataset", "size", "sha256", "content_version", "url",
    ])
    for item in archive.batch.items.all():
        writer.writerow([
            item.position, item.file_code, item.file_name, item.role, item.file_format,
            item.accession, item.assembly, item.dataset, item.size, item.sha256,
            item.content_version, item.content_url,
        ])
    return json_bytes, output.getvalue().encode("utf-8")


def _member_name(item):
    safe_code = re.sub(r"[^A-Za-z0-9._-]", "_", item.file_code) or "file"
    safe_name = re.sub(
        r"[\\/\x00-\x1f\x7f]",
        "_",
        os.path.basename(item.file_name),
    ).strip()
    if safe_name in {"", ".", ".."}:
        safe_name = "datafile"
    return f"files/{item.position:04d}-{safe_code}/{safe_name}"


def _zip_info(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o640 << 16
    return info


def _zip_bytes(target, name, value):
    target.writestr(_zip_info(name), value)


def _tar_bytes(target, name, value):
    info = tarfile.TarInfo(name)
    info.size = len(value)
    info.mode = 0o640
    info.mtime = 0
    target.addfile(info, io.BytesIO(value))


def _copy_and_hash(reader, writer, digest):
    while True:
        chunk = reader.read(CHUNK_SIZE)
        if not chunk:
            return
        digest.update(chunk)
        writer.write(chunk)


class _HashingReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        chunk = self.source.read(size)
        self.digest.update(chunk)
        return chunk

    def hexdigest(self):
        return self.digest.hexdigest()


def _mark_failed(archive, code, detail):
    now = timezone.now()
    ExternalFileArchive.objects.filter(pk=archive.pk).update(
        status=ExternalFileArchive.STATUS_FAILED,
        error_code=code,
        error_detail=str(detail)[:500],
        completed_at=now,
        updated_at=now,
    )


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _digest_json(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _new_archive_id():
    return f"ARCH-{timezone.now():%Y%m%d}-{secrets.token_hex(8).upper()}"
