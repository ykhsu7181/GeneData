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


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalMetadataThrottle])
def accession_files(request, accession):
    accession_obj = Accession.objects.filter(accession=accession).first()
    if accession_obj is None:
        return Response(
            {"detail": "Not found.", "code": "not_found"},
            status=status.HTTP_404_NOT_FOUND,
        )
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
