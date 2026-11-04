import json
import logging
import mimetypes
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timedelta

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .parsers.archive import safe_extract_zip


logger = logging.getLogger(__name__)


class CodonWViewSet(viewsets.ViewSet):
    """CodonW task, upload, result, and download API."""

    _cleanup_scheduler_started = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 启动清理调度器（只启动一次）
        if not CodonWViewSet._cleanup_scheduler_started:
            CodonWViewSet._cleanup_scheduler_started = True
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
