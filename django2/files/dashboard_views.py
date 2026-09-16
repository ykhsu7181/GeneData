from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.services.dashboard_service import build_dashboard_payload


DASHBOARD_CACHE_KEY = "warehouse_dashboard_payload_v2"
DASHBOARD_CACHE_TIMEOUT = 60 * 10


def get_cached_dashboard_payload(force_refresh=False):
    if not force_refresh:
        payload = cache.get(DASHBOARD_CACHE_KEY)
        if payload is not None:
            return payload

    payload = build_dashboard_payload()
    cache.set(DASHBOARD_CACHE_KEY, payload, DASHBOARD_CACHE_TIMEOUT)
    return payload


@api_view(["GET"])
@permission_classes([AllowAny])
def warehouse_dashboard(request):
    return Response(get_cached_dashboard_payload())
