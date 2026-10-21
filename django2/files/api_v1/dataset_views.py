import csv
import re
from io import StringIO

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.api_v1.authentication import DataAccessTokenAuthentication
from files.api_v1.throttles import ExternalManifestThrottle
from files.models import DataAccessToken
from files.services.external_dataset_manifest_service import (
    build_dataset_manifest,
    find_public_datasets,
)


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalManifestThrottle])
def dataset_manifest(request, dataset):
    error = _authorize_manifest(request.auth)
    if error is not None:
        return error
    datasets = find_public_datasets(dataset)
    if not datasets:
        return _not_found()
    return Response(build_dataset_manifest(dataset, datasets, principal=request.auth))


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalManifestThrottle])
def dataset_manifest_tsv(request, dataset):
    error = _authorize_manifest(request.auth)
    if error is not None:
        return error
    datasets = find_public_datasets(dataset)
    if not datasets:
        return _not_found()
    payload = build_dataset_manifest(dataset, datasets, principal=request.auth)
    output = StringIO(newline="")
    writer = csv.writer(output, dialect="excel-tab", lineterminator="\n")
    writer.writerow([
        "accession",
        "file_role",
        "file_name",
        "size",
        "sha256",
        "md5",
        "content_version",
        "url",
    ])
    for item in payload["files"]:
        accession = item["accession"] or ",".join(item["accessions"])
        writer.writerow([
            accession,
            item["role"],
            item["file_name"],
            item["size"],
            item["sha256"],
            item["md5"],
            item["content_version"],
            request.build_absolute_uri(item["content_url"]),
        ])
    response = HttpResponse(
        output.getvalue(),
        content_type="text/tab-separated-values; charset=utf-8",
    )
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", dataset) or "dataset"
    response["Content-Disposition"] = (
        f'attachment; filename="{safe_name}.manifest.tsv"'
    )
    return response


def _authorize_manifest(principal):
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
    if not principal.has_scope(DataAccessToken.SCOPE_DATASET_MANIFEST):
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
