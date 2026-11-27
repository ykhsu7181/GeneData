"""Protected browser-asset responses delegated to Nginx via X-Accel-Redirect."""

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.services.data_asset_access_service import build_data_asset_file_response
from files.services.jbrowse_asset_service import (
    JBrowseAssetError,
    resolve_jbrowse_browser_file,
)
from files.services.jbrowse_config_service import (
    JBrowseAssemblyNotFound,
    get_jbrowse_config,
    get_jbrowse_status,
)
from files.services.jbrowse_location_service import (
    JBrowseLocationError,
    resolve_jbrowse_location,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def jbrowse_status(request, assembly_id):
    annotation_id, error_response = _annotation_id_parameter(request)
    if error_response is not None:
        return error_response
    try:
        payload = get_jbrowse_status(assembly_id, annotation_id=annotation_id)
    except JBrowseAssemblyNotFound:
        return _not_found()
    return Response(payload)


@api_view(["GET"])
@permission_classes([AllowAny])
def jbrowse_config(request, assembly_id):
    annotation_id, error_response = _annotation_id_parameter(request)
    if error_response is not None:
        return error_response
    try:
        config, status_payload = get_jbrowse_config(
            assembly_id,
            annotation_id=annotation_id,
        )
    except JBrowseAssemblyNotFound:
        return _not_found()
    if config is None:
        return Response(status_payload, status=status.HTTP_409_CONFLICT)
    return Response(config)


@api_view(["GET"])
@permission_classes([AllowAny])
def jbrowse_location(request, assembly_id, annotation_id, feature_id):
    expected_version = request.query_params.get("feature_index_version") or None
    try:
        payload = resolve_jbrowse_location(
            assembly_id,
            annotation_id,
            feature_id,
            expected_index_version=expected_version,
        )
    except JBrowseLocationError as exc:
        return Response(
            {"detail": str(exc), "code": exc.code},
            status=exc.http_status,
        )
    return Response(payload)


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def browser_asset(request, file_id):
    asset_code = request.query_params.get("asset_code") or ""
    if not asset_code:
        return _not_found()
    try:
        asset, data_file = resolve_jbrowse_browser_file(
            asset_code,
            file_id,
            user=request.user,
            roots=_jbrowse_protected_roots(),
        )
    except JBrowseAssetError:
        return _not_found()
    decision, response = build_data_asset_file_response(
        asset,
        data_file,
        user=request.user,
        roots=_jbrowse_protected_roots(),
        disposition="inline",
    )
    if not decision.allowed or response is None:
        return _not_found()
    return response


def _jbrowse_protected_roots():
    return {
        "manual": {
            "path": settings.MANUAL_FILES_DIR,
            "internal_uri": getattr(
                settings,
                "GENEDATA_JBROWSE_MANUAL_INTERNAL_PREFIX",
                "/_protected_manual_files/",
            ),
        },
        "derived": {
            "path": settings.GENEDATA_DERIVED_DATA_DIR,
            "internal_uri": getattr(
                settings,
                "GENEDATA_JBROWSE_DERIVED_INTERNAL_PREFIX",
                "/_protected_derived_data/",
            ),
        },
    }


def _integer_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _annotation_id_parameter(request):
    raw_value = request.query_params.get("annotation_id")
    if raw_value in {None, ""}:
        return None, None
    value = _integer_id(raw_value)
    if value is None or value < 1:
        return None, Response(
            {"detail": "annotation_id must be a positive integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return value, None


def _not_found():
    return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
