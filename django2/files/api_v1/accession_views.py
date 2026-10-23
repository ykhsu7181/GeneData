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
from files.api_v1.throttles import ExternalMetadataThrottle
from files.models import Accession
from files.services.external_file_discovery_service import discover_accession_files
from files.services.external_accession_metadata_service import (
    list_external_accession_assemblies,
    serialize_external_accession,
)


def _get_accession(accession):
    try:
        return Accession.objects.select_related("species").get(accession=accession)
    except Accession.DoesNotExist:
        return None


def _not_found():
    return Response(
        {"detail": "Not found.", "code": "not_found"},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def accession_metadata(request, accession):
    accession_obj = _get_accession(accession)
    if accession_obj is None:
        return _not_found()
    return Response(serialize_external_accession(accession_obj))


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def accession_assemblies(request, accession):
    accession_obj = _get_accession(accession)
    if accession_obj is None:
        return _not_found()
    return Response(list_external_accession_assemblies(accession_obj))


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def accession_files(request, accession):
    accession_obj = _get_accession(accession)
    if accession_obj is None:
        return _not_found()
    try:
        payload = discover_accession_files(
            accession_obj,
            principal=request.auth,
            role=request.query_params.get("role"),
            category=request.query_params.get("category"),
            dataset=request.query_params.get("dataset"),
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
