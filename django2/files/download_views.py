import mimetypes
import os

from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import DataFile
from files.services.query_view_helpers import has_path_traversal


@api_view(["GET"])
@permission_classes([AllowAny])
def download_datafile(request, file_id):
    """Download a DataFile from the active file model."""
    data_file = DataFile.objects.filter(id=file_id).first()
    if not data_file:
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    file_path = data_file.file_path
    if not file_path or has_path_traversal(file_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    normalized_path = os.path.abspath(os.path.normpath(file_path))
    if not os.path.isfile(normalized_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    content_type, _ = mimetypes.guess_type(normalized_path)
    response = FileResponse(
        open(normalized_path, "rb"),
        content_type=content_type or "application/octet-stream",
    )
    download_name = os.path.basename(data_file.file_name or normalized_path)
    response["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response
