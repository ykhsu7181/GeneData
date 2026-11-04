from django.shortcuts import render
import os
import mimetypes
import json
import random
import subprocess
import shutil
from datetime import datetime, timedelta
import threading
import time
import zipfile
import tempfile
from django.http import FileResponse, HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from functools import lru_cache
from .models import (
    FileType,
    Organism,
    FileCategory,
    Accession,
    Assembly,
    Annotation,
    DataFile,
    FileRelation,
    Sample,
)
from .serializers import (
    FileTypeSerializer,
    OrganismSerializer, FileCategorySerializer,
    AccessionSerializer, AccessionDetailSerializer
)
from .file_categories import FILE_CATEGORY_CHOICES
from .services.accession_context import (
    AmbiguousContextError,
    get_context_genome_file,
    get_context_organism,
    resolve_preferred_annotation,
    resolve_preferred_assembly,
)
from .services.assembly_visibility import filter_visible_assemblies
from .services.file_relation_service import get_files_for_annotation
from .parsers.archive import safe_extract_zip

import logging

logger = logging.getLogger(__name__)

GENOMEFILE_ARCHIVE_MESSAGE = "GenomeFile API is archived, use DataFile API instead."
GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE = "GenomeFile download is archived, use DataFile download."


def _genomefile_archived_response(message=None):
    return Response(
        {
            "success": False,
            "archived": True,
            "message": message or GENOMEFILE_ARCHIVE_MESSAGE,
        },
        status=status.HTTP_410_GONE,
    )


def _datafile_download_url(file_id):
    if not file_id:
        return None
    return f"/gd/api/files/data-files/{file_id}/download/"


