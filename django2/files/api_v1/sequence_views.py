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
from files.api_v1.throttles import ExternalSequenceThrottle
from files.models import DataAccessToken
from files.services.external_sequence_service import (
    SequenceRegionError,
    fetch_assembly_sequence_region,
    find_external_assembly,
)


@api_view(["GET"])
@authentication_classes([DataAccessTokenAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ExternalSequenceThrottle])
def assembly_sequence(request, assembly):
    error = _authorize_sequence(request.auth)
    if error is not None:
        return error
    try:
        assembly_obj = find_external_assembly(assembly)
        if assembly_obj is None:
            return _error("not_found", "Assembly not found.", 404)
        result = fetch_assembly_sequence_region(
            assembly_obj,
            principal=request.auth,
            sequence_id=request.query_params.get("sequence"),
            start=request.query_params.get("start"),
            end=request.query_params.get("end"),
        )
    except SequenceRegionError as exc:
        return _error(exc.code, str(exc), exc.http_status)
    response = HttpResponse(result.content, content_type="text/x-fasta")
    response["Content-Length"] = str(len(result.content))
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Sequence-Id"] = result.sequence_id
    response["X-Sequence-Start"] = str(result.start)
    response["X-Sequence-End"] = str(result.end)
    response["X-Coordinate-System"] = "1-based-inclusive"
    return response


def _authorize_sequence(principal):
    if principal is None:
        response = _error(
            "authentication_required", "Bearer token required.", 401
        )
        response["WWW-Authenticate"] = "Bearer"
        return response
    if not isinstance(principal, DataAccessToken) or not principal.is_active:
        return _error("invalid_or_inactive_token", "Access denied.", 403)
    if not principal.has_scope(DataAccessToken.SCOPE_SEQUENCE_READ):
        return _error("insufficient_scope", "Access denied.", 403)
    return None


def _error(code, detail, http_status):
    return Response(
        {"detail": detail, "code": code},
        status=http_status,
    )
