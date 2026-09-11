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
from django.db.models import Prefetch, Q
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from functools import lru_cache
from .models import (
    FileType,
    GenomeFile,
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
    FileTypeSerializer, GenomeFileSerializer, GenomeFileListSerializer,
    OrganismSerializer, FileCategorySerializer,
    AccessionSerializer, AccessionDetailSerializer, AccessionGenomeFileSerializer
)
from .services.accession_context import (
    AmbiguousContextError,
    classify_file_scope,
    get_context_genome_file,
    get_context_organism,
    resolve_preferred_annotation,
    resolve_preferred_assembly,
)
from .services.file_relation_service import get_files_for_accession, get_files_for_annotation
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
    for category_code, _ in GenomeFile.FILE_CATEGORY_CHOICES:
        matched_files = [item for item in compatibility_files if item['category'] == category_code]
        status_key = category_code.replace('.', '_')
        file_status[status_key] = len(matched_files) > 0
        file_names[status_key] = matched_files[0]['name'] if matched_files else None

    return file_status, file_names


def _adapt_accession_file_service_result(service_file, accession_obj, legacy_files_by_path=None):
    legacy_files_by_path = legacy_files_by_path or {}
    legacy_file = legacy_files_by_path.get(service_file.get('file_path'))
    category = service_file.get('file_role')
    file_size = service_file.get('file_size')
    is_new_relation = service_file.get('source') == 'new_relation'
    datafile_download_url = _datafile_download_url(service_file.get('file_id')) if is_new_relation else None

    return {
        'id': service_file.get('file_id'),
        'name': service_file.get('file_name'),
        'organism': accession_obj.accession,
        'category': category,
        'file_type_name': legacy_file.file_type.name if legacy_file and legacy_file.file_type else None,
        'file_path': service_file.get('file_path'),
        'size': file_size,
        'file_size': file_size,
        'created_at': legacy_file.created_at if legacy_file else None,
        'accession_id': accession_obj.id,
        'assembly_id': legacy_file.assembly_id if legacy_file else None,
        'annotation_id': legacy_file.annotation_id if legacy_file else None,
        'scope': classify_file_scope(category),
        'source': service_file.get('source'),
        'file_code': service_file.get('file_code'),
        'md5': service_file.get('md5'),
        'datafile_download_url': datafile_download_url,
        'download_url': datafile_download_url,
    }


def _adapt_annotation_file_service_result(service_file):
    file_path = service_file.get('file_path')
    is_new_relation = service_file.get('source') == 'new_relation'
    datafile_download_url = _datafile_download_url(service_file.get('file_id')) if is_new_relation else None
    return {
        'id': service_file.get('file_id'),
        'name': service_file.get('file_name'),
        'file_path': file_path,
        'category': service_file.get('file_role'),
        'file_size': service_file.get('file_size'),
        'source': service_file.get('source'),
        'datafile_download_url': datafile_download_url,
        'download_url': datafile_download_url,
    }


def _adapt_overview_file_service_result(service_file):
    file_size = service_file.get('file_size')
    is_new_relation = service_file.get('source') == 'new_relation'
    datafile_download_url = _datafile_download_url(service_file.get('file_id')) if is_new_relation else None
    return {
        'id': service_file.get('file_id'),
        'name': service_file.get('file_name'),
        'file_path': service_file.get('file_path'),
        'category': service_file.get('file_role'),
        'size': file_size,
        'file_size': file_size,
        'created_at': None,
        'source': service_file.get('source'),
        'file_code': service_file.get('file_code'),
        'md5': service_file.get('md5'),
        'datafile_download_url': datafile_download_url,
        'download_url': datafile_download_url,
    }


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

