from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.services.data_overview_v2_service import build_datafile_detail_payload


@api_view(["GET"])
@permission_classes([AllowAny])
def datafile_detail(request, file_id):
    payload = build_datafile_detail_payload(file_id)
    if payload is None:
        return Response({"detail": "DataFile not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)
