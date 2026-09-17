"""Public read-only endpoints for Assembly data."""

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Assembly
from files.serializers import AssemblyListSerializer
from files.services.assembly_detail_service import get_assembly_detail
from files.services.file_relation_service import GenomeFileSelectionError


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)


def _page_params(request):
    params = getattr(request, "query_params", request.GET)
    page = _positive_int(params.get("page"), 1)
    page_size = min(_positive_int(params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    return page, page_size


def _search_term(request):
    params = getattr(request, "query_params", request.GET)
    return (params.get("search") or params.get("q") or "").strip()


def _assembly_queryset(keyword):
    queryset = Assembly.objects.select_related("accession", "accession__species").all()
    if not keyword:
        return queryset

    return queryset.filter(
        Q(accession__accession__icontains=keyword)
        | Q(name__icontains=keyword)
        | Q(display_name__icontains=keyword)
        | Q(assembly_name__icontains=keyword)
        | Q(assembly_code__icontains=keyword)
        | Q(assembly_accession__icontains=keyword)
        | Q(standard_id__icontains=keyword)
        | Q(species_code__icontains=keyword)
        | Q(assembly_level__icontains=keyword)
        | Q(accession__species__species_code__icontains=keyword)
        | Q(accession__species__scientific_name__icontains=keyword)
        | Q(accession__species__common_name__icontains=keyword)
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def assembly_list(request):
    page, page_size = _page_params(request)
    queryset = _assembly_queryset(_search_term(request))
    paginator = Paginator(queryset, page_size)

    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages) if paginator.num_pages else []

    rows = AssemblyListSerializer(page_obj.object_list if hasattr(page_obj, "object_list") else [], many=True).data
    return Response(
        {
            "count": paginator.count,
            "page": page_obj.number if hasattr(page_obj, "number") else page,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "next": page_obj.next_page_number() if hasattr(page_obj, "has_next") and page_obj.has_next() else None,
            "previous": page_obj.previous_page_number() if hasattr(page_obj, "has_previous") and page_obj.has_previous() else None,
            "results": rows,
        }
    )


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