class GenomeFileViewSet(viewsets.ModelViewSet):
    """Archived GenomeFile API.

    GenomeFile is retained only as a historical archive table. Standard CRUD
    and the old GenomeFile download endpoint are closed; use DataFile APIs for
    active file query, write and download paths.
    """
    queryset = GenomeFile._meta.default_manager.none()
    serializer_class = GenomeFileSerializer

    # 类变量，确保清理调度器只启动一次
    _cleanup_scheduler_started = False
    archive_message = GENOMEFILE_ARCHIVE_MESSAGE
    archive_download_message = GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE

    def _archived_response(self, message=None):
        return _genomefile_archived_response(message or self.archive_message)

    def list(self, request, *args, **kwargs):
        return self._archived_response()

    def retrieve(self, request, *args, **kwargs):
        return self._archived_response()

    def create(self, request, *args, **kwargs):
        return self._archived_response()

    def update(self, request, *args, **kwargs):
        return self._archived_response()

    def partial_update(self, request, *args, **kwargs):
        return self._archived_response()

    def destroy(self, request, *args, **kwargs):
        return self._archived_response()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 启动清理调度器（只启动一次）
        if not GenomeFileViewSet._cleanup_scheduler_started:
            GenomeFileViewSet._cleanup_scheduler_started = True
            self._start_cleanup_scheduler()

    def _parse_uploaded_codonw_results(self, extract_dir):
        """解析上传的CodonW结果文件"""
        try:
            # 查找.blk文件（密码子使用表）和.txt文件（统计信息）
            blk_files = []
            txt_files = []

            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    logger.info(f"检查文件: {file} -> {file_path}")
                    if file.endswith('.blk'):
                        blk_files.append(file_path)
                        logger.info(f"找到.blk文件: {file_path}")
                    elif file.endswith('.txt'):
                        txt_files.append(file_path)
                        logger.info(f"找到.txt文件: {file_path}")

            if not blk_files:
                logger.warning("未找到.blk文件")
                return None

            # 使用第一个找到的.blk文件
            blk_file = blk_files[0]
            organism_name = os.path.basename(blk_file).replace('.blk', '').replace('_codon_usage', '')

            # 解析.blk文件获取密码子使用数据
            codon_usage = self._parse_blk_file(blk_file)
            if not codon_usage:
                logger.error("解析.blk文件失败")
                return None

            # 转换密码子数据格式并按氨基酸分组
            formatted_codon_usage = self._format_codon_usage_data(codon_usage)
            amino_acids = self._group_by_amino_acid(formatted_codon_usage)

            # 构建基本返回数据
            codon_data = {
                'organism': organism_name,
                'codon_usage': formatted_codon_usage,
                'amino_acids': amino_acids,
                'total_codons': sum(data['count'] for data in codon_usage.values()),
                'nucleotide_composition': self._calculate_nucleotide_composition(codon_usage)
            }

            # 如果有.txt文件，解析统计信息
            if txt_files:
                txt_file = txt_files[0]  # 使用第一个找到的.txt文件
                statistics = self._parse_codonw_statistics_file(txt_file)
                if statistics:
                    codon_data['statistics'] = statistics
                    logger.info("成功解析统计信息")

            logger.info(f"成功解析CodonW结果，生物体: {organism_name}")
            return codon_data

        except Exception as e:
            logger.error(f"解析CodonW结果失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _format_codon_usage_data(self, codon_usage):
        """将简单的密码子使用数据转换为包含氨基酸信息的格式"""
        # 标准遗传密码表 - RNA密码子到氨基酸三字母缩写的映射
        codon_to_amino_acid = {
            # 丙氨酸 Ala
            'GCU': 'Ala', 'GCC': 'Ala', 'GCA': 'Ala', 'GCG': 'Ala',
            # 精氨酸 Arg
            'CGU': 'Arg', 'CGC': 'Arg', 'CGA': 'Arg', 'CGG': 'Arg', 'AGA': 'Arg', 'AGG': 'Arg',
            # 天冬酰胺 Asn
            'AAU': 'Asn', 'AAC': 'Asn',
            # 天冬氨酸 Asp
            'GAU': 'Asp', 'GAC': 'Asp',
            # 半胱氨酸 Cys
            'UGU': 'Cys', 'UGC': 'Cys',
            # 谷氨酸 Glu
            'GAA': 'Glu', 'GAG': 'Glu',
            # 谷氨酰胺 Gln
            'CAA': 'Gln', 'CAG': 'Gln',
            # 甘氨酸 Gly
            'GGU': 'Gly', 'GGC': 'Gly', 'GGA': 'Gly', 'GGG': 'Gly',
            # 组氨酸 His
            'CAU': 'His', 'CAC': 'His',
            # 异亮氨酸 Ile
            'AUU': 'Ile', 'AUC': 'Ile', 'AUA': 'Ile',
            # 亮氨酸 Leu
            'UUA': 'Leu', 'UUG': 'Leu', 'CUU': 'Leu', 'CUC': 'Leu', 'CUA': 'Leu', 'CUG': 'Leu',
            # 赖氨酸 Lys
            'AAA': 'Lys', 'AAG': 'Lys',
            # 甲硫氨酸 Met
            'AUG': 'Met',
            # 苯丙氨酸 Phe
            'UUU': 'Phe', 'UUC': 'Phe',
            # 脯氨酸 Pro
            'CCU': 'Pro', 'CCC': 'Pro', 'CCA': 'Pro', 'CCG': 'Pro',
            # 丝氨酸 Ser
            'UCU': 'Ser', 'UCC': 'Ser', 'UCA': 'Ser', 'UCG': 'Ser', 'AGU': 'Ser', 'AGC': 'Ser',
            # 苏氨酸 Thr
            'ACU': 'Thr', 'ACC': 'Thr', 'ACA': 'Thr', 'ACG': 'Thr',
            # 色氨酸 Trp
            'UGG': 'Trp',
            # 酪氨酸 Tyr
            'UAU': 'Tyr', 'UAC': 'Tyr',
            # 缬氨酸 Val
            'GUU': 'Val', 'GUC': 'Val', 'GUA': 'Val', 'GUG': 'Val',
            # 终止密码子 TER
            'UAA': 'TER', 'UAG': 'TER', 'UGA': 'TER'
        }

        formatted_data = {}
        # 计算总密码子数（从count值计算）
        total_codons = sum(data['count'] for data in codon_usage.values())

        for codon, data in codon_usage.items():
            amino_acid_name = codon_to_amino_acid.get(codon, 'Unknown')
            count = data['count']
            rscu = data['rscu']
            frequency = count / total_codons if total_codons > 0 else 0

            # 调试：记录终止密码子
            if codon in ['UAA', 'UAG', 'UGA']:
                logger.info(f"发现终止密码子: {codon} -> {amino_acid_name}, count={count}, rscu={rscu}")

            formatted_data[codon] = {
                'amino_acid': amino_acid_name,
                'codon': codon,
                'count': count,
                'frequency': rscu,  # RSCU值放在frequency字段
                'global_frequency': frequency,  # 全局频率
                'relative_frequency': rscu  # 临时设置，稍后在_group_by_amino_acid中会被正确的相对频率覆盖
            }

        return formatted_data

    def _parse_blk_file(self, blk_file_path):
        """解析.blk文件获取密码子使用数据"""
        try:
            logger.info(f"开始解析.blk文件: {blk_file_path}")
            codon_usage = {}

            with open(blk_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"文件内容长度: {len(content)} 字符")
            logger.info(f"文件内容前200字符: {content[:200]}")

            # 使用正则表达式匹配密码子、计数和RSCU值
            import re
            # 匹配模式：密码子(3个字母) + 数字 + 空格 + 小数(RSCU值)
            # 例如：UUU237493 0.78
            pattern = r'([AUGC]{3})(\d+)\s+([\d.]+)'

            matches = re.findall(pattern, content)
            logger.info(f"正则匹配到 {len(matches)} 个结果")

            # 打印前几个匹配结果用于调试
            for i, (codon, count_str, rscu_str) in enumerate(matches[:10]):
                logger.info(f"匹配 {i+1}: {codon} {count_str} {rscu_str}")

            for codon, count_str, rscu_str in matches:
                try:
                    # 保持RNA密码子格式（使用U），不转换为DNA
                    count = int(count_str)
                    rscu = float(rscu_str)

                    codon_usage[codon] = {
                        'count': count,
                        'rscu': rscu
                    }
                    logger.debug(f"解析密码子: {codon} -> count={count}, rscu={rscu}")
                except ValueError as ve:
                    logger.warning(f"解析密码子数据失败: {codon}, {count_str}, {rscu_str} - {ve}")
                    continue

            logger.info(f"成功解析到 {len(codon_usage)} 个密码子")
            if codon_usage:
                # 显示前几个密码子作为示例
                sample_codons = list(codon_usage.items())[:5]
                logger.info(f"示例密码子: {sample_codons}")

            return codon_usage if codon_usage else None

        except Exception as e:
            logger.error(f"解析.blk文件失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _parse_single_codonw_file(self, file_path):
        """解析单个CodonW结果文件（.blk或.txt）"""
        try:
            file_name = os.path.basename(file_path).lower()

            if file_name.endswith('.blk'):
                # 解析.blk文件
                codon_usage = self._parse_blk_file(file_path)
                if not codon_usage:
                    return None

                organism_name = os.path.basename(file_path).replace('.blk', '').replace('_codon_usage', '')

                return {
                    'organism': organism_name,
                    'codon_usage': codon_usage,
                    'total_codons': sum(codon_usage.values()),
                    'nucleotide_composition': self._calculate_nucleotide_composition(codon_usage)
                }

            elif file_name.endswith('.txt'):
                # 解析.txt文件 - 根据氨基酸-密码子对照表
                return self._parse_txt_file_with_amino_acids(file_path)

            return None

        except Exception as e:
            logger.error(f"解析单个CodonW文件失败: {str(e)}")
            return None

    def _parse_codonw_statistics_file(self, txt_file_path):
        """解析CodonW统计文件"""
        try:
            with open(txt_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if len(lines) < 2:
                logger.warning("统计文件内容不足")
                return None

            # 解析头部和数据行
            header_line = lines[0].strip()
            data_line = lines[1].strip()

            headers = header_line.split('\t')
            values = data_line.split('\t')

            if len(headers) != len(values):
                logger.warning("统计文件格式不匹配")
                return None

            # 构建统计数据字典
            statistics = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    try:
                        # 尝试转换为数字
                        value = float(values[i]) if '.' in values[i] else int(values[i])
                        statistics[header] = value
                    except ValueError:
                        # 如果不能转换为数字，保持字符串
                        statistics[header] = values[i]

            logger.info(f"解析到统计数据: {list(statistics.keys())}")
            return statistics

        except Exception as e:
            logger.error(f"解析统计文件失败: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"解析单个CodonW文件失败: {str(e)}")
            return None

    def _parse_txt_file_with_amino_acids(self, txt_file_path):
        """根据氨基酸-密码子对照表解析.txt文件"""
        try:
            # 氨基酸-密码子对照表
            codon_to_amino_acid = {
                'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
                'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
                'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
                'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
                'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
                'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
                'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
                'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
                'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
                'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
                'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
                'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
                'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
                'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
                'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
                'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G'
            }

            codon_usage = {}

            with open(txt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 使用正则表达式匹配密码子和计数
            import re
            # 匹配模式：密码子(3个字母) + 数字
            pattern = r'([ATGC]{3})(\d+)'

            matches = re.findall(pattern, content)

            for codon, count_str in matches:
                try:
                    count = int(count_str)
                    # 验证密码子是否有效
                    if codon in codon_to_amino_acid:
                        codon_usage[codon] = count
                except ValueError:
                    continue

            if not codon_usage:
                logger.warning("未从txt文件中解析到有效的密码子数据")
                return None

            organism_name = os.path.basename(txt_file_path).replace('.txt', '').replace('_codon_usage', '')

            return {
                'organism': organism_name,
                'codon_usage': codon_usage,
                'total_codons': sum(codon_usage.values()),
                'nucleotide_composition': self._calculate_nucleotide_composition(codon_usage)
            }

        except Exception as e:
            logger.error(f"解析txt文件失败: {str(e)}")
            return None

    def _calculate_nucleotide_composition(self, codon_usage):
        """计算核苷酸组成"""
        try:
            nucleotide_counts = {'A': 0, 'T': 0, 'G': 0, 'C': 0}
            total_nucleotides = 0

            for codon, data in codon_usage.items():
                # 处理新的数据结构：data可能是字典（包含count和rscu）或直接是count值
                count = data['count'] if isinstance(data, dict) else data

                for nucleotide in codon:
                    if nucleotide in nucleotide_counts:
                        nucleotide_counts[nucleotide] += count
                        total_nucleotides += count

            if total_nucleotides == 0:
                return nucleotide_counts

            # 计算百分比
            nucleotide_percentages = {}
            for nucleotide, count in nucleotide_counts.items():
                nucleotide_percentages[nucleotide] = (count / total_nucleotides) * 100

            return nucleotide_percentages

        except Exception as e:
            logger.error(f"计算核苷酸组成失败: {str(e)}")
            return {'A': 0, 'T': 0, 'G': 0, 'C': 0}


    
    def get_serializer_class(self):
        if self.action == 'list':
            return GenomeFileListSerializer
        return GenomeFileSerializer
    
    def get_queryset(self):
        return self.queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Archived legacy GenomeFile download endpoint."""
        return self._archived_response(self.archive_download_message)
    
    @action(detail=False, methods=['get'])
    def download_transcriptome(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_chromosomes(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_chromosome_length(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_chromosomes(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_chromosome_length(self, request):
        return self._archived_response()

    def get_tes(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_codon_data(self, request):
        return self._archived_response()


    def _parse_codon_usage(self, content):
        """解析密码子使用频率数据"""
        import re

        # 密码子到氨基酸的映射表
        codon_to_amino_acid = {
            # Phe
            'UUU': 'Phe', 'UUC': 'Phe',
            # Leu
            'UUA': 'Leu', 'UUG': 'Leu', 'CUU': 'Leu', 'CUC': 'Leu', 'CUA': 'Leu', 'CUG': 'Leu',
            # Ile
            'AUU': 'Ile', 'AUC': 'Ile', 'AUA': 'Ile',
            # Met
            'AUG': 'Met',
            # Val
            'GUU': 'Val', 'GUC': 'Val', 'GUA': 'Val', 'GUG': 'Val',
            # Ser
            'UCU': 'Ser', 'UCC': 'Ser', 'UCA': 'Ser', 'UCG': 'Ser', 'AGU': 'Ser', 'AGC': 'Ser',
            # Pro
            'CCU': 'Pro', 'CCC': 'Pro', 'CCA': 'Pro', 'CCG': 'Pro',
            # Thr
            'ACU': 'Thr', 'ACC': 'Thr', 'ACA': 'Thr', 'ACG': 'Thr',
            # Ala
            'GCU': 'Ala', 'GCC': 'Ala', 'GCA': 'Ala', 'GCG': 'Ala',
            # Tyr
            'UAU': 'Tyr', 'UAC': 'Tyr',
            # His
            'CAU': 'His', 'CAC': 'His',
            # Gln
            'CAA': 'Gln', 'CAG': 'Gln',
            # Asn
            'AAU': 'Asn', 'AAC': 'Asn',
            # Lys
            'AAA': 'Lys', 'AAG': 'Lys',
            # Asp
            'GAU': 'Asp', 'GAC': 'Asp',
            # Glu
            'GAA': 'Glu', 'GAG': 'Glu',
            # Cys
            'UGU': 'Cys', 'UGC': 'Cys',
            # Trp
            'UGG': 'Trp',
            # Arg
            'CGU': 'Arg', 'CGC': 'Arg', 'CGA': 'Arg', 'CGG': 'Arg', 'AGA': 'Arg', 'AGG': 'Arg',
            # Gly
            'GGU': 'Gly', 'GGC': 'Gly', 'GGA': 'Gly', 'GGG': 'Gly',
            # 终止密码子
            'UAA': 'TER', 'UAG': 'TER', 'UGA': 'TER'
        }

        codon_data = {}
        lines = content.strip().split('\n')

        for line in lines:
            if not line.strip() or 'codons in' in line:
                continue

            # 提取所有密码子数据的正则表达式
            # 匹配格式: 密码子+数字+空格+小数
            pattern = r'([AUGC]{3})(\d+)\s+([\d.]+)'
            matches = re.findall(pattern, line)

            for match in matches:
                codon, count, frequency = match

                # 根据密码子查找对应的氨基酸
                amino_acid = codon_to_amino_acid.get(codon, 'Unknown')

                codon_data[codon] = {
                    'amino_acid': amino_acid,
                    'codon': codon,
                    'count': int(count),
                    'frequency': float(frequency)
                }

        return codon_data

    def _group_by_amino_acid(self, codon_usage):
        """按氨基酸分组密码子数据"""
        amino_acids = {}

        for codon, data in codon_usage.items():
            aa = data['amino_acid']

            # 跳过未知的氨基酸，但保留终止密码子
            if aa == 'Unknown':
                continue

            if aa not in amino_acids:
                amino_acids[aa] = {
                    'name': aa,
                    'codons': [],
                    'total_count': 0
                }

            amino_acids[aa]['codons'].append(data)
            amino_acids[aa]['total_count'] += data['count']

        # 计算每个氨基酸内部的相对频率（该密码子使用次数/该氨基酸总使用次数）
        for aa_data in amino_acids.values():
            total_count = aa_data['total_count']
            for codon_data in aa_data['codons']:
                if total_count > 0:
                    # 相对频率 = 该密码子使用次数 / 该氨基酸总使用次数
                    codon_data['relative_frequency'] = codon_data['count'] / total_count
                else:
                    codon_data['relative_frequency'] = 0

        return amino_acids

    def _parse_codon_statistics(self, content):
        """解析密码子统计数据"""
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return {}

        headers = lines[0].split('\t')
        values = lines[1].split('\t')

        stats = {}
        for i, header in enumerate(headers):
            if i < len(values):
                try:
                    # 尝试转换为数字
                    value = float(values[i])
                    stats[header.strip()] = value
                except ValueError:
                    stats[header.strip()] = values[i].strip()

        return stats

    @action(detail=False, methods=['get'])
    def get_centromere(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_coreblocks(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_variableblocks(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def get_annotation_data(self, request):
        """获取指定生物体的注释数据"""
        organism = request.query_params.get('organism')
        accession = request.query_params.get('accession')
        assembly_id = request.query_params.get('assembly_id')
        annotation_id = request.query_params.get('annotation_id')
        chromosome = request.query_params.get('chromosome')
        feature_type = request.query_params.get('feature_type', 'all')  # gene, mRNA, exon, CDS, all
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))

        resolved_organism, _, resolved_assembly, resolved_annotation = get_context_organism(
            annotation_id=annotation_id,
            assembly_id=assembly_id,
            accession=accession,
            organism=organism,
        )

        if not resolved_organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        annotation_file_path = None
        annotation_file_info = None

        if resolved_annotation:
            annotation_files = get_files_for_annotation(resolved_annotation.id, file_role='annotation')
            for annotation_file in annotation_files:
                candidate_path = annotation_file.get('file_path')
                if candidate_path and os.path.exists(candidate_path):
                    annotation_file_path = candidate_path
                    annotation_file_info = _adapt_annotation_file_service_result(annotation_file)
                    break

        if not annotation_file_path or not os.path.exists(annotation_file_path):
            return Response(
                {"error": f"未找到 {resolved_organism} 的注释文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析GFF文件获取注释数据
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

                    # 收集统计信息
                    chromosomes.add(seqid)
                    feature_types.add(feature)

                    # 应用过滤条件
                    if chromosome and seqid != chromosome:
                        continue

                    if feature_type != 'all' and feature != feature_type:
                        continue

                    total_count += 1

                    # 分页处理
                    if total_count <= (page - 1) * page_size:
                        continue
                    if len(annotation_data) >= page_size:
                        continue

                    # 解析attributes字段
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

        # 返回分页结果和统计信息
        return Response({
            'results': annotation_data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'annotation_file': annotation_file_info,
            'statistics': {
                'chromosomes': sorted(list(chromosomes)),
                'feature_types': sorted(list(feature_types)),
                'total_features': total_count
            }
        })

    @action(detail=False, methods=['get'])
    def get_rna_data(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def scan_directory(self, request):
        return self._archived_response()


    def _load_supplementary_data(self):
        """加载补充数据文件"""
        try:
            manual_files_dir = settings.MANUAL_FILES_DIR
            supplementary_file = os.path.join(manual_files_dir, 'supplymentary_data.txt')

            supplementary_data = {}

            if os.path.exists(supplementary_file):
                with open(supplementary_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 跳过标题行
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 5:  # 现在需要至少5列：Accession, SubPopulation, SeqData, longitude, latitude
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
                        elif len(parts) >= 3:  # 兼容旧格式（只有3列）
                            accession = parts[0].strip()
                            sub_population = parts[1].strip()
                            seq_data = parts[2].strip()

                            supplementary_data[accession] = {
                                'sub_population': sub_population if sub_population != '-' else None,
                                'seq_data': seq_data if seq_data != '-' else None,
                                'longitude': None,
                                'latitude': None
                            }

            return supplementary_data
        except Exception as e:
            print(f"加载补充数据失败: {str(e)}")
            return {}

    @action(detail=False, methods=['get'])
    def organisms(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def organisms_with_annotation(self, request):
        return self._archived_response()


    @method_decorator(csrf_exempt, name='dispatch')
    @action(detail=False, methods=['post'])
    def codonw_analysis(self, request):
        """CodonW分析接口 - 支持基因组分析和CDS分析两种模式"""
        try:
            logger.info(f"收到CodonW分析请求: {request.method}")
            logger.info(f"请求文件: {list(request.FILES.keys())}")
            logger.info(f"请求数据: {request.data}")

            if 'file' not in request.FILES:
                logger.error("请求中没有文件")
                return Response(
                    {"error": "没有上传文件"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            uploaded_file = request.FILES['file']

            # 获取分析类型和文件类型
            analysis_type = request.data.get('analysis_type', 'cds')  # 'genomic' 或 'cds'
            file_type = request.data.get('file_type', 'cds')  # 'genome', 'gff', 'cds'

            logger.info(f"分析类型: {analysis_type}, 文件类型: {file_type}")

            # 根据文件类型验证文件格式
            if file_type == 'genome':
                allowed_extensions = ['.fasta', '.fa', '.fas', '.fna']
                error_msg = "请上传FASTA格式的基因组文件"
            elif file_type == 'gff':
                allowed_extensions = ['.gff', '.gff3']
                error_msg = "请上传GFF格式的注释文件"
            else:  # cds
                allowed_extensions = ['.fasta', '.fa', '.fas', '.fna', '.txt']
                error_msg = "请上传FASTA格式的CDS文件"

            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                return Response(
                    {"error": f"不支持的文件格式。{error_msg}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 验证文件大小 (10GB)
            if uploaded_file.size > 10 * 1024 * 1024 * 1024:
                return Response(
                    {"error": "文件大小超过10GB限制"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 验证文件不能为空
            if uploaded_file.size == 0:
                return Response(
                    {"error": "文件不能为空"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 对于FASTA文件，验证文件内容格式
            if file_type in ['genome', 'cds']:
                uploaded_file.seek(0)  # 重置文件指针
                first_chunk = uploaded_file.read(1024).decode('utf-8', errors='ignore')
                uploaded_file.seek(0)  # 重置文件指针

                if not first_chunk.strip():
                    return Response(
                        {"error": "文件内容为空"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if not first_chunk.startswith('>'):
                    return Response(
                        {"error": f"文件格式错误，{error_msg}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 获取客户端ID
            client_id = request.data.get('client_id') or request.META.get('HTTP_X_CLIENT_ID')
            if not client_id:
                return Response(
                    {"error": "缺少客户端标识"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 创建或获取分析任务记录
            import uuid
            from datetime import datetime

            # 对于基因组分析，需要处理多文件上传
            if analysis_type == 'genomic':
                return self._handle_genomic_analysis(request, uploaded_file, file_type, client_id)
            else:
                # CDS分析，直接处理单文件
                return self._handle_cds_analysis(request, uploaded_file, client_id)

        except Exception as e:
            logger.error(f"CodonW分析请求处理失败: {str(e)}")
            return Response(
                {"error": f"处理请求时发生错误: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _handle_genomic_analysis(self, request, uploaded_file, file_type, client_id):
        """处理基因组分析（需要基因组文件和GFF文件）"""
        import uuid
        from datetime import datetime

        # 获取或创建任务ID
        task_id = request.data.get('task_id')
        if not task_id:
            task_id = str(uuid.uuid4())

        logger.info(f"处理基因组分析文件: {file_type}, 任务ID: {task_id}")

        # 检查是否已有任务记录
        existing_task = self._get_task_record(task_id)

        # 创建任务目录
        task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
        upload_dir = os.path.join(task_dir, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        # 保存上传的文件
        if file_type == 'genome':
            file_path = os.path.join(upload_dir, 'genome.fasta')
        elif file_type == 'gff':
            file_path = os.path.join(upload_dir, 'annotation.gff')
        else:
            return Response(
                {"error": "基因组分析模式下文件类型错误"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with open(file_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"文件已保存: {file_path}")

        # 检查是否两个文件都已上传
        genome_file = os.path.join(upload_dir, 'genome.fasta')
        gff_file = os.path.join(upload_dir, 'annotation.gff')

        if os.path.exists(genome_file) and os.path.exists(gff_file):
            # 两个文件都已上传，开始分析
            logger.info(f"基因组分析文件齐全，开始分析任务: {task_id}")

            # 更新任务记录状态
            if existing_task:
                self._update_task_status(task_id, 'pending', 0, '等待开始基因组分析...')
            else:
                # 创建新任务记录
                task_record = {
                    'id': task_id,
                    'client_id': client_id,
                    'filename': f"genomic_analysis_{uploaded_file.name}",
                    'status': 'pending',
                    'progress': 0,
                    'message': '等待开始基因组分析...',
                    'created_at': datetime.now().isoformat(),
                    'completed_at': None,
                    'analysis_type': 'genomic'
                }
                self._save_task_record(task_record)

            # 启动分析线程
            import threading
            analysis_thread = threading.Thread(
                target=self._run_genomic_codonw_analysis,
                args=(task_id, genome_file, gff_file)
            )
            analysis_thread.daemon = True
            analysis_thread.start()

            return Response({
                "message": "基因组分析已开始",
                "task_id": task_id,
                "status": "pending"
            })
        else:
            # 还需要等待另一个文件，但也要创建任务记录
            missing_file = "注释文件" if not os.path.exists(gff_file) else "基因组文件"
            logger.info(f"等待上传{missing_file}，任务ID: {task_id}")

            # 创建等待状态的任务记录
            task_record = {
                'id': task_id,
                'client_id': client_id,
                'filename': f"genomic_analysis_{uploaded_file.name}",
                'status': 'waiting',
                'progress': 0,
                'message': f'等待上传{missing_file}...',
                'created_at': datetime.now().isoformat(),
                'completed_at': None,
                'analysis_type': 'genomic',
                'uploaded_files': [file_type]
            }

            self._save_task_record(task_record)

            return Response({
                "message": f"{file_type}文件上传成功，等待{missing_file}",
                "task_id": task_id,
                "status": "waiting",
                "uploaded_file_type": file_type
            })

    def _handle_cds_analysis(self, request, uploaded_file, client_id):
        """处理CDS分析（直接分析CDS文件）"""
        import uuid
        from datetime import datetime

        task_id = str(uuid.uuid4())
        logger.info(f"处理CDS分析，任务ID: {task_id}")

        # 创建任务目录
        task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
        upload_dir = os.path.join(task_dir, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        # 保存CDS文件
        cds_file = os.path.join(upload_dir, 'cds.fasta')
        with open(cds_file, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        logger.info(f"CDS文件已保存: {cds_file}")

        # 创建任务记录
        task_record = {
            'id': task_id,
            'client_id': client_id,
            'filename': uploaded_file.name,
            'status': 'pending',
            'progress': 0,
            'message': '等待开始CDS分析...',
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
            'analysis_type': 'cds'
        }

        self._save_task_record(task_record)

        # 启动分析线程
        import threading
        analysis_thread = threading.Thread(
            target=self._run_cds_codonw_analysis,
            args=(task_id, cds_file)
        )
        analysis_thread.daemon = True
        analysis_thread.start()

        return Response({
            "message": "CDS分析已开始",
            "task_id": task_id,
            "status": "pending"
        })

    def _run_genomic_codonw_analysis(self, task_id, genome_file, gff_file):
        """运行基因组CodonW分析：gffread提取CDS -> 格式转换 -> CodonW分析"""
        try:
            logger.info(f"开始基因组CodonW分析，任务ID: {task_id}")

            # 更新任务状态
            self._update_task_status(task_id, 'running', 10, '开始基因组分析...')

            # 创建工作目录
            task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
            work_dir = os.path.join(task_dir, 'work')
            results_dir = os.path.join(task_dir, 'results')
            os.makedirs(work_dir, exist_ok=True)
            os.makedirs(results_dir, exist_ok=True)

            # 步骤1：提取CDS序列（使用Python实现）
            self._update_task_status(task_id, 'running', 20, '正在提取CDS序列...')
            cds_file = os.path.join(work_dir, 'cds.fasta')

            # 使用Python实现CDS提取功能
            self._extract_cds_sequences(genome_file, gff_file, cds_file)

            if not os.path.exists(cds_file) or os.path.getsize(cds_file) == 0:
                raise Exception("CDS序列提取失败")

            logger.info(f"CDS序列提取成功: {cds_file}")

            # 步骤2：格式转换
            self._update_task_status(task_id, 'running', 40, '正在进行格式转换...')

            # 动态生成文件名前缀（基于基因组文件名）
            genome_filename = os.path.basename(genome_file)
            filename_prefix = os.path.splitext(genome_filename)[0]  # 去掉扩展名

            nt_file = os.path.join(work_dir, f'{filename_prefix}.nt')

            # 使用awk命令进行格式转换: awk '/^>/ {print $0} /^[^>]/ {gsub("\n",""); print}' cds.fasta > filename.nt
            # 由于Python环境，我们用Python实现相同的功能
            self._convert_fasta_format(cds_file, nt_file)

            logger.info(f"格式转换完成: {nt_file}")

            # 步骤3：运行CodonW分析
            self._update_task_status(task_id, 'running', 60, '正在进行密码子使用分析...')

            # 运行CodonW: codonw filename.nt -nomenu -silent -totals -all_indices
            self._run_codonw_command(task_id, work_dir, filename_prefix)

            # 处理结果
            self._update_task_status(task_id, 'running', 90, '正在处理分析结果...')
            self._process_codonw_output(work_dir, results_dir, task_id, filename_prefix)

            # 完成分析
            from datetime import datetime
            completed_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            self._update_task_status(task_id, 'completed', 100, '基因组分析完成', completed_time)
            logger.info(f"基因组CodonW分析完成，任务ID: {task_id}")

        except Exception as e:
            logger.error(f"基因组CodonW分析失败，任务ID: {task_id}, 错误: {str(e)}")
            self._update_task_status(task_id, 'failed', 0, f'分析失败: {str(e)}')

    def _run_cds_codonw_analysis(self, task_id, cds_file):
        """运行CDS CodonW分析：格式转换 -> CodonW分析"""
        try:
            logger.info(f"开始CDS CodonW分析，任务ID: {task_id}")

            # 更新任务状态
            self._update_task_status(task_id, 'running', 10, '开始CDS分析...')

            # 创建工作目录
            task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
            work_dir = os.path.join(task_dir, 'work')
            results_dir = os.path.join(task_dir, 'results')
            os.makedirs(work_dir, exist_ok=True)
            os.makedirs(results_dir, exist_ok=True)

            # 步骤1：格式转换
            self._update_task_status(task_id, 'running', 30, '正在进行格式转换...')

            # 动态生成文件名前缀（基于CDS文件名）
            cds_filename = os.path.basename(cds_file)
            filename_prefix = os.path.splitext(cds_filename)[0]  # 去掉扩展名

            nt_file = os.path.join(work_dir, f'{filename_prefix}.nt')

            # 复制CDS文件到工作目录并转换格式
            work_cds_file = os.path.join(work_dir, 'cds.fasta')
            shutil.copy2(cds_file, work_cds_file)

            # 格式转换
            self._convert_fasta_format(work_cds_file, nt_file)

            logger.info(f"格式转换完成: {nt_file}")

            # 步骤2：运行CodonW分析
            self._update_task_status(task_id, 'running', 60, '正在进行密码子使用分析...')

            # 运行CodonW: codonw filename.nt -nomenu -silent -totals -all_indices
            self._run_codonw_command(task_id, work_dir, filename_prefix)

            # 处理结果
            self._update_task_status(task_id, 'running', 90, '正在处理分析结果...')
            self._process_codonw_output(work_dir, results_dir, task_id, filename_prefix)

            # 完成分析
            from datetime import datetime
            completed_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            self._update_task_status(task_id, 'completed', 100, 'CDS分析完成', completed_time)
            logger.info(f"CDS CodonW分析完成，任务ID: {task_id}")

        except Exception as e:
            logger.error(f"CDS CodonW分析失败，任务ID: {task_id}, 错误: {str(e)}")
            self._update_task_status(task_id, 'failed', 0, f'分析失败: {str(e)}')

    def _convert_fasta_format(self, input_file, output_file):
        """转换FASTA格式：将多行序列合并为单行"""
        try:
            with open(input_file, 'r', encoding='utf-8') as infile, \
                 open(output_file, 'w', encoding='utf-8') as outfile:

                current_seq = ""
                for line in infile:
                    line = line.strip()
                    if line.startswith('>'):
                        # 如果有之前的序列，先写入
                        if current_seq:
                            outfile.write(current_seq + '\n')
                            current_seq = ""
                        # 写入序列头
                        outfile.write(line + '\n')
                    else:
                        # 累积序列
                        current_seq += line

                # 写入最后一个序列
                if current_seq:
                    outfile.write(current_seq + '\n')

            logger.info(f"FASTA格式转换完成: {input_file} -> {output_file}")

        except Exception as e:
            raise Exception(f"FASTA格式转换失败: {str(e)}")

    def _run_codonw_command(self, task_id, work_dir, filename_prefix):
        """运行CodonW命令"""
        try:
            # CodonW程序路径配置
            codonw_executable = getattr(settings, 'CODONW_EXECUTABLE', 'codonw')

            # 智能检测CodonW程序
            if not os.path.exists(codonw_executable):
                found_codonw = shutil.which('codonw')
                if found_codonw:
                    codonw_executable = found_codonw
                    logger.info(f"在PATH中找到CodonW: {codonw_executable}")
                else:
                    raise Exception(f"CodonW程序未找到。请确保已安装CodonW程序。配置路径: {codonw_executable}")

            # 构建CodonW命令: codonw input_file -nomenu -silent -totals -all_indices
            input_file = f'{filename_prefix}.nt'  # 输入文件是.nt文件
            cmd = [
                codonw_executable,
                input_file,          # 输入文件
                '-nomenu',           # 非交互模式运行
                '-silent',           # 静默模式，自动覆盖文件
                '-totals',           # 计算总统计信息
                '-all_indices'       # 计算所有密码子使用指数
            ]

            logger.info(f"CodonW命令: {' '.join(cmd)}")

            # 在工作目录中执行CodonW
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 等待进程完成
            timeout_seconds = getattr(settings, 'CODONW_TIMEOUT', 1800)
            logger.info(f"等待CodonW进程完成，超时时间: {timeout_seconds}秒")

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                logger.info(f"CodonW进程完成，返回码: {process.returncode}")
                logger.info(f"CodonW标准输出: {stdout}")
                if stderr:
                    logger.warning(f"CodonW标准错误: {stderr}")

                if process.returncode != 0:
                    raise Exception(f"CodonW执行失败，返回码: {process.returncode}, 错误: {stderr}")

            except subprocess.TimeoutExpired:
                logger.error(f"CodonW进程超时 ({timeout_seconds}秒)")
                process.kill()
                raise Exception(f"CodonW分析超时 ({timeout_seconds}秒)")

        except Exception as e:
            raise Exception(f"CodonW命令执行失败: {str(e)}")

    def _extract_cds_sequences(self, genome_file, gff_file, output_file):
        """从基因组文件和GFF注释文件中提取CDS序列"""
        try:
            logger.info(f"开始提取CDS序列: {genome_file} + {gff_file} -> {output_file}")

            # 读取基因组序列
            genome_sequences = self._read_fasta_file(genome_file)
            logger.info(f"读取到 {len(genome_sequences)} 个基因组序列")

            # 解析GFF文件，提取CDS信息
            cds_features = self._parse_gff_file(gff_file)
            logger.info(f"解析到 {len(cds_features)} 个CDS特征")

            # 提取CDS序列
            cds_count = 0
            with open(output_file, 'w', encoding='utf-8') as outfile:
                for cds in cds_features:
                    try:
                        seq_id = cds['seqid']
                        start = int(cds['start']) - 1  # GFF是1-based，Python是0-based
                        end = int(cds['end'])
                        strand = cds['strand']

                        if seq_id not in genome_sequences:
                            logger.warning(f"序列 {seq_id} 在基因组文件中未找到")
                            continue

                        # 提取序列
                        sequence = genome_sequences[seq_id][start:end]

                        # 如果是负链，需要反向互补
                        if strand == '-':
                            sequence = self._reverse_complement(sequence)

                        # 写入FASTA格式
                        gene_id = cds.get('gene_id', f"CDS_{cds_count + 1}")
                        outfile.write(f">{gene_id}\n{sequence}\n")
                        cds_count += 1

                    except Exception as e:
                        logger.warning(f"处理CDS特征时出错: {e}")
                        continue

            logger.info(f"成功提取 {cds_count} 个CDS序列")

        except Exception as e:
            raise Exception(f"CDS序列提取失败: {str(e)}")

    def _read_fasta_file(self, fasta_file):
        """读取FASTA文件，返回序列字典"""
        sequences = {}
        current_id = None
        current_seq = []

        with open(fasta_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    # 保存前一个序列
                    if current_id is not None:
                        sequences[current_id] = ''.join(current_seq)

                    # 开始新序列
                    current_id = line[1:].split()[0]  # 取第一个空格前的部分作为ID
                    current_seq = []
                else:
                    current_seq.append(line)

            # 保存最后一个序列
            if current_id is not None:
                sequences[current_id] = ''.join(current_seq)

        return sequences

    def _parse_gff_file(self, gff_file):
        """解析GFF文件，提取CDS特征"""
        cds_features = []

        with open(gff_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # 跳过注释行和空行
                if line.startswith('#') or not line:
                    continue

                fields = line.split('\t')
                if len(fields) < 9:
                    continue

                # 只处理CDS特征
                if fields[2].lower() != 'cds':
                    continue

                # 解析属性字段
                attributes = self._parse_gff_attributes(fields[8])

                cds_feature = {
                    'seqid': fields[0],
                    'source': fields[1],
                    'type': fields[2],
                    'start': fields[3],
                    'end': fields[4],
                    'score': fields[5],
                    'strand': fields[6],
                    'phase': fields[7],
                    'attributes': attributes,
                    'gene_id': attributes.get('gene_id', attributes.get('ID', f"gene_{len(cds_features) + 1}"))
                }

                cds_features.append(cds_feature)

        return cds_features

    def _parse_gff_attributes(self, attr_string):
        """解析GFF属性字段"""
        attributes = {}

        # 分割属性
        for attr in attr_string.split(';'):
            attr = attr.strip()
            if '=' in attr:
                key, value = attr.split('=', 1)
                attributes[key.strip()] = value.strip()

        return attributes

    def _reverse_complement(self, sequence):
        """计算DNA序列的反向互补序列"""
        complement_map = {
            'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G',
            'a': 't', 't': 'a', 'g': 'c', 'c': 'g',
            'N': 'N', 'n': 'n'
        }

        # 反向
        reversed_seq = sequence[::-1]

        # 互补
        complement_seq = ''.join(complement_map.get(base, base) for base in reversed_seq)

        return complement_seq

    def _save_task_record(self, task_record):
        """保存任务记录到JSON文件"""
        tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
        tasks = []

        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
            except Exception as e:
                logger.warning(f"读取任务文件失败: {e}")
                tasks = []

        tasks.append(task_record)

        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务记录失败: {e}")
            raise

    def _get_task_record(self, task_id):
        """获取任务记录"""
        tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')

        if not os.path.exists(tasks_file):
            return None

        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            for task in tasks:
                if task.get('id') == task_id:
                    return task

            return None
        except Exception as e:
            logger.warning(f"读取任务记录失败: {e}")
            return None

    @action(detail=False, methods=['get'], url_path='codonw_status/(?P<task_id>[^/.]+)')
    def codonw_status(self, request, task_id=None):
        """获取CodonW分析状态"""
        try:
            logger.info(f"查询CodonW状态，任务ID: {task_id}")
            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            logger.info(f"任务文件路径: {tasks_file}")

            if not os.path.exists(tasks_file):
                logger.warning(f"任务文件不存在: {tasks_file}")
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            task = next((t for t in tasks if t['id'] == task_id), None)
            if not task:
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response({
                "status": task['status'],
                "progress": task.get('progress', 0),
                "message": task.get('message', '')
            })

        except Exception as e:
            logger.error(f"获取CodonW状态失败: {str(e)}")
            return Response(
                {"error": f"获取状态失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def codonw_history(self, request):
        """获取CodonW分析历史（仅当前客户端）"""
        try:
            logger.info(f"CodonW历史请求参数: {request.query_params}")
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            client_id = request.query_params.get('client_id')

            logger.info(f"解析参数 - page: {page}, page_size: {page_size}, client_id: {client_id}")

            if not client_id:
                logger.warning("缺少客户端标识")
                return Response(
                    {"error": "缺少客户端标识"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            all_tasks = []
            if os.path.exists(tasks_file):
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    all_tasks = json.load(f)

            # 只获取当前客户端的任务
            client_tasks = [task for task in all_tasks if task.get('client_id') == client_id]

            # 按创建时间倒序排列
            client_tasks.sort(key=lambda x: x['created_at'], reverse=True)

            # 分页
            total = len(client_tasks)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_tasks = client_tasks[start_index:end_index]

            return Response({
                'count': total,
                'next': f"?page={page + 1}&page_size={page_size}&client_id={client_id}" if end_index < total else None,
                'previous': f"?page={page - 1}&page_size={page_size}&client_id={client_id}" if page > 1 else None,
                'results': paginated_tasks
            })

        except Exception as e:
            logger.error(f"获取CodonW历史失败: {str(e)}")
            return Response(
                {"error": f"获取历史失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='codonw_download/(?P<task_id>[^/.]+)')
    def codonw_download(self, request, task_id=None):
        """下载CodonW分析结果"""
        try:
            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            if not os.path.exists(tasks_file):
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            task = next((t for t in tasks if t['id'] == task_id), None)
            if not task or task['status'] != 'completed':
                return Response(
                    {"error": "任务不存在或未完成"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 创建结果压缩包 - 只打包results子目录
            import zipfile
            import tempfile

            task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
            results_dir = os.path.join(task_dir, 'results')

            if not os.path.exists(results_dir):
                return Response(
                    {"error": "结果文件不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 创建临时zip文件，只包含results目录中的文件
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in os.listdir(results_dir):
                    file_path = os.path.join(results_dir, file)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, file)  # 直接放在zip根目录

            # 返回文件响应
            response = FileResponse(
                open(temp_zip.name, 'rb'),
                as_attachment=True,
                filename=f'codonw_results_{task_id}.zip'
            )

            # 清理临时文件（在响应发送后）
            def cleanup():
                try:
                    os.unlink(temp_zip.name)
                except:
                    pass

            import atexit
            atexit.register(cleanup)

            return response

        except Exception as e:
            logger.error(f"下载CodonW结果失败: {str(e)}")
            return Response(
                {"error": f"下载失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'], url_path='codonw_delete/(?P<task_id>[^/.]+)')
    def codonw_delete(self, request, task_id=None):
        """删除CodonW分析任务（仅允许删除自己的任务）"""
        try:
            # 获取客户端ID（从查询参数或请求头）
            client_id = request.query_params.get('client_id') or request.META.get('HTTP_X_CLIENT_ID')
            if not client_id:
                return Response(
                    {"error": "缺少客户端标识"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            if not os.path.exists(tasks_file):
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            task = next((t for t in tasks if t['id'] == task_id), None)
            if not task:
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 验证任务所有权
            if task.get('client_id') != client_id:
                return Response(
                    {"error": "无权限删除此任务"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # 删除相关文件
            try:
                if 'file_path' in task and os.path.exists(task['file_path']):
                    os.remove(task['file_path'])

                results_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
                if os.path.exists(results_dir):
                    import shutil
                    shutil.rmtree(results_dir)
            except Exception as e:
                logger.warning(f"删除文件时出错: {str(e)}")

            # 从任务列表中移除
            tasks = [t for t in tasks if t['id'] != task_id]
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

            return Response({"message": "任务删除成功"})

        except Exception as e:
            logger.error(f"删除CodonW任务失败: {str(e)}")
            return Response(
                {"error": f"删除失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def codonw_result_upload(self, request):
        """上传CodonW结果文件进行可视化"""
        try:
            logger.info("收到CodonW结果上传请求")

            if 'file' not in request.FILES:
                return Response(
                    {"success": False, "message": "没有上传文件"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            uploaded_file = request.FILES['file']
            file_name = uploaded_file.name.lower()

            logger.info(f"上传文件名: {uploaded_file.name}")

            # 检查文件类型 - 只支持ZIP
            if not file_name.endswith('.zip'):
                return Response(
                    {"success": False, "message": "只支持ZIP格式的CodonW结果文件"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 创建临时目录处理文件
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, uploaded_file.name)

                # 保存上传的文件
                with open(zip_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                logger.info(f"ZIP文件已保存到: {zip_path}")

                # 解压文件
                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)

                try:
                    safe_extract_zip(zip_path, extract_dir)
                    logger.info(f"ZIP文件已解压到: {extract_dir}")

                    # 列出解压后的文件
                    extracted_files = []
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            extracted_files.append(os.path.join(root, file))
                    logger.info(f"解压后的文件: {extracted_files}")

                except (zipfile.BadZipFile, ValueError):
                    return Response(
                        {"success": False, "message": "无效的ZIP文件"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 查找CodonW结果文件
                codon_data = self._parse_uploaded_codonw_results(extract_dir)

                if codon_data:
                    logger.info("CodonW结果解析成功")
                    return Response({
                        "success": True,
                        "message": "CodonW结果解析成功",
                        "data": codon_data,
                        "organism": codon_data.get('organism', '上传的结果')
                    })
                else:
                    logger.error("未找到有效的CodonW结果文件")
                    # 列出解压后的所有文件以便调试
                    all_files = []
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            all_files.append(os.path.join(root, file))
                    logger.error(f"解压后的所有文件: {all_files}")

                    return Response(
                        {"success": False, "message": f"未找到有效的CodonW结果文件(.blk和.txt)。解压后的文件: {[os.path.basename(f) for f in all_files]}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        except Exception as e:
            logger.error(f"上传CodonW结果失败: {str(e)}")
            return Response(
                {"success": False, "message": f"处理失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='codonw_results/(?P<task_id>[^/.]+)')
    def codonw_results(self, request, task_id=None):
        """获取CodonW分析结果用于codon-card可视化"""
        try:
            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            if not os.path.exists(tasks_file):
                return Response(
                    {"error": "任务不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            task = next((t for t in tasks if t['id'] == task_id), None)
            if not task or task['status'] != 'completed':
                return Response(
                    {"error": "任务不存在或未完成"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 读取结果文件
            results_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id, 'results')
            logger.info(f"查找结果目录: {results_dir}")

            if not os.path.exists(results_dir):
                logger.error(f"结果目录不存在: {results_dir}")
                return Response(
                    {"error": "结果文件不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 查找.blk文件
            blk_files = []
            all_files = os.listdir(results_dir)
            logger.info(f"结果目录中的所有文件: {all_files}")

            for file in all_files:
                if file.endswith('.blk'):
                    blk_files.append(os.path.join(results_dir, file))
                    logger.info(f"找到.blk文件: {file}")

            if not blk_files:
                logger.error(f"未找到.blk文件，目录中的文件: {all_files}")
                return Response(
                    {"error": "未找到分析结果文件"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 解析.blk文件
            blk_file = blk_files[0]
            codon_usage = self._parse_blk_file(blk_file)

            if not codon_usage:
                return Response(
                    {"error": "解析结果文件失败"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 转换数据格式以兼容CodonCard页面
            formatted_codon_usage = self._format_codon_usage_data(codon_usage)
            amino_acids = self._group_by_amino_acid(formatted_codon_usage)

            # 解析genome_analysis_results.txt文件获取统计数据
            analysis_file = os.path.join(results_dir, 'genome_analysis_results.txt')
            analysis_stats = None
            if os.path.exists(analysis_file):
                analysis_stats = self._parse_codonw_statistics_file(analysis_file)

            # 构建返回数据
            organism_name = os.path.basename(blk_file).replace('.blk', '').replace('_codon_usage', '')
            result_data = {
                'organism': organism_name,
                'task_id': task_id,
                'codon_usage': formatted_codon_usage,
                'amino_acids': amino_acids,
                'total_codons': sum(data['count'] for data in codon_usage.values()),
                'nucleotide_composition': self._calculate_nucleotide_composition(codon_usage),
                'statistics': analysis_stats,  # 重命名为statistics以匹配前端
                'analysis_info': {
                    'filename': task.get('filename', ''),
                    'created_at': task.get('created_at', ''),
                    'completed_at': task.get('completed_at', ''),
                    'analysis_type': task.get('analysis_type', '')
                }
            }

            return Response(result_data)

        except Exception as e:
            logger.error(f"获取CodonW结果失败: {str(e)}")
            return Response(
                {"error": f"获取结果失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _run_codonw_analysis(self, task_id, file_path):
        """运行CodonW分析的后台方法"""
        try:
            # 更新任务状态
            self._update_task_status(task_id, 'running', 10, '开始分析...')

            # 创建结果目录
            results_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task_id)
            os.makedirs(results_dir, exist_ok=True)

            # 调用真正的CodonW程序
            self._execute_codonw(task_id, file_path, results_dir)

            # 标记任务完成
            from datetime import datetime
            self._update_task_status(
                task_id,
                'completed',
                100,
                '分析完成',
                completed_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"CodonW分析失败: {str(e)}")
            self._update_task_status(task_id, 'failed', 0, f'分析失败: {str(e)}')

    def _execute_codonw(self, task_id, input_file, results_dir):
        """执行真正的CodonW程序"""
        import subprocess
        import shutil

        try:
            # CodonW程序路径配置
            codonw_executable = getattr(settings, 'CODONW_EXECUTABLE', 'codonw')

            # 智能检测CodonW程序
            if not os.path.exists(codonw_executable):
                # 如果配置的路径不存在，尝试在PATH中查找
                found_codonw = shutil.which('codonw')
                if found_codonw:
                    codonw_executable = found_codonw
                    logger.info(f"在PATH中找到CodonW: {codonw_executable}")
                else:
                    raise Exception(f"CodonW程序未找到。请确保已安装CodonW程序。配置路径: {codonw_executable}")

            logger.info(f"使用CodonW程序: {codonw_executable}")

            self._update_task_status(task_id, 'running', 20, '准备输入文件...')

            # 准备工作目录
            work_dir = os.path.join(results_dir, 'work')
            os.makedirs(work_dir, exist_ok=True)

            # 获取用户上传文件的文件名（不带扩展名）
            original_filename = os.path.basename(input_file)
            filename_without_ext = os.path.splitext(original_filename)[0]

            # 复制输入文件到工作目录，使用原始文件名
            work_input = os.path.join(work_dir, original_filename)
            shutil.copy2(input_file, work_input)

            logger.info(f"使用文件名: {filename_without_ext}, 输入文件: {original_filename}")

            self._update_task_status(task_id, 'running', 30, '运行CodonW分析...')

            # 构建CodonW命令
            # 使用指定的CodonW命令: codonw -totals -all_indices -nomenu [filename] [filename.ext]
            cmd = [
                codonw_executable,
                '-totals',           # 计算总统计信息
                '-all_indices',      # 计算所有密码子使用指数
                '-nomenu',           # 非交互模式运行
                filename_without_ext, # 输出文件前缀（用户文件名，不带扩展名）
                original_filename    # 输入文件（用户上传的文件）
            ]

            logger.info(f"CodonW命令: {' '.join(cmd)}")

            # 在工作目录中执行CodonW
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self._update_task_status(task_id, 'running', 50, '正在计算密码子指数...')

            # 等待进程完成
            timeout_seconds = getattr(settings, 'CODONW_TIMEOUT', 1800)
            logger.info(f"等待CodonW进程完成，超时时间: {timeout_seconds}秒")

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                logger.info(f"CodonW进程完成，返回码: {process.returncode}")
                logger.info(f"CodonW标准输出: {stdout}")
                if stderr:
                    logger.warning(f"CodonW标准错误: {stderr}")

                if process.returncode != 0:
                    raise Exception(f"CodonW执行失败，返回码: {process.returncode}, 错误: {stderr}")

                self._update_task_status(task_id, 'running', 80, '处理分析结果...')

            except subprocess.TimeoutExpired:
                logger.error(f"CodonW进程超时 ({timeout_seconds}秒)")
                process.kill()
                raise Exception(f"CodonW分析超时 ({timeout_seconds}秒)")

            # 处理CodonW输出文件
            self._process_codonw_output(work_dir, results_dir, task_id, filename_without_ext)

            self._update_task_status(task_id, 'running', 90, '生成最终报告...')

            # 生成汇总报告
            self._generate_codonw_summary(results_dir, task_id, input_file)

            # 清理工作目录
            shutil.rmtree(work_dir, ignore_errors=True)

        except subprocess.TimeoutExpired:
            raise Exception("CodonW分析超时")
        except Exception as e:
            logger.error(f"执行CodonW失败: {str(e)}")
            raise

    def _process_codonw_output(self, work_dir, results_dir, task_id, filename_prefix='species'):
        """处理CodonW的输出文件 - 只复制.blk和.out文件到results目录"""
        try:
            logger.info(f"工作目录中的所有文件: {os.listdir(work_dir)}")
            logger.info(f"查找以 '{filename_prefix}' 开头的输出文件")

            # 查找.blk和.out文件
            blk_file = None
            out_file = None

            logger.info(f"正在查找以 '{filename_prefix}.' 开头的文件")

            for file in os.listdir(work_dir):
                logger.info(f"检查文件: {file}")
                if file.startswith(filename_prefix + '.'):
                    logger.info(f"文件 {file} 匹配前缀 {filename_prefix}")
                    if file.endswith('.blk'):
                        blk_file = os.path.join(work_dir, file)
                        logger.info(f"找到.blk文件: {blk_file}")
                    elif file.endswith('.out'):
                        out_file = os.path.join(work_dir, file)
                        logger.info(f"找到.out文件: {out_file}")
                else:
                    logger.info(f"文件 {file} 不匹配前缀 {filename_prefix}")

            logger.info(f"最终找到CodonW输出文件: blk={blk_file}, out={out_file}")

            # 复制.blk文件到results目录
            if blk_file and os.path.exists(blk_file):
                blk_result_path = os.path.join(results_dir, f'{filename_prefix}_codon_usage.blk')
                shutil.copy2(blk_file, blk_result_path)
                logger.info(f"密码子使用表已保存: {blk_result_path}")

            # 复制.out文件到results目录并重命名为.txt
            if out_file and os.path.exists(out_file):
                out_result_path = os.path.join(results_dir, f'{filename_prefix}_analysis_results.txt')
                shutil.copy2(out_file, out_result_path)
                logger.info(f"分析结果已保存: {out_result_path}")

            # 如果找到了结果文件，清理results目录中的旧文件
            if blk_file or out_file:
                # 删除旧的固定命名文件
                old_files = ['codonw_main_results.txt', 'codon_usage_table.txt', 'codonw_details.csv']
                for old_file in old_files:
                    old_path = os.path.join(results_dir, old_file)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        logger.info(f"删除旧文件: {old_file}")
            else:
                logger.warning("未找到CodonW输出文件(.blk或.out)")
                logger.warning(f"filename_prefix: '{filename_prefix}'")
                logger.warning(f"work_dir files: {os.listdir(work_dir)}")
                raise Exception("CodonW分析未生成预期的输出文件")

        except Exception as e:
            logger.error(f"处理CodonW输出失败: {str(e)}")
            raise

    def _parse_codonw_results_to_csv(self, results_file, output_dir):
        """解析CodonW结果文件并生成CSV格式"""
        try:
            csv_file = os.path.join(output_dir, 'codonw_details.csv')

            with open(results_file, 'r', encoding='utf-8') as infile, \
                 open(csv_file, 'w', encoding='utf-8') as outfile:

                # 写入CSV头部
                outfile.write("Sequence_ID,Length,ENC,CAI,CBI,Fop,GC,GC3s\n")

                # 解析CodonW输出格式
                # CodonW的输出格式通常是制表符分隔的
                for line in infile:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('title'):
                        # 根据CodonW的实际输出格式调整解析逻辑
                        parts = line.split('\t')
                        if len(parts) >= 8:  # 确保有足够的列
                            # 提取主要指标
                            seq_id = parts[0] if parts[0] else f"seq_{len(parts)}"
                            length = parts[1] if len(parts) > 1 else "0"
                            enc = parts[2] if len(parts) > 2 else "0"
                            cai = parts[3] if len(parts) > 3 else "0"
                            cbi = parts[4] if len(parts) > 4 else "0"
                            fop = parts[5] if len(parts) > 5 else "0"
                            gc = parts[6] if len(parts) > 6 else "0"
                            gc3s = parts[7] if len(parts) > 7 else "0"

                            outfile.write(f"{seq_id},{length},{enc},{cai},{cbi},{fop},{gc},{gc3s}\n")

            logger.info(f"CodonW结果已转换为CSV格式: {csv_file}")

        except Exception as e:
            logger.error(f"解析CodonW结果失败: {str(e)}")
            # 如果解析失败，生成一个基本的CSV文件
            self._generate_fallback_csv(output_dir)

    def _generate_fallback_csv(self, output_dir):
        """生成备用的CSV文件（当解析失败时）"""
        csv_file = os.path.join(output_dir, 'codonw_details.csv')
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("Sequence_ID,Length,ENC,CAI,CBI,Fop,GC,GC3s\n")
            f.write("analysis_completed,0,0,0,0,0,0,0\n")

    def _generate_codonw_summary(self, results_dir, task_id, input_file):
        """生成CodonW分析汇总报告"""
        try:
            summary_file = os.path.join(results_dir, 'codonw_summary.txt')

            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("CodonW Analysis Results Summary\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Task ID: {task_id}\n")
                f.write(f"Input file: {os.path.basename(input_file)}\n")
                f.write(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 尝试读取详细结果进行统计
                csv_file = os.path.join(results_dir, 'codonw_details.csv')
                if os.path.exists(csv_file):
                    with open(csv_file, 'r', encoding='utf-8') as csv_f:
                        lines = csv_f.readlines()
                        if len(lines) > 1:  # 除了标题行
                            f.write(f"Total sequences analyzed: {len(lines) - 1}\n")

                            # 计算平均值
                            enc_values = []
                            cai_values = []
                            gc_values = []

                            for line in lines[1:]:  # 跳过标题行
                                parts = line.strip().split(',')
                                if len(parts) >= 8:
                                    try:
                                        enc_values.append(float(parts[2]))
                                        cai_values.append(float(parts[3]))
                                        gc_values.append(float(parts[6]))
                                    except ValueError:
                                        continue

                            if enc_values:
                                f.write(f"Average ENC: {sum(enc_values)/len(enc_values):.2f}\n")
                            if cai_values:
                                f.write(f"Average CAI: {sum(cai_values)/len(cai_values):.3f}\n")
                            if gc_values:
                                f.write(f"Average GC content: {sum(gc_values)/len(gc_values):.1f}%\n")

                f.write("\nOutput files:\n")
                f.write("- codonw_details.csv: Detailed results in CSV format\n")
                f.write("- codonw_main_results.txt: Original CodonW output\n")
                f.write("- codon_usage_table.txt: Codon usage table\n")
                f.write("- optimal_codon_freq.txt: Optimal codon frequencies\n")
                f.write("- cai_values.txt: CAI values\n")
                f.write("- enc_values.txt: ENC values\n")

            logger.info(f"CodonW汇总报告已生成: {summary_file}")

        except Exception as e:
            logger.error(f"生成CodonW汇总报告失败: {str(e)}")

    def _update_task_status(self, task_id, status, progress=None, message=None, completed_at=None):
        """更新任务状态"""
        try:
            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            tasks = []
            if os.path.exists(tasks_file):
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)

            for task in tasks:
                if task['id'] == task_id:
                    task['status'] = status
                    if progress is not None:
                        task['progress'] = progress
                    if message is not None:
                        task['message'] = message
                    if completed_at is not None:
                        task['completed_at'] = completed_at
                    break

            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"更新任务状态失败: {str(e)}")

    def _cleanup_expired_tasks(self):
        """清理过期任务"""
        try:
            # 正式环境：7天过期
            expiry_minutes = 7 * 24 * 60  # 7天
            # expiry_minutes = 1  # 测试：1分钟

            tasks_file = os.path.join(settings.MEDIA_ROOT, 'codonw_tasks.json')
            if not os.path.exists(tasks_file):
                return

            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)

            current_time = datetime.now()
            tasks_to_keep = []
            deleted_count = 0

            for task in tasks:
                try:
                    # 解析任务创建时间
                    created_at_str = task.get('created_at', '')
                    if created_at_str:
                        # 处理ISO格式时间
                        if 'T' in created_at_str:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            if created_at.tzinfo:
                                created_at = created_at.replace(tzinfo=None)
                        else:
                            # 处理普通格式时间
                            created_at = datetime.strptime(created_at_str, '%Y/%m/%d %H:%M:%S')

                        # 检查是否过期
                        age_minutes = (current_time - created_at).total_seconds() / 60

                        if age_minutes > expiry_minutes:
                            # 删除任务文件夹
                            task_dir = os.path.join(settings.MEDIA_ROOT, 'codonw_results', task['id'])
                            if os.path.exists(task_dir):
                                shutil.rmtree(task_dir)
                                logger.info(f"删除过期任务文件夹: {task_dir}")

                            logger.info(f"删除过期任务: {task['id']}, 创建时间: {created_at_str}, 年龄: {age_minutes:.1f}分钟")
                            deleted_count += 1
                        else:
                            tasks_to_keep.append(task)
                    else:
                        # 没有创建时间的任务保留
                        tasks_to_keep.append(task)

                except Exception as e:
                    logger.error(f"处理任务 {task.get('id', 'unknown')} 时出错: {str(e)}")
                    # 出错的任务保留
                    tasks_to_keep.append(task)

            # 更新任务文件
            if deleted_count > 0:
                with open(tasks_file, 'w', encoding='utf-8') as f:
                    json.dump(tasks_to_keep, f, ensure_ascii=False, indent=2)
                logger.info(f"清理完成，删除了 {deleted_count} 个过期任务，保留了 {len(tasks_to_keep)} 个任务")

        except Exception as e:
            logger.error(f"清理过期任务失败: {str(e)}")

    def _start_cleanup_scheduler(self):
        """启动清理任务调度器"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(60)  # 每60秒检查一次
                    self._cleanup_expired_tasks()
                except Exception as e:
                    logger.error(f"清理调度器出错: {str(e)}")

        # 启动后台线程
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("任务清理调度器已启动，每60秒检查一次过期任务")




    @action(detail=False, methods=['get'])
    def supplementary_data(self, request):
        """获取补充数据"""
        try:
            supplementary_data = self._load_supplementary_data()
            return Response(supplementary_data)
        except Exception as e:
            logger.error(f"获取补充数据失败: {str(e)}")
            return Response(
                {"error": f"获取补充数据失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def paginated_overview(self, request):
        """Overview rows based on default assembly / default annotation context."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            search = request.query_params.get('search', '')
            sub_populations = request.query_params.get('sub_populations', '')

            def serialize_file(file_obj):
                if not file_obj:
                    return None
                if isinstance(file_obj, dict):
                    return {
                        'id': file_obj.get('id'),
                        'name': file_obj.get('name'),
                        'file_path': file_obj.get('file_path'),
                        'size': file_obj.get('size'),
                        'file_size': file_obj.get('file_size'),
                        'category': file_obj.get('category'),
                        'created_at': file_obj.get('created_at'),
                        'source': file_obj.get('source'),
                        'datafile_download_url': file_obj.get('datafile_download_url'),
                        'download_url': file_obj.get('download_url'),
                    }
                return None

            def file_category(file_obj):
                if isinstance(file_obj, dict):
                    return file_obj.get('category') or ''
                return file_obj.category or ''

            def first_file(files, category):
                for file_obj in files:
                    if file_category(file_obj) == category:
                        return file_obj
                return None

            accession_qs = Accession.objects.prefetch_related(
                'files',
                Prefetch(
                    'assemblies',
                    queryset=Assembly.objects.prefetch_related(
                        'files',
                        Prefetch(
                            'annotations',
                            queryset=Annotation.objects.prefetch_related('files'),
                        ),
                    ),
                ),
            ).order_by('accession')

            if search:
                accession_qs = accession_qs.filter(accession__icontains=search)

            accession_list = list(accession_qs)

            if sub_populations:
                if sub_populations == 'NONE':
                    accession_list = []
                else:
                    selected_populations = [pop.strip() for pop in sub_populations.split(',') if pop.strip()]
                    include_unknown = 'Unknown' in selected_populations or '????' in selected_populations
                    known_populations = {
                        pop for pop in selected_populations
                        if pop not in {'Unknown', '????'}
                    }
                    filtered_accessions = []
                    for accession_obj in accession_list:
                        accession_sub_population = (accession_obj.sub_population or '').strip()
                        if accession_sub_population in known_populations:
                            filtered_accessions.append(accession_obj)
                        elif include_unknown and not accession_sub_population:
                            filtered_accessions.append(accession_obj)
                    accession_list = filtered_accessions

            rows = []
            for accession_obj in accession_list:
                assemblies = list(accession_obj.assemblies.all())
                default_assembly = next((assembly for assembly in assemblies if assembly.is_default), None)
                if not default_assembly and assemblies:
                    default_assembly = assemblies[0]

                default_annotations = list(default_assembly.annotations.all()) if default_assembly else []
                default_annotation = next((annotation for annotation in default_annotations if annotation.is_default), None)
                if not default_annotation and default_annotations:
                    default_annotation = default_annotations[0]

                relation_files = get_files_for_accession(accession_obj.id)
                if relation_files:
                    overview_files = [
                        _adapt_overview_file_service_result(item)
                        for item in relation_files
                    ]
                    default_annotation_files = [
                        item for item in overview_files
                        if file_category(item) == 'annotation'
                    ]
                    default_assembly_files = [
                        item for item in overview_files
                        if file_category(item) != 'annotation'
                    ]
                else:
                    default_assembly_files = []
                    default_annotation_files = []

                rows.append({
                    'accession': accession_obj.accession,
                    'genome': serialize_file(first_file(default_assembly_files, 'genome')),
                    'annotation': serialize_file(first_file(default_annotation_files, 'annotation')),
                    'hasTranscriptome': any(
                        file_category(file_obj).startswith('transcriptome.')
                        for file_obj in default_assembly_files
                    ),
                    'codon': serialize_file(first_file(default_assembly_files, 'codon')),
                    'centromere': serialize_file(first_file(default_assembly_files, 'centromere')),
                    'TEs': serialize_file(first_file(default_assembly_files, 'TEs')),
                    'coreBlocks': serialize_file(first_file(default_assembly_files, 'coreBlocks')),
                    'miRNA': serialize_file(first_file(default_assembly_files, 'miRNA')),
                    'tRNA': serialize_file(first_file(default_assembly_files, 'tRNA')),
                    'rRNA': serialize_file(first_file(default_assembly_files, 'rRNA')),
                    'subPopulation': accession_obj.sub_population,
                    'seqData': accession_obj.seq_data,
                    'longitude': accession_obj.longitude,
                    'latitude': accession_obj.latitude,
                    'assembly_count': len(assemblies),
                    'annotation_count': sum(len(list(assembly.annotations.all())) for assembly in assemblies),
                    'default_assembly_id': default_assembly.id if default_assembly else None,
                    'default_annotation_id': default_annotation.id if default_annotation else None,
                })

            total = len(rows)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = rows[start_index:end_index]

            return Response({
                'count': total,
                'next': f"?page={page + 1}&page_size={page_size}" if end_index < total else None,
                'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
                'results': paginated_data
            })

        except Exception as e:
            logger.error(f"????????: {str(e)}")
            return Response(
                {"error": f"????????: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def categories(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def all_files(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def sub_populations(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def transcriptome_types(self, request):
        return self._archived_response()

    @action(detail=False, methods=['get'])
    def paginated_transcriptome_overview(self, request):
        return self._archived_response()


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


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_login(request):
    """管理员登录接口"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        # 硬编码验证
        if username == 'root' and password == 'root123':
            # 生成简单的token（实际项目中应该使用JWT）
            token = f"admin_token_{datetime.now().timestamp()}"
            return Response({
                'success': True,
                'token': token,
                'user': {
                    'username': username,
                    'role': 'admin'
                }
            })
        else:
            return Response({
                'success': False,
                'message': '用户名或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return Response({
            'success': False,
            'message': '登录失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
    @action(detail=False, methods=['get'])
    def paginated_overview(self, request):
        """Overview rows based on default assembly / default annotation context."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            search = request.query_params.get('search', '')
            sub_populations = request.query_params.get('sub_populations', '')

            def serialize_file(file_obj):
                if not file_obj:
                    return None
                return {
                    'id': file_obj.id,
                    'name': file_obj.name,
                    'file_path': file_obj.file_path,
                    'size': file_obj.size,
                    'created_at': file_obj.created_at,
                }

            def first_file(files, category):
                for file_obj in files:
                    if file_obj.category == category:
                        return file_obj
                return None

            accession_qs = Accession.objects.prefetch_related(
                'files',
                Prefetch(
                    'assemblies',
                    queryset=Assembly.objects.prefetch_related(
                        'files',
                        Prefetch(
                            'annotations',
                            queryset=Annotation.objects.prefetch_related('files'),
                        ),
                    ),
                ),
            ).order_by('accession')

            if search:
                accession_qs = accession_qs.filter(accession__icontains=search)

            accession_list = list(accession_qs)

            if sub_populations:
                if sub_populations == 'NONE':
                    accession_list = []
                else:
                    selected_populations = [pop.strip() for pop in sub_populations.split(',') if pop.strip()]
                    include_unknown = 'Unknown' in selected_populations or 'æœªçŸ¥äºšç¾¤' in selected_populations
                    known_populations = {
                        pop for pop in selected_populations
                        if pop not in {'Unknown', 'æœªçŸ¥äºšç¾¤'}
                    }
                    filtered_accessions = []
                    for accession_obj in accession_list:
                        accession_sub_population = (accession_obj.sub_population or '').strip()
                        if accession_sub_population in known_populations:
                            filtered_accessions.append(accession_obj)
                        elif include_unknown and not accession_sub_population:
                            filtered_accessions.append(accession_obj)
                    accession_list = filtered_accessions

            rows = []
            for accession_obj in accession_list:
                assemblies = list(accession_obj.assemblies.all())
                default_assembly = next((assembly for assembly in assemblies if assembly.is_default), None)
                if not default_assembly and assemblies:
                    default_assembly = assemblies[0]

                default_assembly_files = list(default_assembly.files.all()) if default_assembly else []
                default_annotations = list(default_assembly.annotations.all()) if default_assembly else []
                default_annotation = next((annotation for annotation in default_annotations if annotation.is_default), None)
                if not default_annotation and default_annotations:
                    default_annotation = default_annotations[0]

                default_annotation_files = list(default_annotation.files.all()) if default_annotation else []
                legacy_files = list(accession_obj.files.all())

                if not default_assembly_files and legacy_files:
                    default_assembly_files = [file_obj for file_obj in legacy_files if not file_obj.annotation_id]

                if not default_annotation_files and legacy_files:
                    if default_annotation:
                        default_annotation_files = [
                            file_obj for file_obj in legacy_files
                            if file_obj.annotation_id == default_annotation.id
                        ]
                    else:
                        default_annotation_files = [
                            file_obj for file_obj in legacy_files if file_obj.category == 'annotation'
                        ]

                rows.append({
                    'accession': accession_obj.accession,
                    'genome': serialize_file(first_file(default_assembly_files, 'genome')),
                    'annotation': serialize_file(first_file(default_annotation_files, 'annotation')),
                    'hasTranscriptome': any(
                        file_obj.category.startswith('transcriptome.') for file_obj in default_assembly_files
                    ),
                    'codon': serialize_file(first_file(default_assembly_files, 'codon')),
                    'centromere': serialize_file(first_file(default_assembly_files, 'centromere')),
                    'TEs': serialize_file(first_file(default_assembly_files, 'TEs')),
                    'coreBlocks': serialize_file(first_file(default_assembly_files, 'coreBlocks')),
                    'miRNA': serialize_file(first_file(default_assembly_files, 'miRNA')),
                    'tRNA': serialize_file(first_file(default_assembly_files, 'tRNA')),
                    'rRNA': serialize_file(first_file(default_assembly_files, 'rRNA')),
                    'subPopulation': accession_obj.sub_population,
                    'seqData': accession_obj.seq_data,
                    'longitude': accession_obj.longitude,
                    'latitude': accession_obj.latitude,
                    'assembly_count': len(assemblies),
                    'annotation_count': sum(len(list(assembly.annotations.all())) for assembly in assemblies),
                    'default_assembly_id': default_assembly.id if default_assembly else None,
                    'default_annotation_id': default_annotation.id if default_annotation else None,
                })

            total = len(rows)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = rows[start_index:end_index]

            return Response({
                'count': total,
                'next': f"?page={page + 1}&page_size={page_size}" if end_index < total else None,
                'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
                'results': paginated_data
            })
        except Exception as e:
            logger.error(f"èŽ·å–åˆ†é¡µæ•°æ®å¤±è´¥: {str(e)}")
            return Response(
                {"error": f"èŽ·å–åˆ†é¡µæ•°æ®å¤±è´¥: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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


def _analyze_uploaded_file(filename, file_path):
    """分析上传的文件，自动识别类型和分类"""
    parts = filename.split('.')
    extension = parts[-1] if len(parts) > 1 else ''

    # 处理压缩文件格式
    if extension in ['gz', 'zip', 'bz2', 'xz']:
        if len(parts) > 2:
            extension = f"{parts[-2]}.{parts[-1]}"

    # 默认值
    organism = 'unknown'
    category = 'other'

    # 组织类型列表
    tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']

    try:
        # 1. 处理转录组文件格式: transcriptome.type.organism.extension
        if len(parts) >= 4 and parts[0] == 'transcriptome' and parts[1] in tissue_types:
            organism = parts[2]
            category = f"transcriptome.{parts[1]}"

        # 2. 处理注释文件格式: annotation.organism.extension
        elif len(parts) >= 3 and parts[0] == 'annotation':
            organism = parts[1]
            category = 'annotation'

        # 3. 处理coreBlocks文件格式: coreBlocks.organism.bed
        elif len(parts) >= 3 and parts[0] in ['coreBlocks', 'variableBlocks']:
            organism = parts[1]
            category = parts[0]

        # 4. 处理其他格式: category.organism.extension
        elif len(parts) >= 3:
            potential_category = parts[0]
            potential_organism = parts[1]

            # 验证category是否有效
            valid_categories = [choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES]
            if potential_category in valid_categories and potential_organism not in tissue_types:
                category = potential_category
                organism = potential_organism

    except Exception as e:
        logger.warning(f"文件名分析失败: {filename}, 错误: {str(e)}")

    return {
        'organism': organism,
        'category': category,
        'extension': extension
    }


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
@permission_classes([AllowAny])
@csrf_exempt
def admin_create_accession(request):
    """新增Accession数据"""
    try:
        data = json.loads(request.body)
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
@permission_classes([AllowAny])
@csrf_exempt
def admin_update_accession(request, accession):
    """更新Accession数据"""
    try:
        data = json.loads(request.body)
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
@permission_classes([AllowAny])
@csrf_exempt
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
@permission_classes([AllowAny])
@csrf_exempt
def admin_batch_delete_accessions(request):
    """批量删除Accession数据"""
    try:
        data = json.loads(request.body)
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
@permission_classes([AllowAny])
@csrf_exempt
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
@permission_classes([AllowAny])
@csrf_exempt
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

        assemblies = list(
            accession_obj.assemblies.all().order_by('-is_default', 'name', 'id')
        )
        annotation_map = {}
        for assembly in assemblies:
            assembly.prefetched_files = []
            assembly.prefetched_annotations = list(
                assembly.annotations.all().order_by('-is_default', 'name', 'id')
            )
            for annotation in assembly.prefetched_annotations:
                annotation.prefetched_files = []
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

        for assembly in assemblies:
            for annotation in assembly.prefetched_annotations:
                annotation_files = getattr(annotation, 'prefetched_files', []) or []
                annotation_source_file = next(
                    (
                        file_obj for file_obj in annotation_files
                        if file_obj.category == 'annotation' and file_obj.file_path
                    ),
                    None,
                )

                annotation_file_path = annotation_source_file.file_path if annotation_source_file else None

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