def _format_file_size(size):
    size = int(size or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024


def _build_accession_file_inventory(accession_obj, assemblies):
    assembly_ids = [assembly.id for assembly in assemblies]
    annotation_ids = [
        annotation.id
        for assembly in assemblies
        for annotation in getattr(assembly, "prefetched_annotations", [])
    ]
    relation_filter = Q(
        related_type="accession",
        related_id=str(accession_obj.id),
    )
    if assembly_ids:
        relation_filter |= Q(
            related_type="assembly",
            related_id__in=[str(value) for value in assembly_ids],
        )
    if annotation_ids:
        relation_filter |= Q(
            related_type="annotation",
            related_id__in=[str(value) for value in annotation_ids],
        )

    relation_priority = {"accession": 0, "assembly": 1, "annotation": 2}
    relations = list(
        FileRelation.objects.filter(relation_filter)
        .select_related("file__file_type", "file__dataset__project")
        .order_by("file_id", "id")
    )
    relations.sort(key=lambda item: (item.file_id, relation_priority.get(item.related_type, 99), item.id))

    assembly_labels = {
        str(assembly.id): assembly.display_name or assembly.name
        for assembly in assemblies
    }
    annotation_labels = {
        str(annotation.id): annotation.display_name or annotation.name
        for assembly in assemblies
        for annotation in getattr(assembly, "prefetched_annotations", [])
    }
    object_labels = {
        "accession": {str(accession_obj.id): accession_obj.accession},
        "assembly": assembly_labels,
        "annotation": annotation_labels,
    }
    relation_entries_by_file = {}
    for relation in relations:
        relation_entries_by_file.setdefault(relation.file_id, []).append({
            "related_type": relation.related_type,
            "related_id": relation.related_id,
            "related_code": relation.related_code,
            "related_object": (
                object_labels.get(relation.related_type, {}).get(relation.related_id)
                or relation.related_code
                or relation.related_id
            ),
            "file_role": relation.file_role,
            "is_primary": relation.is_primary,
        })

    inventory = []
    seen_file_ids = set()
    for relation in relations:
        data_file = relation.file
        if data_file.id in seen_file_ids:
            continue
        seen_file_ids.add(data_file.id)
        dataset = data_file.dataset
        inventory.append({
            "id": data_file.id,
            "file_code": data_file.file_code,
            "name": data_file.file_name,
            "file_name": data_file.file_name,
            "file_path": data_file.file_path,
            "file_size": data_file.file_size,
            "size": data_file.file_size,
            "size_display": _format_file_size(data_file.file_size),
            "md5": data_file.md5,
            "file_role": relation.file_role,
            "category": relation.file_role,
            "file_type": data_file.file_type.name if data_file.file_type else None,
            "related_type": relation.related_type,
            "related_id": relation.related_id,
            "related_code": relation.related_code,
            "related_object": (
                object_labels.get(relation.related_type, {}).get(relation.related_id)
                or relation.related_code
                or relation.related_id
            ),
            "relations": relation_entries_by_file.get(data_file.id, []),
            "accession_id": accession_obj.id,
            "assembly_id": int(relation.related_id) if relation.related_type == "assembly" else None,
            "annotation_id": int(relation.related_id) if relation.related_type == "annotation" else None,
            "dataset_id": dataset.id if dataset else None,
            "dataset_code": dataset.dataset_code if dataset else None,
            "dataset_name": dataset.dataset_name if dataset else None,
            "scope": relation.related_type,
            "source": "new_relation",
            "created_at": data_file.created_at,
            "updated_at": data_file.updated_at,
            "datafile_download_url": _datafile_download_url(data_file.id),
            "download_url": _datafile_download_url(data_file.id),
        })

    return inventory, relations


def _build_compatibility_file_summary(files_data, default_assembly_id=None, default_annotation_id=None):
    """
    Compatibility-only summary for legacy callers.
    The result is aggregated from the default assembly / default annotation path
    and does not represent the full accession hierarchy.
    """
    compatibility_files = []
    for item in files_data:
        scope = item.get('scope')
        if scope == 'annotation':
            if default_annotation_id and item.get('annotation_id') == default_annotation_id:
                compatibility_files.append(item)
        else:
            if default_assembly_id and item.get('assembly_id') == default_assembly_id:
                compatibility_files.append(item)

    file_status = {}
    file_names = {}
    for category_code, _ in FILE_CATEGORY_CHOICES:
        matched_files = [item for item in compatibility_files if item['category'] == category_code]
        status_key = category_code.replace('.', '_')
        file_status[status_key] = len(matched_files) > 0
        file_names[status_key] = matched_files[0]['name'] if matched_files else None

    return file_status, file_names








def _has_path_traversal(file_path):
    path_parts = file_path.replace('\\', os.sep).replace('/', os.sep).split(os.sep)
    return any(part == '..' for part in path_parts)


@lru_cache(maxsize=128)
def _parse_annotation_summary(annotation_file_path):
    summary = {
        'source_summary': None,
        'feature_types_summary': None,
        'chromosomes_summary': None,
        'coordinate_range_summary': None,
    }

    if not annotation_file_path or not os.path.exists(annotation_file_path):
        return summary

    sources = set()
    feature_types = set()
    chromosomes = set()
    min_start = None
    max_end = None

    try:
        with open(annotation_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('\t')
                if len(parts) < 5:
                    continue

                seqid = parts[0].strip()
                source = parts[1].strip() if len(parts) > 1 else ''
                feature = parts[2].strip() if len(parts) > 2 else ''

                try:
                    start = int(parts[3])
                    end = int(parts[4])
                except (TypeError, ValueError):
                    start = None
                    end = None

                if seqid:
                    chromosomes.add(seqid)
                if source and source != '.':
                    sources.add(source)
                if feature and feature != '.':
                    feature_types.add(feature)

                if start is not None:
                    min_start = start if min_start is None else min(min_start, start)
                if end is not None:
                    max_end = end if max_end is None else max(max_end, end)
    except Exception as e:
        logger.warning(f"解析注释摘要失败: {annotation_file_path}, error: {str(e)}")
        return summary

    if sources:
        summary['source_summary'] = ', '.join(sorted(sources))
    if feature_types:
        summary['feature_types_summary'] = ', '.join(sorted(feature_types))
    if chromosomes:
        summary['chromosomes_summary'] = ', '.join(sorted(chromosomes))
    if min_start is not None and max_end is not None:
        summary['coordinate_range_summary'] = f"{min_start:,} - {max_end:,}"

    return summary

class FileTypeViewSet(viewsets.ModelViewSet):
    """文件类型视图集"""
    queryset = FileType.objects.all()
    serializer_class = FileTypeSerializer

class OrganismViewSet(viewsets.ModelViewSet):
    """生物体视图集"""
    queryset = Organism.objects.all()
    serializer_class = OrganismSerializer

class FileCategoryViewSet(viewsets.ModelViewSet):
    """文件类别视图集"""
    queryset = FileCategory.objects.all()
    serializer_class = FileCategorySerializer



def download_manual_file(request, filename=None):
    """手动文件下载函数"""
    try:
        # 优先使用URL参数中的filename，如果没有则使用GET参数中的path
        if filename:
            file_path = filename
        else:
            file_path = request.GET.get('path')

        if not file_path:
            return HttpResponse("未提供文件路径", status=400)

        # 安全检查：确保路径在允许的目录内
        manual_files_dir = settings.MANUAL_FILES_DIR
        abs_file_path = os.path.join(manual_files_dir, file_path)

        if not os.path.exists(abs_file_path):
            return HttpResponse("文件不存在", status=404)

        # 获取文件类型
        content_type, _ = mimetypes.guess_type(abs_file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        # 创建文件响应
        response = FileResponse(open(abs_file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(abs_file_path)}"'
        return response

    except Exception as e:
        return HttpResponse(f"下载文件时出错: {str(e)}", status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def download_datafile(request, file_id):
    """Download a DataFile without changing the legacy GenomeFile download API."""
    data_file = DataFile.objects.filter(id=file_id).first()
    if not data_file:
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    file_path = data_file.file_path
    if not file_path or _has_path_traversal(file_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    normalized_path = os.path.abspath(os.path.normpath(file_path))
    if not os.path.isfile(normalized_path):
        return Response({"error": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    content_type, _ = mimetypes.guess_type(normalized_path)
    if content_type is None:
        content_type = 'application/octet-stream'

    download_name = os.path.basename(data_file.file_name or normalized_path)
    response = FileResponse(open(normalized_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{download_name}"'
    return response


# ==================== 管理后台API ====================

    def _resolve_request_organism(self, request):
        organism = request.query_params.get('organism')
        accession = request.query_params.get('accession')
        assembly_id = request.query_params.get('assembly_id')
        annotation_id = request.query_params.get('annotation_id')
        return get_context_organism(
            annotation_id=annotation_id,
            assembly_id=assembly_id,
            accession=accession,
            organism=organism,
        )

    def _resolve_annotation_file_path(self, request):
        organism = request.query_params.get('organism')
        accession = request.query_params.get('accession')
        assembly_id = request.query_params.get('assembly_id')
        annotation_id = request.query_params.get('annotation_id')
        resolved_organism, _, resolved_assembly, resolved_annotation = get_context_organism(
            annotation_id=annotation_id,
            assembly_id=assembly_id,
            accession=accession,
            organism=organism,
        )

        if resolved_annotation:
            for annotation_file in get_files_for_annotation(resolved_annotation.id, file_role='annotation'):
                candidate_path = annotation_file.get('file_path')
                if candidate_path and os.path.exists(candidate_path):
                    return resolved_organism, candidate_path

        manual_files_dir = settings.MANUAL_FILES_DIR
        for extension in ['gff', 'gff3']:
            candidate = os.path.join(manual_files_dir, f'annotation.{resolved_organism}.{extension}')
            if os.path.exists(candidate):
                return resolved_organism, candidate

        return resolved_organism, None

    @action(detail=False, methods=['get'])
    def get_chromosomes(self, request):
        """获取指定上下文的染色体列表"""
        organism = request.query_params.get('organism')
        accession = request.query_params.get('accession')
        assembly_id = request.query_params.get('assembly_id')
        if not organism and not accession and not assembly_id:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        _, _, genome_file = get_context_genome_file(
            assembly_id=assembly_id,
            accession=accession,
            organism=organism,
        )

        if not genome_file:
            return Response(
                {"error": f"未找到 {organism or accession or assembly_id} 的基因组文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        chromosomes = []
        try:
            with open(genome_file.file_path, 'r') as f:
                for line in f:
                    if line.startswith('>'):
                        chromosomes.append(line.strip().split()[0][1:])
        except Exception as e:
            logger.error(f"解析基因组文件失败: {str(e)}")
            return Response(
                {"error": f"解析基因组文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(chromosomes)

    @action(detail=False, methods=['get'])
    def get_chromosome_length(self, request):
        """获取指定上下文和染色体的实际长度"""
        organism = request.query_params.get('organism')
        accession = request.query_params.get('accession')
        assembly_id = request.query_params.get('assembly_id')
        chromosome = request.query_params.get('chromosome')

        if not organism and not accession and not assembly_id:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        _, _, genome_file = get_context_genome_file(
            assembly_id=assembly_id,
            accession=accession,
            organism=organism,
        )

        if not genome_file:
            return Response(
                {"error": f"未找到 {organism or accession or assembly_id} 的基因组文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            from Bio import SeqIO
            import gzip

            if genome_file.file_path.endswith('.gz'):
                with gzip.open(genome_file.file_path, 'rt') as f:
                    for record in SeqIO.parse(f, "fasta"):
                        if record.id == chromosome:
                            return Response({"length": len(record.seq)})
            else:
                with open(genome_file.file_path, 'r') as f:
                    for record in SeqIO.parse(f, "fasta"):
                        if record.id == chromosome:
                            return Response({"length": len(record.seq)})

            return Response(
                {"error": f"在基因组文件中未找到染色体 {chromosome}"},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            logger.error(f"解析基因组文件获取染色体长度失败: {str(e)}")
            return Response(
                {"error": f"解析基因组文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _compat_get_tes_context(self, request):
        resolved_organism, _, _, _ = self._resolve_request_organism(request)
        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        request._request.GET = request._request.GET.copy()
        request._request.GET['organism'] = resolved_organism
        return resolved_organism

    def _compat_get_centromere_context(self, request):
        resolved_organism, _, _, _ = self._resolve_request_organism(request)
        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        request._request.GET = request._request.GET.copy()
        request._request.GET['organism'] = resolved_organism
        return resolved_organism

    def _compat_get_coreblocks_context(self, request):
        resolved_organism, _, _, _ = self._resolve_request_organism(request)
        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        request._request.GET = request._request.GET.copy()
        request._request.GET['organism'] = resolved_organism
        return resolved_organism

    @action(detail=False, methods=['get'])
    def get_annotation_data(self, request):
        """获取指定上下文的注释数据"""
        resolved_organism, annotation_file_path = self._resolve_annotation_file_path(request)
        chromosome = request.query_params.get('chromosome')
        feature_type = request.query_params.get('feature_type', 'all')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))

        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not annotation_file_path:
            return Response(
                {"error": f"未找到 {resolved_organism} 的注释文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        annotation_data = []
        total_count = 0
        chromosomes = set()
        feature_types = set()

        try:
            with open(annotation_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split('\t')
                    if len(parts) < 9:
                        continue

                    seqid = parts[0]
                    source = parts[1]
                    feature = parts[2]
                    start = int(parts[3])
                    end = int(parts[4])
                    score = parts[5] if parts[5] != '.' else None
                    strand = parts[6]
                    phase = parts[7] if parts[7] != '.' else None
                    attributes = parts[8]

                    chromosomes.add(seqid)
                    feature_types.add(feature)

                    if chromosome and seqid != chromosome:
                        continue
                    if feature_type != 'all' and feature != feature_type:
                        continue

                    total_count += 1
                    if total_count <= (page - 1) * page_size:
                        continue
                    if len(annotation_data) >= page_size:
                        continue

                    attr_dict = {}
                    for attr in attributes.split(';'):
                        if '=' in attr:
                            key, value = attr.split('=', 1)
                            attr_dict[key] = value

                    annotation_data.append({
                        'seqid': seqid,
                        'source': source,
                        'feature': feature,
                        'start': start,
                        'end': end,
                        'length': end - start + 1,
                        'score': score,
                        'strand': strand,
                        'phase': phase,
                        'attributes': attr_dict,
                        'line_number': line_num
                    })

        except Exception as e:
            logger.error(f"解析注释文件失败: {str(e)}")
            return Response(
                {"error": f"解析注释文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'results': annotation_data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'statistics': {
                'chromosomes': sorted(list(chromosomes)),
                'feature_types': sorted(list(feature_types)),
                'total_features': total_count
            }
        })

    def _compat_get_rna_context(self, request):
        resolved_organism, _, _, _ = self._resolve_request_organism(request)
        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        request._request.GET = request._request.GET.copy()
        request._request.GET['organism'] = resolved_organism
        return resolved_organism


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def admin_session(request):
    """Return the server-side administrator session state and issue a CSRF cookie."""
    user = request.user
    is_admin = bool(user and user.is_authenticated and user.is_staff)
    return Response({
        'success': True,
        'authenticated': is_admin,
        'user': {
            'username': user.get_username(),
            'is_staff': True,
            'is_superuser': bool(user.is_superuser),
        } if is_admin else None,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_protect
def admin_login(request):
    """管理员登录接口"""
    try:
        data = request.data if isinstance(request.data, dict) else {}
        username = data.get('username')
        password = data.get('password')

        user = authenticate(request=request._request, username=username, password=password)
        if not user or not user.is_active:
            return Response({
                'success': False,
                'message': '用户名或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_staff:
            return Response({
                'success': False,
                'message': '该账号没有管理员权限'
            }, status=status.HTTP_403_FORBIDDEN)

        django_login(request._request, user)
        return Response({
            'success': True,
            'user': {
                'username': user.get_username(),
                'is_staff': True,
                'is_superuser': bool(user.is_superuser),
            }
        })

    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return Response({
            'success': False,
            'message': '登录失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['GET'])
@permission_classes([AllowAny])
def admin_files_list(request):
    return _genomefile_archived_response()


@api_view(['DELETE'])
@permission_classes([AllowAny])
def admin_delete_file(request, file_id):
    return _genomefile_archived_response()


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_batch_delete(request):
    return _genomefile_archived_response()


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_batch_download(request):
    return _genomefile_archived_response(GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_upload_file(request):
    return _genomefile_archived_response()




@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_logout(request):
    django_logout(request._request)
    return Response({'success': True, 'message': '已退出登录'})


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_statistics(request):
    return _genomefile_archived_response()


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_rescan_files(request):
    return _genomefile_archived_response()


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_download_file(request, file_id):
    return _genomefile_archived_response(GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE)


# ==================== 数据表格管理API ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def admin_data_management_list(request):
    """获取数据表格列表（管理后台）"""
    try:
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')  # Accession搜索
        sub_populations = request.GET.get('sub_populations', '')  # SubPopulation筛选

        # 获取补充数据
        supplementary_data = {}
        try:
            manual_files_dir = settings.MANUAL_FILES_DIR
            supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

            if os.path.exists(supplementary_file):
                with open(supplementary_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 跳过标题行
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 5:
                            accession = parts[0].strip()
                            sub_population = parts[1].strip()
                            seq_data = parts[2].strip()
                            longitude = parts[3].strip()
                            latitude = parts[4].strip()

                            supplementary_data[accession] = {
                                'sub_population': sub_population if sub_population != '-' else None,
                                'seq_data': seq_data if seq_data != '-' else None,
                                'longitude': float(longitude) if longitude != '-' else None,
                                'latitude': float(latitude) if latitude != '-' else None
                            }
        except Exception as e:
            logger.warning(f"读取补充数据失败: {str(e)}")

        # 获取所有accession
        all_accessions = list(supplementary_data.keys())

        # Accession搜索过滤
        if search:
            all_accessions = [acc for acc in all_accessions if search.lower() in acc.lower()]

        # SubPopulation筛选
        if sub_populations:
            if sub_populations == 'NONE':
                # 如果传入NONE，返回空结果
                all_accessions = []
            else:
                # 解析多个亚群（逗号分隔）
                selected_sub_pops = [sp.strip() for sp in sub_populations.split(',') if sp.strip()]
                if selected_sub_pops:
                    filtered_accessions = []
                    for acc in all_accessions:
                        acc_data = supplementary_data.get(acc, {})
                        acc_sub_pop = acc_data.get('sub_population', '-')
                        # 处理None值
                        if acc_sub_pop is None:
                            acc_sub_pop = '-'
                        if acc_sub_pop in selected_sub_pops:
                            filtered_accessions.append(acc)
                    all_accessions = filtered_accessions

        # 分页
        total_count = len(all_accessions)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_accessions = all_accessions[start_index:end_index]

        # 构建结果
        results = []
        for accession in paginated_accessions:
            data = supplementary_data.get(accession, {})

            # 检查文件存在性并获取文件名
            manual_files_dir = settings.MANUAL_FILES_DIR

            # 查找文件并获取文件名
            def find_file(patterns):
                for pattern in patterns:
                    file_path = os.path.join(manual_files_dir, pattern)
                    if os.path.exists(file_path):
                        return os.path.basename(file_path)
                return None

            file_info = {
                'genomeFile': find_file([f'genome.{accession}.{ext}' for ext in ['fasta', 'fa', 'fas']]),
                'annotationFile': find_file([f'annotation.{accession}.gff', f'annotation.{accession}.gff3']),
                'transcriptomeAllFile': find_file([f'transcriptome.all.{accession}.tar.gz']),
                'transcriptomeLeafFile': find_file([f'transcriptome.leaf.{accession}.tar.gz']),
                'transcriptomePaniclesFile': find_file([f'transcriptome.panicles.{accession}.tar.gz']),
                'transcriptomeShootFile': find_file([f'transcriptome.shoot.{accession}.tar.gz']),
                'transcriptomeStemFile': find_file([f'transcriptome.stem.{accession}.tar.gz']),
                'transcriptomeRootFile': find_file([f'transcriptome.root.{accession}.tar.gz']),
                'codonFile': find_file([f'codon.{accession}.tar.gz']),
                'centromereFile': find_file([f'centromere.{accession}.bed']),
                'tesFile': find_file([f'TEs.{accession}.tar.gz']),
                'coreBlocksFile': find_file([f'coreBlocks.{accession}.bed']),
                'miRNAFile': find_file([f'miRNA.{accession}.bed']),
                'tRNAFile': find_file([f'tRNA.{accession}.bed']),
                'rRNAFile': find_file([f'rRNA.{accession}.bed']),
            }

            # 保持原有的布尔值检查（向后兼容）
            file_checks = {
                'hasGenome': file_info['genomeFile'] is not None,
                'hasAnnotation': file_info['annotationFile'] is not None,
                'hasTranscriptomeAll': file_info['transcriptomeAllFile'] is not None,
                'hasTranscriptomeLeaf': file_info['transcriptomeLeafFile'] is not None,
                'hasTranscriptomePanicles': file_info['transcriptomePaniclesFile'] is not None,
                'hasTranscriptomeShoot': file_info['transcriptomeShootFile'] is not None,
                'hasTranscriptomeStem': file_info['transcriptomeStemFile'] is not None,
                'hasTranscriptomeRoot': file_info['transcriptomeRootFile'] is not None,
                'hasCodon': file_info['codonFile'] is not None,
                'hasCentromere': file_info['centromereFile'] is not None,
                'hasTEs': file_info['tesFile'] is not None,
                'hasCoreBlocks': file_info['coreBlocksFile'] is not None,
                'hasmiRNA': file_info['miRNAFile'] is not None,
                'hastRNA': file_info['tRNAFile'] is not None,
                'hasrRNA': file_info['rRNAFile'] is not None,
            }

            # 调试信息：记录文件检查结果
            if accession == 'IR64':  # 只为IR64记录详细信息，避免日志过多
                logger.info(f"检查 {accession} 的文件状态:")
                for check_name, result in file_checks.items():
                    logger.info(f"  {check_name}: {result}")
                logger.info(f"  manual_files_dir: {manual_files_dir}")
                # 列出实际存在的相关文件
                import glob
                related_files = glob.glob(os.path.join(manual_files_dir, f'*{accession}*'))
                logger.info(f"  实际相关文件: {[os.path.basename(f) for f in related_files]}")

            result = {
                'accession': accession,
                'subPopulation': data.get('sub_population') or '-',
                'seqData': data.get('seq_data') or '-',
                'longitude': data.get('longitude'),
                'latitude': data.get('latitude'),
                **file_checks,
                **file_info
            }
            results.append(result)

        return Response({
            'success': True,
            'data': results,
            'total': total_count,
            'page': page,
            'page_size': page_size
        })

    except Exception as e:
        logger.error(f"获取数据列表失败: {str(e)}")
        return Response({
            'success': False,
            'message': '获取数据列表失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_create_accession(request):
    """新增Accession数据"""
    try:
        data = request.data if isinstance(request.data, dict) else {}
        accession = data.get('accession', '').strip()
        sub_population = data.get('subPopulation', '-').strip()
        seq_data = data.get('seqData', '-').strip()
        longitude = data.get('longitude')
        latitude = data.get('latitude')

        if not accession:
            return Response({
                'success': False,
                'message': 'Accession不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 读取现有数据
        manual_files_dir = settings.MANUAL_FILES_DIR
        supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

        lines = []
        accession_exists = False

        if os.path.exists(supplementary_file):
            with open(supplementary_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 检查是否已存在
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and line.split('\t')[0].strip() == accession:
                    accession_exists = True
                    break
        else:
            # 创建文件头
            lines = ['Accession\tSubPopulation\tSeqData\tlongitude\tlatitude\n']

        if accession_exists:
            return Response({
                'success': False,
                'message': f'Accession "{accession}" 已存在'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 添加新行
        longitude_str = str(longitude) if longitude is not None else '-'
        latitude_str = str(latitude) if latitude is not None else '-'
        new_line = f"{accession}\t{sub_population}\t{seq_data}\t{longitude_str}\t{latitude_str}\n"
        lines.append(new_line)

        # 写回文件
        with open(supplementary_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return Response({
            'success': True,
            'message': '新增成功'
        })

    except Exception as e:
        logger.error(f"新增Accession失败: {str(e)}")
        return Response({
            'success': False,
            'message': '新增失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_update_accession(request, accession):
    """更新Accession数据"""
    try:
        data = request.data if isinstance(request.data, dict) else {}
        sub_population = data.get('subPopulation', '-').strip()
        seq_data = data.get('seqData', '-').strip()
        longitude = data.get('longitude')
        latitude = data.get('latitude')

        # 读取现有数据
        manual_files_dir = settings.MANUAL_FILES_DIR
        supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

        if not os.path.exists(supplementary_file):
            return Response({
                'success': False,
                'message': '数据文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        lines = []
        found = False

        with open(supplementary_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 更新对应行
        for i, line in enumerate(lines):
            if i == 0:  # 跳过标题行
                continue
            if line.strip() and line.split('\t')[0].strip() == accession:
                longitude_str = str(longitude) if longitude is not None else '-'
                latitude_str = str(latitude) if latitude is not None else '-'
                lines[i] = f"{accession}\t{sub_population}\t{seq_data}\t{longitude_str}\t{latitude_str}\n"
                found = True
                break

        if not found:
            return Response({
                'success': False,
                'message': f'Accession "{accession}" 不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        # 写回文件
        with open(supplementary_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return Response({
            'success': True,
            'message': '更新成功'
        })

    except Exception as e:
        logger.error(f"更新Accession失败: {str(e)}")
        return Response({
            'success': False,
            'message': '更新失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_delete_accession(request, accession):
    """删除Accession数据"""
    try:
        # 读取现有数据
        manual_files_dir = settings.MANUAL_FILES_DIR
        supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

        if not os.path.exists(supplementary_file):
            return Response({
                'success': False,
                'message': '数据文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        lines = []
        found = False

        with open(supplementary_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 删除对应行
        new_lines = [lines[0]]  # 保留标题行
        for i, line in enumerate(lines):
            if i == 0:  # 跳过标题行
                continue
            if line.strip() and line.split('\t')[0].strip() == accession:
                found = True
                continue  # 跳过这一行，即删除
            new_lines.append(line)

        if not found:
            return Response({
                'success': False,
                'message': f'Accession "{accession}" 不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        # 写回文件
        with open(supplementary_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 删除相关文件
        file_patterns = [
            f'genome.{accession}.*',
            f'annotation.{accession}.*',
            f'codon.{accession}.*',
            f'centromere.{accession}.*',
            f'TEs.{accession}.*',
            f'coreBlocks.{accession}.*',
            f'miRNA.{accession}.*',
            f'tRNA.{accession}.*',
            f'rRNA.{accession}.*',
            f'transcriptome.*.{accession}.*'
        ]

        deleted_files = []
        for pattern in file_patterns:
            import glob
            matching_files = glob.glob(os.path.join(manual_files_dir, pattern))
            for file_path in matching_files:
                try:
                    os.remove(file_path)
                    deleted_files.append(os.path.basename(file_path))
                except Exception as e:
                    logger.warning(f"删除文件失败 {file_path}: {str(e)}")

        return Response({
            'success': True,
            'message': f'删除成功，同时删除了 {len(deleted_files)} 个相关文件',
            'deleted_files': deleted_files
        })

    except Exception as e:
        logger.error(f"删除Accession失败: {str(e)}")
        return Response({
            'success': False,
            'message': '删除失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_batch_delete_accessions(request):
    """批量删除Accession数据"""
    try:
        data = request.data if isinstance(request.data, dict) else {}
        accessions = data.get('accessions', [])

        if not accessions:
            return Response({
                'success': False,
                'message': '请提供要删除的Accession列表'
            }, status=status.HTTP_400_BAD_REQUEST)

        manual_files_dir = settings.MANUAL_FILES_DIR
        supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

        if not os.path.exists(supplementary_file):
            return Response({
                'success': False,
                'message': '数据文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        # 读取现有数据
        lines = []
        with open(supplementary_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 过滤掉要删除的accessions
        new_lines = [lines[0]]  # 保留标题行
        deleted_accessions = []

        for i, line in enumerate(lines):
            if i == 0:  # 跳过标题行
                continue
            if line.strip():
                parts = line.strip().split('\t')
                if len(parts) > 0 and parts[0].strip() in accessions:
                    deleted_accessions.append(parts[0].strip())
                    continue  # 跳过这一行，即删除
            new_lines.append(line)

        if not deleted_accessions:
            return Response({
                'success': False,
                'message': '没有找到要删除的Accession'
            }, status=status.HTTP_404_NOT_FOUND)

        # 写回文件
        with open(supplementary_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 删除相关文件
        all_deleted_files = []
        for accession in deleted_accessions:
            file_patterns = [
                f'genome.{accession}.*',
                f'annotation.{accession}.*',
                f'codon.{accession}.*',
                f'centromere.{accession}.*',
                f'TEs.{accession}.*',
                f'coreBlocks.{accession}.*',
                f'miRNA.{accession}.*',
                f'tRNA.{accession}.*',
                f'rRNA.{accession}.*',
                f'transcriptome.*.{accession}.*'
            ]

            for pattern in file_patterns:
                import glob
                matching_files = glob.glob(os.path.join(manual_files_dir, pattern))
                for file_path in matching_files:
                    try:
                        os.remove(file_path)
                        all_deleted_files.append(os.path.basename(file_path))
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {str(e)}")

        return Response({
            'success': True,
            'message': f'成功删除 {len(deleted_accessions)} 个 Accession，同时删除了 {len(all_deleted_files)} 个相关文件',
            'deleted_accessions': deleted_accessions,
            'deleted_files': all_deleted_files
        })

    except Exception as e:
        logger.error(f"批量删除Accession失败: {str(e)}")
        return Response({
            'success': False,
            'message': '批量删除失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_upload_data_file(request):
    """上传数据文件"""
    try:
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'message': '请选择要上传的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['file']
        accession = request.POST.get('accession', '').strip()
        file_type = request.POST.get('fileType', '').strip()

        if not accession or not file_type:
            return Response({
                'success': False,
                'message': 'Accession和文件类型不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证文件类型和扩展名
        file_extensions = {
            'genome': ['.fasta', '.fa', '.fas'],
            'annotation': ['.gff', '.gff3'],
            'transcriptome.all': ['.tar.gz'],
            'transcriptome.leaf': ['.tar.gz'],
            'transcriptome.panicles': ['.tar.gz'],
            'transcriptome.shoot': ['.tar.gz'],
            'transcriptome.stem': ['.tar.gz'],
            'transcriptome.root': ['.tar.gz'],
            'codon': ['.tar.gz'],
            'centromere': ['.bed'],
            'TEs': ['.tar.gz'],
            'coreBlocks': ['.bed'],
            'miRNA': ['.bed'],
            'tRNA': ['.bed'],
            'rRNA': ['.bed']
        }

        if file_type not in file_extensions:
            return Response({
                'success': False,
                'message': f'不支持的文件类型: {file_type}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查文件扩展名
        filename = uploaded_file.name.lower()
        valid_extensions = file_extensions[file_type]

        if not any(filename.endswith(ext) for ext in valid_extensions):
            return Response({
                'success': False,
                'message': f'{file_type} 文件必须是以下格式之一: {", ".join(valid_extensions)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 构建目标文件名
        manual_files_dir = settings.MANUAL_FILES_DIR
        if not os.path.exists(manual_files_dir):
            os.makedirs(manual_files_dir)

        # 根据文件类型确定文件扩展名
        if filename.endswith('.tar.gz'):
            file_extension = 'tar.gz'
        else:
            file_extension = filename.split('.')[-1]

        target_filename = f"{file_type}.{accession}.{file_extension}"
        target_path = os.path.join(manual_files_dir, target_filename)

        # 如果文件已存在，直接删除
        if os.path.exists(target_path):
            os.remove(target_path)
            logger.info(f"已删除现有文件: {target_path}")

        # 保存新文件
        with open(target_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        file_size = os.path.getsize(target_path)
        logger.info(f"文件上传成功: {target_filename}, 大小: {file_size} bytes")

        return Response({
            'success': True,
            'message': f'{file_type} 文件上传成功',
            'filename': target_filename,
            'size': file_size
        })

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'文件上传失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_download_data_file(request, accession, file_type):
    return _genomefile_archived_response(GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_delete_data_file(request, accession, file_type):
    """删除数据文件"""
    try:
        manual_files_dir = settings.MANUAL_FILES_DIR

        # 根据文件类型查找文件
        file_patterns = {
            'genome': [f'genome.{accession}.fasta', f'genome.{accession}.fa', f'genome.{accession}.fas'],
            'annotation': [f'annotation.{accession}.gff', f'annotation.{accession}.gff3'],
            'transcriptome.all': [f'transcriptome.all.{accession}.tar.gz'],
            'transcriptome.leaf': [f'transcriptome.leaf.{accession}.tar.gz'],
            'transcriptome.panicles': [f'transcriptome.panicles.{accession}.tar.gz'],
            'transcriptome.shoot': [f'transcriptome.shoot.{accession}.tar.gz'],
            'transcriptome.stem': [f'transcriptome.stem.{accession}.tar.gz'],
            'transcriptome.root': [f'transcriptome.root.{accession}.tar.gz'],
            'codon': [f'codon.{accession}.tar.gz'],
            'centromere': [f'centromere.{accession}.bed'],
            'TEs': [f'TEs.{accession}.tar.gz'],
            'coreBlocks': [f'coreBlocks.{accession}.bed'],
            'miRNA': [f'miRNA.{accession}.bed'],
            'tRNA': [f'tRNA.{accession}.bed'],
            'rRNA': [f'rRNA.{accession}.bed']
        }

        if file_type not in file_patterns:
            return Response({
                'success': False,
                'message': f'不支持的文件类型: {file_type}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 查找并删除文件
        deleted_files = []
        for pattern in file_patterns[file_type]:
            file_path = os.path.join(manual_files_dir, pattern)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files.append(os.path.basename(file_path))
                    logger.info(f"删除文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除文件失败 {file_path}: {str(e)}")

        if not deleted_files:
            return Response({
                'success': False,
                'message': f'未找到 {accession} 的 {file_type} 文件'
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'message': f'成功删除 {len(deleted_files)} 个文件',
            'deleted_files': deleted_files
        })

    except Exception as e:
        logger.error(f"文件删除失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'文件删除失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_subpopulation_stats(request):
    """获取亚群统计信息"""
    try:
        # 获取补充数据
        supplementary_data = {}
        manual_files_dir = settings.MANUAL_FILES_DIR
        supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

        if os.path.exists(supplementary_file):
            with open(supplementary_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 跳过标题行
            for line in lines[1:]:
                line = line.strip()
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 5:
                        accession = parts[0].strip()
                        sub_population = parts[1].strip()

                        supplementary_data[accession] = {
                            'sub_population': sub_population if sub_population != '-' else '未知',
                        }

        # 统计每个亚群的数据
        subpop_stats = {}

        for accession, data in supplementary_data.items():
            sub_pop = data['sub_population']

            if sub_pop not in subpop_stats:
                subpop_stats[sub_pop] = {
                    'subpopulation': sub_pop,
                    'accession_count': 0,
                    'file_count': 0,
                    'total_size': 0
                }

            subpop_stats[sub_pop]['accession_count'] += 1

            # 统计该accession的文件数量和大小
            file_patterns = [
                f'genome.{accession}.*',
                f'annotation.{accession}.*',
                f'codon.{accession}.*',
                f'centromere.{accession}.*',
                f'TEs.{accession}.*',
                f'coreBlocks.{accession}.*',
                f'miRNA.{accession}.*',
                f'tRNA.{accession}.*',
                f'rRNA.{accession}.*',
                f'transcriptome.*.{accession}.*'
            ]

            import glob
            for pattern in file_patterns:
                matching_files = glob.glob(os.path.join(manual_files_dir, pattern))
                for file_path in matching_files:
                    if os.path.exists(file_path):
                        subpop_stats[sub_pop]['file_count'] += 1
                        try:
                            file_size = os.path.getsize(file_path)
                            subpop_stats[sub_pop]['total_size'] += file_size
                        except Exception as e:
                            logger.warning(f"获取文件大小失败 {file_path}: {str(e)}")

        # 转换为列表并排序
        result = list(subpop_stats.values())
        result.sort(key=lambda x: x['accession_count'], reverse=True)

        return Response({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"获取亚群统计失败: {str(e)}")
        return Response({
            'success': False,
            'message': '获取亚群统计失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def accession_detail(request, accession):
    """获取单个 accession 的层级详情信息"""
    try:
        accession_obj = Accession.objects.filter(accession=accession).first()

        if not accession_obj:
            return Response({
                'success': False,
                'message': f'Accession "{accession}" 不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        assemblies = filter_visible_assemblies(
            accession_obj.assemblies.all().order_by('-is_default', 'name', 'id')
        )
        annotation_map = {}
        for assembly in assemblies:
            assembly.prefetched_file_relations = []
            assembly.prefetched_annotations = list(
                assembly.annotations.all().order_by('-is_default', 'name', 'id')
            )
            for annotation in assembly.prefetched_annotations:
                annotation.prefetched_file_relations = []
                annotation_map[annotation.id] = annotation

        assembly_map = {assembly.id: assembly for assembly in assemblies}
        context_error = None
        try:
            default_assembly = resolve_preferred_assembly(accession_obj)
        except AmbiguousContextError as exc:
            default_assembly = None
            default_annotation = None
            context_error = {
                'code': exc.code,
                'related_type': exc.related_type,
                'parent': exc.parent_code,
                'message': str(exc),
            }
        else:
            try:
                default_annotation = resolve_preferred_annotation(default_assembly)
            except AmbiguousContextError as exc:
                default_annotation = None
                context_error = {
                    'code': exc.code,
                    'related_type': exc.related_type,
                    'parent': exc.parent_code,
                    'message': str(exc),
                }

        files_data, hierarchy_relations = _build_accession_file_inventory(
            accession_obj,
            assemblies,
        )

        for relation in hierarchy_relations:
            try:
                related_id = int(relation.related_id)
            except (TypeError, ValueError):
                continue
            if relation.related_type == 'assembly' and related_id in assembly_map:
                assembly_map[related_id].prefetched_file_relations.append(relation)
            elif relation.related_type == 'annotation' and related_id in annotation_map:
                annotation_map[related_id].prefetched_file_relations.append(relation)

        for assembly in assemblies:
            for annotation in assembly.prefetched_annotations:
                annotation_relations = getattr(annotation, 'prefetched_file_relations', []) or []
                annotation_source_relation = next(
                    (
                        relation for relation in annotation_relations
                        if relation.file_role == 'annotation' and relation.file.file_path
                    ),
                    None,
                )

                annotation_file_path = (
                    annotation_source_relation.file.file_path
                    if annotation_source_relation else None
                )

                annotation.summary_metadata = _parse_annotation_summary(annotation_file_path)

        accession_obj.prefetched_assemblies = assemblies
        detail_data = AccessionDetailSerializer(accession_obj).data
        assemblies_data = detail_data.pop('assemblies', [])
        species = accession_obj.species
        detail_data['species'] = {
            'id': species.id,
            'species_code': species.species_code,
            'scientific_name': species.scientific_name,
            'chinese_name': species.chinese_name,
            'common_name': species.common_name,
        } if species else None

        relation_counts = {}
        for relation in hierarchy_relations:
            relation_counts[(relation.related_type, relation.related_id)] = (
                relation_counts.get((relation.related_type, relation.related_id), 0) + 1
            )
        for assembly_data in assemblies_data:
            assembly_id = str(assembly_data.get('id'))
            assembly_data['file_count'] = relation_counts.get(('assembly', assembly_id), 0)
            for annotation_data in assembly_data.get('annotations', []):
                annotation_id = str(annotation_data.get('id'))
                annotation_data['file_count'] = relation_counts.get(
                    ('annotation', annotation_id),
                    0,
                )

        file_status, file_names = _build_compatibility_file_summary(
            files_data,
            default_assembly_id=default_assembly.id if default_assembly else None,
            default_annotation_id=default_annotation.id if default_annotation else None,
        )

        total_annotation_count = sum(len(assembly.prefetched_annotations) for assembly in assemblies)
        total_size = sum(int(item.get('file_size') or 0) for item in files_data)
        datasets_by_id = {}
        projects_by_id = {}
        for relation in hierarchy_relations:
            dataset = relation.file.dataset
            if not dataset:
                continue
            datasets_by_id[dataset.id] = {
                'id': dataset.id,
                'dataset_code': dataset.dataset_code,
                'dataset_name': dataset.dataset_name,
                'dataset_type': dataset.dataset_type,
                'version': dataset.version,
                'visibility': dataset.visibility,
                'status': dataset.status,
            }
            project = dataset.project
            if project:
                projects_by_id[project.id] = {
                    'id': project.id,
                    'project_code': project.project_code,
                    'project_name': project.project_name,
                    'owner': project.owner,
                    'status': project.status,
                }

        file_roles = {relation.file_role.lower() for relation in hierarchy_relations if relation.file_role}
        dataset_types = {
            item['dataset_type']
            for item in datasets_by_id.values()
            if item.get('dataset_type')
        }

        def readiness(*keywords):
            return 'ready' if any(
                any(keyword in value for keyword in keywords)
                for value in file_roles | dataset_types
            ) else 'unavailable'

        projects = sorted(projects_by_id.values(), key=lambda item: item['project_code'])
        datasets = sorted(datasets_by_id.values(), key=lambda item: item['dataset_code'])

        return Response({
            'success': True,
            'data': {
                'accession': detail_data,
                'assemblies': assemblies_data,
                'summary': {
                    'assembly_count': len(assemblies),
                    'annotation_count': total_annotation_count,
                    'file_count': len(files_data),
                    'sample_count': Sample.objects.filter(accession=accession_obj).count(),
                    'dataset_count': len(datasets),
                    'total_size': total_size,
                    'total_size_display': _format_file_size(total_size),
                    'default_assembly_id': default_assembly.id if default_assembly else None,
                    'default_annotation_id': default_annotation.id if default_annotation else None,
                    'context_status': 'ambiguous' if context_error else ('resolved' if default_assembly else 'unavailable'),
                    'context_error': context_error,
                },
                'projects': projects,
                'datasets': datasets,
                'data_status': {
                    'genome': readiness('genome', 'fasta'),
                    'annotation': readiness('annotation', 'gff', 'gtf'),
                    'transcriptome': readiness('transcriptome', 'rna', 'expression'),
                    'population': readiness('population', 'variant', 'vcf'),
                },
                'audit': {
                    'created_at': accession_obj.created_at,
                    'updated_at': accession_obj.updated_at,
                    'created_by': next(
                        (item['owner'] for item in projects if item.get('owner')),
                        None,
                    ),
                },
                # Compatibility-only flat view for old callers.
                'files': files_data,
                'file_count': len(files_data),
                'file_status': file_status,
                'file_names': file_names,
            }
        })

    except Exception as e:
        logger.error(f"获取 accession 详情失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'获取 accession 详情失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

