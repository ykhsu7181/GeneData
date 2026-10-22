import csv
import re
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.api_v1.authentication import DataAccessTokenAuthentication
from files.api_v1.throttles import ExternalBatchThrottle
from files.models import DataAccessToken, ExternalFileBatch
from files.services.external_file_batch_service import (
    BatchRequestError,
    batch_payload,
    create_batch,
    public_resolution,
    resolve_batch_request,
    snapshot_is_stale,
)


@api_view(["POST"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def resolve_file_batch(request):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_CREATE)
    if error:
        return error
    try:
        resolution = resolve_batch_request(request.data, principal=request.auth)
    except BatchRequestError as exc:
        return _error(exc)
    return Response(public_resolution(resolution))


@api_view(["POST"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def create_file_batch(request):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_CREATE)
    if error:
        return error
    try:
        batch, created = create_batch(
            request.data,
            principal=request.auth,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except BatchRequestError as exc:
        return _error(exc)
    return Response(batch_payload(batch), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def file_batch_detail(request, batch_id):
    batch, error = _owned_batch(request, batch_id)
    if error:
        return error
    return Response(batch_payload(batch, include_files=False))


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def file_batch_manifest(request, batch_id):
    batch, error = _manifest_batch(request, batch_id)
    if error:
        return error
    return Response(batch_payload(batch))


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def file_batch_manifest_tsv(request, batch_id):
    batch, error = _manifest_batch(request, batch_id)
    if error:
        return error
    output = StringIO(newline="")
    writer = csv.writer(output, dialect="excel-tab", lineterminator="\n")
    writer.writerow([
        "position", "file_code", "file_name", "role", "format", "accession",
        "assembly", "dataset", "size", "sha256", "content_version", "url",
    ])
    for item in batch.items.all():
        writer.writerow([
            item.position, item.file_code, item.file_name, item.role, item.file_format,
            item.accession, item.assembly, item.dataset, item.size, item.sha256,
            item.content_version, request.build_absolute_uri(item.content_url),
        ])
    response = HttpResponse(output.getvalue(), content_type="text/tab-separated-values; charset=utf-8")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", batch.batch_id)
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.manifest.tsv"'
    response["X-Snapshot-SHA256"] = batch.snapshot_sha256
    return response


def _manifest_batch(request, batch_id):
    batch, error = _owned_batch(request, batch_id)
    if error:
        return batch, error
    if batch.expires_at <= timezone.now():
        return None, Response(
            {"detail": "Batch manifest expired.", "code": "batch_expired"},
            status=status.HTTP_410_GONE,
        )
    if snapshot_is_stale(batch):
        return None, Response(
            {"detail": "A source file no longer matches this immutable snapshot.", "code": "snapshot_stale"},
            status=status.HTTP_409_CONFLICT,
        )
    return batch, None


def _owned_batch(request, batch_id):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_READ)
    if error:
        return None, error
    batch = ExternalFileBatch.objects.prefetch_related("items").filter(
        batch_id=batch_id,
        created_by_token=request.auth,
    ).first()
    if batch is None:
        return None, Response({"detail": "Not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
    return batch, None


def _authorize(principal, scope):
    if principal is None:
        response = Response(
            {"detail": "Bearer token required.", "code": "authentication_required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        response["WWW-Authenticate"] = "Bearer"
        return response
    if not isinstance(principal, DataAccessToken) or not principal.is_active:
        return Response({"detail": "Access denied.", "code": "invalid_or_inactive_token"}, status=403)
    if not principal.has_scope(scope):
        return Response({"detail": "Access denied.", "code": "insufficient_scope"}, status=403)
    return None


def _error(exc):
    payload = {"detail": exc.detail, "code": exc.code}
    payload.update(exc.payload)
    return Response(payload, status=exc.status_code)
