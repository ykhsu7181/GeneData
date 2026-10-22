from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.api_v1.authentication import DataAccessTokenAuthentication
from files.api_v1.throttles import ExternalBatchThrottle
from files.models import DataAccessToken, ExternalFileArchive, ExternalFileBatch
from files.services.external_file_archive_service import (
    ArchiveRequestError,
    archive_sources_authorized,
    archive_payload,
    build_archive_response,
    queue_archive,
)
from files.services.protected_asset_service import apply_conditional_request


@api_view(["POST"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def create_file_archive(request, batch_id):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_ARCHIVE)
    if error:
        return error
    batch = ExternalFileBatch.objects.prefetch_related("items__data_file").filter(
        batch_id=batch_id,
        created_by_token=request.auth,
    ).first()
    if batch is None:
        return _not_found()
    try:
        archive, created = queue_archive(
            batch,
            principal=request.auth,
            payload=request.data,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except ArchiveRequestError as exc:
        return Response(
            {"detail": exc.detail, "code": exc.code},
            status=exc.status_code,
        )
    response = Response(
        archive_payload(archive),
        status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
    )
    response["Location"] = f"/gd/api/v1/file-archives/{archive.archive_id}/"
    if archive.status in {ExternalFileArchive.STATUS_QUEUED, ExternalFileArchive.STATUS_RUNNING}:
        response["Retry-After"] = "5"
    return response


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def file_archive_status(request, archive_id):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_READ)
    if error:
        return error
    archive = _owned_archive(request.auth, archive_id)
    if archive is None:
        return _not_found()
    payload = archive_payload(archive)
    response = Response(payload)
    if payload["status"] in {ExternalFileArchive.STATUS_QUEUED, ExternalFileArchive.STATUS_RUNNING}:
        response["Retry-After"] = "5"
    return response


@api_view(["GET", "HEAD"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalBatchThrottle])
def file_archive_content(request, archive_id):
    error = _authorize(request.auth, DataAccessToken.SCOPE_BATCH_DOWNLOAD)
    if error:
        return error
    archive = _owned_archive(request.auth, archive_id)
    if archive is None:
        return _not_found()
    if archive.expires_at <= timezone.now() or archive.status == ExternalFileArchive.STATUS_EXPIRED:
        return Response(
            {"detail": "Archive expired.", "code": "archive_expired"},
            status=status.HTTP_410_GONE,
        )
    if archive.status in {ExternalFileArchive.STATUS_QUEUED, ExternalFileArchive.STATUS_RUNNING}:
        return Response(
            {"detail": "Archive is not ready.", "code": "archive_not_ready"},
            status=status.HTTP_409_CONFLICT,
        )
    if archive.status == ExternalFileArchive.STATUS_FAILED:
        return Response(
            {"detail": "Archive generation failed.", "code": "archive_failed"},
            status=status.HTTP_409_CONFLICT,
        )
    if not archive_sources_authorized(archive, principal=request.auth):
        return _not_found()
    response = build_archive_response(archive)
    if response is None:
        return Response(
            {"detail": "Archive output is unavailable.", "code": "archive_unavailable"},
            status=status.HTTP_409_CONFLICT,
        )
    return apply_conditional_request(request, response)


def _owned_archive(principal, archive_id):
    return ExternalFileArchive.objects.select_related("batch").filter(
        archive_id=archive_id,
        created_by_token=principal,
    ).first()


def _authorize(principal, scope):
    if principal is None:
        response = Response(
            {"detail": "Bearer token required.", "code": "authentication_required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        response["WWW-Authenticate"] = "Bearer"
        return response
    if not isinstance(principal, DataAccessToken) or not principal.is_active:
        return Response(
            {"detail": "Access denied.", "code": "invalid_or_inactive_token"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not principal.has_scope(scope):
        return Response(
            {"detail": "Access denied.", "code": "insufficient_scope"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _not_found():
    return Response(
        {"detail": "Not found.", "code": "not_found"},
        status=status.HTTP_404_NOT_FOUND,
    )
