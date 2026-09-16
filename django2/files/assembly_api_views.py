"""Public read-only endpoints for Assembly detail data."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Assembly
from files.services.assembly_detail_service import get_assembly_detail
from files.services.file_relation_service import GenomeFileSelectionError


@api_view(["GET"])
@permission_classes([AllowAny])
def assembly_summary(request, assembly_id):
    try:
        data = get_assembly_detail(assembly_id)
    except Assembly.DoesNotExist:
        return Response(
            {"success": False, "message": f'Assembly "{assembly_id}" 不存在'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except GenomeFileSelectionError as exc:
        return Response(
            {
                "success": False,
                "message": "Assembly 主基因组文件配置冲突",
                "detail": str(exc),
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response({"success": True, "data": data})
