import csv
from datetime import datetime, timezone as datetime_timezone
from io import StringIO
from pathlib import Path

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
from files.api_v1.throttles import ExternalContentThrottle, ExternalMetadataThrottle
from files.models import DataFile, Dataset
from files.services.datafile_access_service import (
    ACTION_CONTENT,
    ACTION_METADATA,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)
from files.services.external_file_catalog_service import collect_external_files, list_external_files
from files.services.external_file_urls import external_content_url
from files.services.protected_asset_service import (
    apply_conditional_request,
    build_protected_file_response,
)


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def file_catalog(request):
    try:
        payload = list_external_files(
            principal=request.auth,
            file_name=request.query_params.get("file_name"),
            name_contains=request.query_params.get("name_contains"),
            accession=request.query_params.get("accession"),
            assembly=request.query_params.get("assembly"),
            dataset=request.query_params.get("dataset"),
            role=request.query_params.get("role"),
            file_format=request.query_params.get("format"),
            page=request.query_params.get("page", 1),
            page_size=request.query_params.get("page_size", 100),
        )
    except ValueError as exc:
        return Response(
            {"detail": str(exc), "code": "invalid_query"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(payload)


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def file_catalog_manifest_tsv(request):
    """Return the complete authorized file catalog as an Excel-friendly TSV."""
    rows = collect_external_files(principal=request.auth)
    output = StringIO(newline="")
    writer = csv.writer(output, dialect="excel-tab", lineterminator="\n")
    writer.writerow([
        "file_code", "file_name", "accession", "assembly", "dataset",
        "role", "format", "size", "sha256", "content_url",
    ])
    for item in rows:
        writer.writerow([
            item["file_code"], item["file_name"], ",".join(item["accessions"]),
            ",".join(item["assemblies"]), ",".join(item["datasets"]),
            ",".join(item["roles"]), item["format"] or "", item["size"],
            item["sha256"], request.build_absolute_uri(item["content_url"]),
        ])
    response = HttpResponse(
        output.getvalue(),
        content_type="text/tab-separated-values; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="genedata_public_files.tsv"'
    response["X-File-Count"] = str(len(rows))
    return response


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def file_metadata(request, file_identifier):
    data_file = _data_file(file_identifier)
    if data_file is None:
        return _not_found()
    decision = resolve_datafile_access(
        data_file,
        principal=request.auth,
        action=ACTION_METADATA,
    )
    if not decision.allowed:
        return _decision_error(decision)
    location = resolve_protected_datafile_path(data_file)
    if not location.allowed:
        return _not_found()
    try:
        stat = Path(location.resolved_path).stat()
    except OSError:
        return _not_found()

    roles = list(dict.fromkeys(
        data_file.relations.order_by("-is_primary", "id")
        .values_list("file_role", flat=True)
    ))
    return Response({
        "id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "format": _file_format(data_file),
        "role": roles[0] if roles else None,
        "size": stat.st_size,
        "sha256": data_file.sha256.lower(),
        "md5": data_file.md5,
        "content_version": data_file.content_version,
        "dataset": _dataset_code(data_file),
        "last_modified": datetime.fromtimestamp(
            stat.st_mtime, tz=datetime_timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        "content_url": external_content_url(data_file.file_code),
    })


@api_view(["GET", "HEAD"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalContentThrottle])
def file_content(request, file_identifier):
    data_file = _data_file(file_identifier)
    if data_file is None:
        return _not_found()
    decision = resolve_datafile_access(
        data_file,
        principal=request.auth,
        action=ACTION_CONTENT,
    )
    if not decision.allowed:
        return _decision_error(decision)
    response = build_protected_file_response(data_file, disposition="attachment")
    if response is None:
        return _not_found()
    return apply_conditional_request(request, response)


def _data_file(file_identifier):
    queryset = (
        DataFile.objects.select_related("file_type", "dataset")
    )
    data_file = queryset.filter(file_code=file_identifier).first()
    if data_file is not None:
        return data_file
    if str(file_identifier).isdigit():
        return queryset.filter(id=int(file_identifier)).first()
    return None


def _file_format(data_file):
    if data_file.file_type_id:
        file_type = data_file.file_type
        return file_type.format or file_type.code or file_type.name or file_type.extension
    suffix = Path(data_file.file_name).suffix.lstrip(".")
    return suffix.upper() or None


def _dataset_code(data_file):
    if data_file.dataset_id:
        return data_file.dataset.dataset_code
    related_ids = []
    for value in data_file.relations.filter(related_type="dataset").values_list(
        "related_id", flat=True
    ):
        try:
            related_ids.append(int(value))
        except (TypeError, ValueError):
            return None
    codes = list(
        Dataset.objects.filter(id__in=set(related_ids))
        .order_by("dataset_code")
        .values_list("dataset_code", flat=True)
    )
    return codes[0] if len(codes) == 1 else None


def _decision_error(decision):
    if decision.reason == "authentication_required":
        response = Response(
            {"detail": "Bearer token required.", "code": "authentication_required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        response["WWW-Authenticate"] = "Bearer"
        return response
    if decision.reason in {"invalid_or_inactive_token", "insufficient_scope", "insufficient_access_tier"}:
        return Response(
            {"detail": "Access denied.", "code": decision.reason},
            status=status.HTTP_403_FORBIDDEN,
        )
    return _not_found()


def _not_found():
    return Response(
        {"detail": "Not found.", "code": "not_found"},
        status=status.HTTP_404_NOT_FOUND,
    )
