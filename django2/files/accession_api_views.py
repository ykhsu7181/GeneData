"""Small read-only endpoints used by the unified Accession card page."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.services.accession_detail_service import (
    get_accession_annotations,
    get_accession_assemblies,
    get_accession_datasets,
    get_accession_files,
    get_accession_or_none,
    get_accession_samples,
    get_accession_summary,
)


def _page_params(request):
    params = getattr(request, "query_params", request.GET)
    return params.get("page", 1), params.get("page_size", 20)


def _accession_response(accession_code, loader, request=None):
    accession = get_accession_or_none(accession_code)
    if not accession:
        return Response(
            {"success": False, "message": f'Accession "{accession_code}" 不存在'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request is None:
        data = loader(accession)
    else:
        page, page_size = _page_params(request)
        data = loader(accession, page, page_size)
    return Response({"success": True, "data": data})


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_summary(request, accession):
    return _accession_response(accession, get_accession_summary)


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_datasets(request, accession):
    return _accession_response(accession, get_accession_datasets, request)


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_samples(request, accession):
    return _accession_response(accession, get_accession_samples, request)


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_assemblies(request, accession):
    return _accession_response(accession, get_accession_assemblies, request)


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_annotations(request, accession):
    return _accession_response(accession, get_accession_annotations, request)


@api_view(["GET"])
@permission_classes([AllowAny])
def accession_files(request, accession):
    return _accession_response(accession, get_accession_files, request)
