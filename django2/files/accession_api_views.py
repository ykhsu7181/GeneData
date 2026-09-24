"""Endpoints used by the unified Accession card and homepage."""

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Accession
from files.services.accession_detail_service import (
    get_accession_annotations,
    get_accession_assemblies,
    get_accession_datasets,
    get_accession_files,
    get_accession_or_none,
    get_accession_samples,
    get_accession_summary,
)
from files.services.dashboard_service import DASHBOARD_CACHE_KEY, build_popular_accessions


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
def popular_accessions(request):
    limit = getattr(request, "query_params", request.GET).get("limit", 10)
    normalized_limit = min(max(_safe_int(limit, 10), 1), 10)
    results = build_popular_accessions(normalized_limit)
    return Response({"count": len(results), "results": results, "limit": normalized_limit})


def _safe_int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


@api_view(["POST"])
@permission_classes([AllowAny])
def record_accession_view(request, accession):
    accession_obj = get_accession_or_none(accession)
    if not accession_obj:
        return Response(
            {"success": False, "message": f'Accession "{accession}" does not exist.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    viewed_at = timezone.now()
    Accession.objects.filter(pk=accession_obj.pk).update(
        view_count=F("view_count") + 1,
        last_viewed_at=viewed_at,
    )
    accession_obj.refresh_from_db(fields=["view_count", "last_viewed_at"])
    cache.delete(DASHBOARD_CACHE_KEY)
    return Response(
        {
            "success": True,
            "accession": accession_obj.accession,
            "view_count": accession_obj.view_count,
            "last_viewed_at": accession_obj.last_viewed_at,
        }
    )


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
