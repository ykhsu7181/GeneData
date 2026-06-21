from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.services.dashboard_service import build_dashboard_payload


@api_view(["GET"])
@permission_classes([AllowAny])
def warehouse_dashboard(request):
    return Response(build_dashboard_payload())
