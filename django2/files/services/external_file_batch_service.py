"""Resolve batch selectors and persist immutable DataFile manifest snapshots."""

import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from files.models import DataFile, ExternalFileBatch, ExternalFileBatchItem
from files.services.datafile_access_service import ACTION_BATCH
from files.services.external_file_catalog_service import (
    collect_external_files,
    normalize_file_name,
)


SELECTOR_KEYS = frozenset({
    "file_code", "file_name", "accession", "assembly", "dataset", "role", "format",
})


class BatchRequestError(ValueError):
    def __init__(self, code, detail, *, status_code=400, payload=None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.payload = payload or {}


def resolve_batch_request(payload, *, principal):
    normalized = normalize_batch_request(payload)
    selector_count = _selector_count(normalized)
    max_selectors = getattr(settings, "GENEDATA_BATCH_MAX_SELECTORS", 1000)
    if selector_count > max_selectors:
        raise BatchRequestError(
            "selector_limit_exceeded",
            f"At most {max_selectors} selectors are allowed.",
            status_code=413,
        )

    catalog = collect_external_files(principal=principal, action=ACTION_BATCH)
    resolved = []
    ambiguous = []
    missing = []
    seen = set()

    def include(items):
        for item in items:
            if item["file_code"] not in seen:
                seen.add(item["file_code"])
                resolved.append(item)

    for file_code in normalized["file_codes"]:
        matches = [item for item in catalog if item["file_code"] == file_code]
        if matches:
            include(matches)
        else:
            missing.append({"selector": {"file_code": file_code}, "code": "not_found"})

    for selector in normalized["selectors"]:
        matches = [item for item in catalog if _matches_selector(item, selector)]
        if len(matches) == 1:
            include(matches)
        elif len(matches) > 1:
            ambiguous.append({
                "selector": selector,
                "candidates": [_candidate(item) for item in matches],
            })
        else:
            missing.append({"selector": selector, "code": "not_found"})

    roles = normalized["roles"]
    for field, values in (
        ("accession", normalized["accessions"]),
        ("assembly", normalized["assemblies"]),
        ("dataset", normalized["datasets"]),
    ):
        for value in values:
            matches = [
                item for item in catalog
                if _matches_business_value(item, field, value)
                and (not roles or any(_equal(role, item_role) for role in roles for item_role in item["roles"]))
            ]
            if matches:
                include(matches)
            else:
                selector = {field: value}
                if roles:
                    selector["roles"] = roles
                missing.append({"selector": selector, "code": "not_found"})

    blocked = []
    max_files = getattr(settings, "GENEDATA_BATCH_MAX_FILES", 1000)
    max_bytes = getattr(settings, "GENEDATA_BATCH_MAX_BYTES", 500 * 1024 ** 3)
    total_size = sum(item["size"] for item in resolved)
    if len(resolved) > max_files:
        blocked.append({"code": "file_limit_exceeded", "limit": max_files, "actual": len(resolved)})
    if total_size > max_bytes:
        blocked.append({"code": "byte_limit_exceeded", "limit": max_bytes, "actual": total_size})

    return {
        "strict": normalized["strict"],
        "selector_count": selector_count,
        "resolved": [_public_item(item) for item in resolved],
        "ambiguous": ambiguous,
        "missing": missing,
        "blocked": blocked,
        "summary": {
            "resolved": len(resolved),
            "ambiguous": len(ambiguous),
            "missing": len(missing),
            "blocked": len(blocked),
            "total_size": total_size,
        },
        "_normalized": normalized,
        "_catalog_items": resolved,
    }


def create_batch(payload, *, principal, idempotency_key=None):
    normalized = normalize_batch_request(payload)
    request_fingerprint = _digest(normalized)
    idempotency_hash = None
    if idempotency_key is not None:
        key = str(idempotency_key).strip()
        if not key or len(key) > 255:
            raise BatchRequestError("invalid_idempotency_key", "Idempotency-Key must contain 1 to 255 characters.")
        idempotency_hash = hashlib.sha256(f"{principal.pk}:{key}".encode()).hexdigest()
        existing = ExternalFileBatch.objects.filter(idempotency_hash=idempotency_hash).first()
        if existing:
            if existing.request_fingerprint != request_fingerprint:
                raise BatchRequestError(
                    "idempotency_conflict",
                    "This Idempotency-Key was already used with a different request.",
                    status_code=409,
                )
            return existing, False

    resolution = resolve_batch_request(normalized, principal=principal)
    has_issues = any(resolution[name] for name in ("ambiguous", "missing", "blocked"))
    if resolution["blocked"]:
        raise BatchRequestError(
            "batch_limit_exceeded",
            "The resolved batch exceeds a configured quota.",
            status_code=413,
            payload={"resolution": public_resolution(resolution)},
        )
    if normalized["strict"] and has_issues:
        raise BatchRequestError(
            "strict_resolution_failed",
            "Strict batch creation requires every selector to resolve without ambiguity.",
            status_code=409,
            payload={"resolution": public_resolution(resolution)},
        )
    if not resolution["_catalog_items"]:
        raise BatchRequestError(
            "no_files_resolved",
            "No authorized, released, physically available files were resolved.",
            status_code=409,
            payload={"resolution": public_resolution(resolution)},
        )

    snapshot_items = [_snapshot_item(item, position) for position, item in enumerate(resolution["_catalog_items"], 1)]
    snapshot_sha256 = _digest([_snapshot_payload(item) for item in snapshot_items])
    ttl_hours = getattr(settings, "GENEDATA_BATCH_TTL_HOURS", 24)
    status_value = ExternalFileBatch.STATUS_PARTIAL if has_issues else ExternalFileBatch.STATUS_READY
    summary = public_resolution(resolution)

    try:
        with transaction.atomic():
            batch = ExternalFileBatch.objects.create(
                batch_id=_new_batch_id(),
                name=normalized["name"],
                created_by_token=principal,
                token_prefix_snapshot=principal.token_prefix,
                status=status_value,
                strict=normalized["strict"],
                request_fingerprint=request_fingerprint,
                idempotency_hash=idempotency_hash,
                file_count=len(snapshot_items),
                total_size=sum(item["size"] for item in snapshot_items),
                snapshot_sha256=snapshot_sha256,
                resolution_summary=summary,
                expires_at=timezone.now() + timedelta(hours=ttl_hours),
            )
            ExternalFileBatchItem.objects.bulk_create([
                ExternalFileBatchItem(batch=batch, **item) for item in snapshot_items
            ])
    except IntegrityError:
        if idempotency_hash:
            existing = ExternalFileBatch.objects.filter(idempotency_hash=idempotency_hash).first()
            if existing and existing.request_fingerprint == request_fingerprint:
                return existing, False
        raise
    return batch, True


def normalize_batch_request(payload):
    if not isinstance(payload, dict):
        raise BatchRequestError("invalid_request", "The request body must be a JSON object.")
    selectors = payload.get("selectors", [])
    if not isinstance(selectors, list):
        raise BatchRequestError("invalid_selectors", "selectors must be an array.")
    normalized_selectors = []
    for index, selector in enumerate(selectors):
        if not isinstance(selector, dict) or not selector:
            raise BatchRequestError("invalid_selector", f"selectors[{index}] must be a non-empty object.")
        unknown = set(selector) - SELECTOR_KEYS
        if unknown:
            raise BatchRequestError("invalid_selector", f"Unsupported selector fields: {sorted(unknown)}.")
        cleaned = {key: str(value).strip() for key, value in selector.items() if str(value).strip()}
        if not cleaned:
            raise BatchRequestError("invalid_selector", f"selectors[{index}] contains no usable values.")
        normalized_selectors.append(cleaned)

    normalized = {
        "name": str(payload.get("name") or "").strip()[:255],
        "strict": _boolean(payload.get("strict", True)),
        "selectors": normalized_selectors,
        "file_codes": _string_list(payload, "file_codes"),
        "accessions": _string_list(payload, "accessions"),
        "assemblies": _string_list(payload, "assemblies"),
        "datasets": _string_list(payload, "datasets"),
        "roles": _string_list(payload, "roles"),
    }
    if _selector_count(normalized) == 0:
        raise BatchRequestError("selectors_required", "At least one file, business object, or compound selector is required.")
    return normalized


def public_resolution(resolution):
    return {key: resolution[key] for key in (
        "strict", "selector_count", "resolved", "ambiguous", "missing", "blocked", "summary",
    )}


def batch_payload(batch, *, include_files=True):
    payload = {
        "batch_id": batch.batch_id,
        "name": batch.name,
        "status": batch.status,
        "strict": batch.strict,
        "file_count": batch.file_count,
        "total_size": batch.total_size,
        "snapshot_sha256": batch.snapshot_sha256,
        "resolution": batch.resolution_summary,
        "created_at": batch.created_at.isoformat(),
        "expires_at": batch.expires_at.isoformat(),
        "manifest_url": f"/gd/api/v1/file-batches/{batch.batch_id}/manifest/",
        "manifest_tsv_url": f"/gd/api/v1/file-batches/{batch.batch_id}/manifest.tsv",
    }
    if include_files:
        payload["files"] = [_item_payload(item) for item in batch.items.all()]
    return payload


def snapshot_is_stale(batch):
    current = {
        item.file_code: item
        for item in DataFile.objects.filter(id__in=batch.items.values_list("data_file_id", flat=True))
    }
    for item in batch.items.all():
        data_file = current.get(item.file_code)
        if (
            data_file is None
            or not data_file.is_current
            or data_file.publication_status != DataFile.PUBLICATION_RELEASED
            or data_file.content_version != item.content_version
        ):
            return True
    return False


def _snapshot_item(item, position):
    return {
        "data_file_id": item["id"],
        "position": position,
        "file_code": item["file_code"],
        "file_name": item["file_name"],
        "content_version": item["content_version"],
        "size": item["size"],
        "sha256": item["sha256"],
        "file_format": item["format"] or "",
        "role": item["role"] or "",
        "accession": item["accession"] or "",
        "assembly": item["assembly"] or "",
        "dataset": item["dataset"] or "",
        "roles": item["roles"],
        "accessions": item["accessions"],
        "assemblies": item["assemblies"],
        "datasets": item["datasets"],
        "content_url": item["content_url"],
    }


def _item_payload(item):
    return {
        "position": item.position,
        "file_code": item.file_code,
        "file_name": item.file_name,
        "content_version": item.content_version,
        "size": item.size,
        "sha256": item.sha256,
        "format": item.file_format,
        "role": item.role or None,
        "roles": item.roles,
        "accession": item.accession or None,
        "accessions": item.accessions,
        "assembly": item.assembly or None,
        "assemblies": item.assemblies,
        "dataset": item.dataset or None,
        "datasets": item.datasets,
        "content_url": item.content_url,
    }


def _snapshot_payload(item):
    return {
        "position": item["position"],
        "file_code": item["file_code"],
        "file_name": item["file_name"],
        "content_version": item["content_version"],
        "size": item["size"],
        "sha256": item["sha256"],
        "format": item["file_format"],
        "role": item["role"] or None,
        "roles": item["roles"],
        "accession": item["accession"] or None,
        "accessions": item["accessions"],
        "assembly": item["assembly"] or None,
        "assemblies": item["assemblies"],
        "dataset": item["dataset"] or None,
        "datasets": item["datasets"],
        "content_url": item["content_url"],
    }


def _public_item(item):
    return {key: value for key, value in item.items() if not key.startswith("_") and key != "id"}


def _candidate(item):
    return {key: item[key] for key in (
        "file_code", "file_name", "format", "role", "accessions", "assemblies", "datasets", "content_version",
    )}


def _matches_selector(item, selector):
    mappings = {
        "file_code": [item["file_code"]],
        "file_name": [item["file_name"]],
        "accession": item["accessions"],
        "assembly": item["assemblies"] + item.get("_assembly_aliases", []),
        "dataset": item["datasets"] + item.get("_dataset_aliases", []),
        "role": item["roles"],
        "format": [item["format"]],
    }
    return all(any(_equal(expected, actual) for actual in mappings[key]) for key, expected in selector.items())


def _matches_business_value(item, field, value):
    values = item[f"{field}s"] + item.get(f"_{field}_aliases", [])
    return any(_equal(value, actual) for actual in values)


def _equal(first, second):
    return normalize_file_name(first) == normalize_file_name(second)


def _selector_count(normalized):
    return sum(len(normalized[key]) for key in ("selectors", "file_codes", "accessions", "assemblies", "datasets"))


def _string_list(payload, key):
    values = payload.get(key, [])
    if not isinstance(values, list):
        raise BatchRequestError("invalid_request", f"{key} must be an array.")
    cleaned = []
    seen = set()
    for value in values:
        text = str(value).strip()
        folded = normalize_file_name(text)
        if text and folded not in seen:
            seen.add(folded)
            cleaned.append(text)
    return cleaned


def _boolean(value):
    if isinstance(value, bool):
        return value
    raise BatchRequestError("invalid_request", "strict must be true or false.")


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _new_batch_id():
    return f"BATCH-{timezone.now():%Y%m%d}-{secrets.token_hex(8).upper()}"
