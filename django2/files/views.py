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
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from .models import FileType, GenomeFile, Organism, FileCategory
from .serializers import (
    FileTypeSerializer, GenomeFileSerializer, GenomeFileListSerializer,
    OrganismSerializer, FileCategorySerializer
)
import logging

logger = logging.getLogger(__name__)

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
    """基因组文件视图集"""
    queryset = GenomeFile.objects.all()
    serializer_class = GenomeFileSerializer

    # 类变量，确保清理调度器只启动一次
    _cleanup_scheduler_started = False

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
        queryset = GenomeFile.objects.all()
        organism = self.request.query_params.get('organism', None)
        category = self.request.query_params.get('category', None)
        
        # 定义已知的组织类型，这些不应该被当作生物体
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
        
        # 过滤掉organism是组织类型的记录
        queryset = queryset.exclude(organism__in=tissue_types)
        
        if organism:
            queryset = queryset.filter(organism=organism)
        if category:
            queryset = queryset.filter(category=category)
            
        return queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载文件"""
        try:
            file_obj = self.get_object()
            file_path = file_obj.file_path
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return Response(
                    {"error": "文件不存在"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 获取文件类型
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # 创建文件响应
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
        
        except Exception as e:
            logger.error(f"文件下载失败: {str(e)}")
            return Response(
                {"error": f"文件下载失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def download_transcriptome(self, request):
        """下载特定类型的转录组文件"""
        try:
            organism = request.query_params.get('organism')
            tissue_type = request.query_params.get('type')
            
            if not organism or not tissue_type:
                return Response(
                    {"error": "缺少必要的参数: organism 或 type"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 1. 首先尝试从数据库查找特定类型的转录组文件
            category = f"transcriptome.{tissue_type}"
            file_obj = GenomeFile.objects.filter(
                organism=organism,
                category=category
            ).first()
            
            if file_obj:
                file_path = file_obj.file_path
            else:
                # 2. 尝试在manual_files目录中查找特定命名格式的文件
                directory = settings.MANUAL_FILES_DIR
                # 支持多种可能的扩展名
                possible_extensions = ['fastaq.gz', 'fasta.gz', 'fa.gz', 'fq.gz', 'fastq.gz']
                file_path = None
                
                for ext in possible_extensions:
                    temp_path = os.path.join(directory, f"transcriptome.{tissue_type}.{organism}.{ext}")
                    if os.path.exists(temp_path):
                        file_path = temp_path
                        break
                
                # 3. 如果特定类型文件不存在，尝试回退到通用转录组文件
                if not file_path:
                    file_obj = GenomeFile.objects.filter(
                        organism=organism,
                        category='transcriptome'
                    ).first()
                    
                    if file_obj:
                        file_path = file_obj.file_path
                    else:
                        # 4. 最后尝试查找任何可能的通用转录组文件
                        for ext in possible_extensions:
                            temp_path = os.path.join(directory, f"transcriptome.{organism}.{ext}")
                            if os.path.exists(temp_path):
                                file_path = temp_path
                                break
                        
                        if not file_path:
                            return Response(
                                {"error": f"未找到 {organism} 的 {tissue_type} 类型转录组文件"},
                                status=status.HTTP_404_NOT_FOUND
                            )
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return Response(
                    {"error": f"文件不存在: {os.path.basename(file_path)}"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 获取文件类型
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # 创建文件响应
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
        
        except Exception as e:
            logger.error(f"转录组文件下载失败: {str(e)}")
            return Response(
                {"error": f"转录组文件下载失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_chromosomes(self, request):

        # 导入数据库连接模块
        from django.db import connection
        # 打印接口使用的数据库名称
        # logger.info(f"get_chromosomes接口连接的数据库: {connection.settings_dict['NAME']}")

        """获取指定生物体的染色体列表"""
        organism = request.query_params.get('organism')
        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 查找对应的基因组文件
        genome_file = GenomeFile.objects.filter(
            organism=organism,
            category='genome'
        ).first()
        
        if not genome_file:
            return Response(
                {"error": f"未找到 {organism} 的基因组文件"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 解析FASTA文件获取染色体信息
        chromosomes = []
        try:
            with open(genome_file.file_path, 'r') as f:
                for line in f:
                    if line.startswith('>'):
                        # 提取染色体名称（去掉>符号和后续描述）
                        chrom_name = line.strip().split()[0][1:]
                        chromosomes.append(chrom_name)
        except Exception as e:
            logger.error(f"解析基因组文件失败: {str(e)}")
            return Response(
                {"error": f"解析基因组文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(chromosomes)

    @action(detail=False, methods=['get'])
    def get_chromosome_length(self, request):
        """获取指定生物体和染色体的实际长度"""
        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 查找对应的基因组文件
        genome_file = GenomeFile.objects.filter(
            organism=organism,
            category='genome'
        ).first()

        if not genome_file:
            return Response(
                {"error": f"未找到 {organism} 的基因组文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析FASTA文件获取指定染色体的长度
        try:
            from Bio import SeqIO
            import gzip

            # 检查文件是否是压缩文件
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

            # 如果没有找到指定的染色体
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

    @action(detail=False, methods=['get'])
    def get_tes(self, request):
        """获取指定生物体和染色体的TEs数据"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"get_tes called with path: {request.path}, method: {request.method}")

        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')

        logger.info(f"get_tes parameters - organism: {organism}, chromosome: {chromosome}")

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 构建TEs文件路径 - 从tar.gz压缩包中读取
        manual_files_dir = settings.MANUAL_FILES_DIR
        tar_file_path = os.path.join(manual_files_dir, f'TEs.{organism}.tar.gz')
        target_file_name = f'{organism}.fasta.mod.EDTA.TEanno.gff3'

        logger.info(f"Looking for TEs tar file at: {tar_file_path}")
        logger.info(f"Target file in tar: {target_file_name}")

        if not os.path.exists(tar_file_path):
            return Response(
                {"error": f"未找到 {organism} 的TEs压缩文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析GFF3文件获取TEs数据
        tes_data = []
        count = 0
        max_records = 1000  # 限制返回的记录数量，避免前端性能问题

        try:
            import tarfile

            # 从tar.gz文件中读取目标文件
            with tarfile.open(tar_file_path, 'r:gz') as tar:
                # 查找目标文件
                target_member = None
                for member in tar.getmembers():
                    if member.name.endswith(target_file_name) or member.name == target_file_name:
                        target_member = member
                        break

                if target_member is None:
                    return Response(
                        {"error": f"在压缩包中未找到文件 {target_file_name}"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # 读取文件内容
                file_obj = tar.extractfile(target_member)
                if file_obj is None:
                    return Response(
                        {"error": f"无法读取压缩包中的文件 {target_file_name}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # 逐行处理文件内容
                for line_bytes in file_obj:
                    line = line_bytes.decode('utf-8').strip()
                    # 跳过注释行和空行
                    if line.startswith('#') or not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 9:
                        seqid = parts[0]
                        source = parts[1]
                        sequence_ontology = parts[2]
                        start = int(parts[3])
                        end = int(parts[4])
                        score = parts[5]
                        strand = parts[6]
                        phase = parts[7]
                        attributes = parts[8]

                        # 只返回指定染色体的数据
                        if seqid == chromosome:
                            # 限制记录数量
                            if count >= max_records:
                                break

                            # 解析attributes字段，只保留重要的属性
                            attr_dict = {}
                            for attr in attributes.split(';'):
                                if '=' in attr:
                                    key, value = attr.split('=', 1)
                                    # 只保留重要的属性
                                    if key in ['ID', 'Name', 'Classification', 'Identity', 'Method']:
                                        attr_dict[key] = value

                            tes_data.append({
                                'seqid': seqid,
                                'source': source,
                                'sequence_ontology': sequence_ontology,
                                'start': start,
                                'end': end,
                                'score': score,
                                'strand': strand,
                                'phase': phase,
                                'attributes': attr_dict
                            })
                            count += 1
        except Exception as e:
            logger.error(f"解析TEs文件失败: {str(e)}")
            return Response(
                {"error": f"解析TEs文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(tes_data)

    @action(detail=False, methods=['get'])
    def get_codon_data(self, request):
        """获取指定生物体的密码子使用偏好性数据"""
        import logging
        import tarfile
        import re

        logger = logging.getLogger(__name__)
        organism = request.query_params.get('organism')

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查是否是CodonW分析结果
        if organism.startswith('CodonW Analysis (Task:') and organism.endswith(')'):
            # 提取task_id
            import re
            match = re.search(r'Task:\s*([^)]+)', organism)
            if match:
                task_id = match.group(1).strip()
                logger.info(f"检测到CodonW分析结果请求，任务ID: {task_id}")
                # 调用codonw_results方法的逻辑
                return self._get_codonw_results_data(task_id)

        # 构建codon文件路径 - 从tar.gz压缩包中读取
        manual_files_dir = settings.MANUAL_FILES_DIR
        tar_file_path = os.path.join(manual_files_dir, f'codon.{organism}.tar.gz')

        logger.info(f"Looking for codon tar file at: {tar_file_path}")

        if not os.path.exists(tar_file_path):
            return Response(
                {"error": f"未找到 {organism} 的codon压缩文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            codon_data = {
                'organism': organism,
                'codon_usage': {},
                'statistics': {},
                'amino_acids': {}
            }

            with tarfile.open(tar_file_path, 'r:gz') as tar:
                # 读取密码子使用频率文件 (.blk)
                blk_member = None
                stats_member = None

                for member in tar.getmembers():
                    if member.name.endswith('.blk'):
                        blk_member = member
                    elif member.name.endswith('.fa.txt'):
                        stats_member = member

                # 解析密码子使用频率数据
                if blk_member:
                    file_obj = tar.extractfile(blk_member)
                    if file_obj:
                        content = file_obj.read().decode('utf-8')
                        codon_data['codon_usage'] = self._parse_codon_usage(content)
                        codon_data['amino_acids'] = self._group_by_amino_acid(codon_data['codon_usage'])

                # 解析统计数据
                if stats_member:
                    file_obj = tar.extractfile(stats_member)
                    if file_obj:
                        content = file_obj.read().decode('utf-8')
                        codon_data['statistics'] = self._parse_codon_statistics(content)

            return Response(codon_data)

        except Exception as e:
            logger.error(f"解析codon文件失败: {str(e)}")
            return Response(
                {"error": f"解析codon文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        """获取指定生物体和染色体的centromere数据"""
        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 构建centromere文件路径
        manual_files_dir = settings.MANUAL_FILES_DIR
        centromere_bed_path = os.path.join(manual_files_dir, f'centromere.{organism}.bed')

        if not os.path.exists(centromere_bed_path):
            return Response(
                {"error": f"未找到 {organism} 的centromere文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析BED文件获取centromere数据
        centromere_data = []
        try:
            with open(centromere_bed_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 3:
                        seqid = parts[0]
                        start = int(parts[1])
                        end = int(parts[2])

                        # 只返回指定染色体的数据
                        if seqid == chromosome:
                            centromere_data.append({
                                'seqid': seqid,
                                'start': start,
                                'end': end
                            })
        except Exception as e:
            logger.error(f"解析centromere文件失败: {str(e)}")
            return Response(
                {"error": f"解析centromere文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(centromere_data)

    @action(detail=False, methods=['get'])
    def get_coreblocks(self, request):
        """获取指定生物体和染色体的coreBlocks数据"""
        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 构建coreBlocks文件路径
        manual_files_dir = settings.MANUAL_FILES_DIR
        coreblocks_bed_path = os.path.join(manual_files_dir, f'coreBlocks.{organism}.bed')

        if not os.path.exists(coreblocks_bed_path):
            return Response(
                {"error": f"未找到 {organism} 的coreBlocks文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析BED文件获取coreBlocks数据
        coreblocks_data = []
        try:
            with open(coreblocks_bed_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 3:
                        seqid = parts[0]
                        start = int(parts[1])
                        end = int(parts[2])

                        # 只返回指定染色体的数据
                        if seqid == chromosome:
                            coreblocks_data.append({
                                'seqid': seqid,
                                'start': start,
                                'end': end,
                                'length': end - start
                            })
        except Exception as e:
            logger.error(f"解析coreBlocks文件失败: {str(e)}")
            return Response(
                {"error": f"解析coreBlocks文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(coreblocks_data)

    @action(detail=False, methods=['get'])
    def get_annotation_data(self, request):
        """获取指定生物体的注释数据"""
        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')
        feature_type = request.query_params.get('feature_type', 'all')  # gene, mRNA, exon, CDS, all
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 构建注释文件路径
        manual_files_dir = settings.MANUAL_FILES_DIR
        annotation_file_path = os.path.join(manual_files_dir, f'annotation.{organism}.gff')

        if not os.path.exists(annotation_file_path):
            return Response(
                {"error": f"未找到 {organism} 的注释文件"},
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
            'statistics': {
                'chromosomes': sorted(list(chromosomes)),
                'feature_types': sorted(list(feature_types)),
                'total_features': total_count
            }
        })

    @action(detail=False, methods=['get'])
    def get_rna_data(self, request):
        """获取指定生物体和染色体的RNA数据（rRNA, miRNA, tRNA）"""
        organism = request.query_params.get('organism')
        chromosome = request.query_params.get('chromosome')
        rna_type = request.query_params.get('type')  # rRNA, miRNA, tRNA

        if not organism:
            return Response(
                {"error": "缺少必要的参数: organism"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not chromosome:
            return Response(
                {"error": "缺少必要的参数: chromosome"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not rna_type or rna_type not in ['rRNA', 'miRNA', 'tRNA']:
            return Response(
                {"error": "缺少或无效的参数: type (必须是 rRNA, miRNA, tRNA 之一)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 构建RNA文件路径
        manual_files_dir = settings.MANUAL_FILES_DIR
        rna_bed_path = os.path.join(manual_files_dir, f'{rna_type}.{organism}.bed')

        if not os.path.exists(rna_bed_path):
            return Response(
                {"error": f"未找到 {organism} 的{rna_type}文件"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 解析BED文件获取RNA数据
        rna_data = []
        count = 0
        max_records = 1000  # 限制返回的记录数量

        try:
            with open(rna_bed_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 4:
                        # 处理不同格式的BED文件
                        if rna_type == 'miRNA' and len(parts) >= 8:
                            # miRNA格式: name family seqid start end strand score e_value
                            name = parts[0]
                            family = parts[1]
                            seqid = parts[2]
                            start = int(parts[3])
                            end = int(parts[4])
                            strand = parts[5] if len(parts) > 5 else '.'
                            score = parts[6] if len(parts) > 6 else '.'
                            e_value = parts[7] if len(parts) > 7 else '.'

                            # 只返回指定染色体的数据
                            if seqid == chromosome:
                                if count >= max_records:
                                    break

                                rna_data.append({
                                    'seqid': seqid,
                                    'start': start,
                                    'end': end,
                                    'name': name,
                                    'family': family,
                                    'strand': strand,
                                    'score': score,
                                    'e_value': e_value,
                                    'type': rna_type
                                })
                                count += 1
                        else:
                            # rRNA和tRNA格式: seqid start end name
                            seqid = parts[0]
                            start = int(parts[1])
                            end = int(parts[2])
                            name = parts[3] if len(parts) > 3 else ''

                            # 只返回指定染色体的数据
                            if seqid == chromosome:
                                if count >= max_records:
                                    break

                                rna_data.append({
                                    'seqid': seqid,
                                    'start': start,
                                    'end': end,
                                    'name': name,
                                    'type': rna_type
                                })
                                count += 1
        except Exception as e:
            logger.error(f"解析{rna_type}文件失败: {str(e)}")
            return Response(
                {"error": f"解析{rna_type}文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(rna_data)

    @action(detail=False, methods=['get'])
    def scan_directory(self, request):
        """扫描目录，自动添加文件到数据库并清理不存在的文件记录"""
        try:
            directory = settings.MANUAL_FILES_DIR
            files_added = 0
            files_removed = 0
            
            if not os.path.exists(directory):
                return Response(
                    {"error": f"目录不存在: {directory}"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 获取所有现存文件的路径集合
            existing_files = set()
            for root, _, files in os.walk(directory):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    existing_files.add(file_path)
            
            # 清理数据库中不存在的文件记录
            for file_obj in GenomeFile.objects.all():
                if file_obj.file_path not in existing_files:
                    file_obj.delete()
                    files_removed += 1
            
            # 获取有效的文件扩展名映射
            extension_map = {}
            for file_type in FileType.objects.all():
                extension_map[file_type.extension] = file_type
                
            # 定义有效的组织类型，这些不应被视为生物体/物种
            tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
                
            # 扫描目录中的文件（包括子目录）
            for root, _, files in os.walk(directory):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    
                    # 检查文件是否已存在
                    if GenomeFile.objects.filter(file_path=file_path).exists():
                        continue
                        
                    parts = filename.split('.')
                    extension = parts[-1] if len(parts) > 1 else ''
                    
                    # 特殊处理压缩文件格式
                    if extension in ['gz', 'zip', 'bz2', 'xz']:
                        if len(parts) > 2:
                            extension = f"{parts[-2]}.{parts[-1]}"  # 例如: fasta.gz
                    
                    # 获取或创建文件类型
                    file_type = extension_map.get(extension)
                    if not file_type:
                        file_type = FileType.objects.create(
                            name=extension.upper() if extension else 'UNKNOWN',
                            extension=extension
                        )
                        extension_map[extension] = file_type
                    
                    # 处理不同的文件命名格式
                    
                    # 1. 处理格式: transcriptome.type.organism.extension[.gz]
                    # 例如: transcriptome.leaf.MH63.fastaq.gz
                    if len(parts) >= 4 and parts[0] == 'transcriptome' and parts[1] in tissue_types:
                        tissue_type = parts[1]
                        organism = parts[2]
                        category = f"transcriptome.{tissue_type}"
                        
                        # 确保这个organism是有效的生物体，而不是组织类型
                        if organism in tissue_types:
                            # 如果organism是组织类型，可能文件命名有问题，跳过或处理
                            logger.warning(f"文件名格式有问题，organism与组织类型冲突: {filename}")
                            continue
                        
                        GenomeFile.objects.create(
                            name=filename,
                            organism=organism,
                            category=category,
                            file_path=file_path,
                            file_type=file_type,
                            size=os.path.getsize(file_path)
                        )
                        files_added += 1
                    
                    # 2. 处理注释数据文件格式: annotation.organism.gff[.gz]
                    # 例如: annotation.MH63.gff, annotation.ZS97.gff.gz
                    elif len(parts) >= 3 and parts[0] == 'annotation' and (parts[-1] == 'gff' or (len(parts) > 3 and parts[-2] == 'gff')):
                        organism = parts[1]
                        category = 'annotation'
                        
                        # 确保organism不是组织类型
                        if organism in tissue_types:
                            logger.warning(f"文件名格式有问题，organism与组织类型冲突: {filename}")
                            continue
                        
                        GenomeFile.objects.create(
                            name=filename,
                            organism=organism,
                            category=category,
                            file_path=file_path,
                            file_type=file_type,
                            size=os.path.getsize(file_path)
                        )
                        files_added += 1

                    # 3. 处理coreBlocks数据文件格式: coreBlocks.organism.bed[.gz]
                    # 例如: coreBlocks.IR64.bed, coreBlocks.MH63.bed.gz
                    elif len(parts) >= 3 and parts[0] == 'coreBlocks' and (parts[-1] == 'bed' or (len(parts) > 3 and parts[-2] == 'bed')):
                        organism = parts[1]
                        category = 'coreBlocks'

                        # 确保organism不是组织类型
                        if organism in tissue_types:
                            logger.warning(f"文件名格式有问题，organism与组织类型冲突: {filename}")
                            continue

                        GenomeFile.objects.create(
                            name=filename,
                            organism=organism,
                            category=category,
                            file_path=file_path,
                            file_type=file_type,
                            size=os.path.getsize(file_path)
                        )
                        files_added += 1

                    # 4. 处理格式: category.organism.extension[.gz]
                    # 例如: transcriptome.MH63.fasta, genome.ZS97.fasta.gz
                    elif len(parts) >= 3:
                        category = parts[0]
                        organism = parts[1]
                        
                        # 确保organism不是组织类型
                        if organism in tissue_types:
                            # 这可能是转录组类型的文件，使用不同的解析方式
                            if category == 'transcriptome':
                                tissue_type = organism  # 组织类型实际上是第二个部分
                                organism = parts[2] if len(parts) > 2 else 'unknown'  # 生物体是第三个部分
                                category = f"transcriptome.{tissue_type}"
                            else:
                                # 如果不是转录组但organism是组织类型，可能文件命名有问题
                                logger.warning(f"文件名格式有问题，organism与组织类型冲突: {filename}")
                                continue
                        
                        # 验证category和organism
                        valid_category = False
                        for cat_choice, _ in GenomeFile.FILE_CATEGORY_CHOICES:
                            if cat_choice == category:
                                valid_category = True
                                break
                        
                        # 验证organism是否有效（不为空且不是组织类型）
                        valid_organism = organism and organism not in tissue_types

                        if valid_category and valid_organism:
                            GenomeFile.objects.create(
                                name=filename,
                                organism=organism,
                                category=category,
                                file_path=file_path,
                                file_type=file_type,
                                size=os.path.getsize(file_path)
                            )
                            files_added += 1
                        else:
                            # 如果不符合预期格式，记录但不抛出错误
                            logger.warning(f"文件名格式不符合预期: {filename}")
                    
                    else:
                        # 如果不符合预期格式，记录但不抛出错误
                        logger.warning(f"文件名格式不符合预期: {filename}")
            
            # 清理不再使用的Organism记录
            # 获取当前所有文件中使用的organism
            active_organisms = set(GenomeFile.objects.values_list('organism', flat=True).distinct())
            
            # 从Organism表中删除不再使用的记录
            from files.models import Organism
            deleted_organisms = 0
            for org in Organism.objects.all():
                if org.code not in active_organisms:
                    org.delete()
                    deleted_organisms += 1
                    logger.info(f"删除不再使用的生物体记录: {org.code}")
            
            return Response({
                "message": f"成功添加 {files_added} 个文件，删除 {files_removed} 个不存在的文件记录，清理 {deleted_organisms} 个不再使用的生物体记录",
                "details": f"扫描目录: {directory}"
            })
        
        except Exception as e:
            logger.error(f"扫描目录失败: {str(e)}")
            return Response(
                {"error": f"扫描目录失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        """获取生物体列表，支持搜索参数"""
        try:
            # 获取搜索参数
            search = request.query_params.get('search', '').strip()

            # 1. 首先尝试使用静态方法获取所有生物体
            if hasattr(GenomeFile, 'get_all_organisms'):
                organisms = GenomeFile.get_all_organisms()
                logger.info(f"使用get_all_organisms方法获取生物体列表: {organisms}")
            else:
                # 2. 如果静态方法不存在，回退到从数据库中获取
                organisms = list(GenomeFile.objects.values_list('organism', flat=True).distinct())

                # 3. 过滤掉组织类型，它们不应该被当作生物体
                tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
                organisms = [org for org in organisms if org not in tissue_types]

                # 4. 排序结果
                organisms.sort()
                logger.info(f"从数据库获取生物体列表: {organisms}")

            # 5. 如果有搜索条件，进行过滤
            if search:
                organisms = [org for org in organisms if search.lower() in org.lower()]
                logger.info(f"搜索'{search}'后的生物体列表: {organisms}")

            # 如果列表为空，返回空列表
            if not organisms:
                logger.info("生物体列表为空，返回空列表")
                return Response([])

            return Response(organisms)
        except Exception as e:
            logger.error(f"获取生物体列表时发生错误: {str(e)}")
            # 出错时返回空列表
            return Response([])

    @action(detail=False, methods=['get'])
    def organisms_with_annotation(self, request):
        """获取有注释文件的生物体列表"""
        try:
            # 获取所有生物体列表
            if hasattr(GenomeFile, 'get_all_organisms'):
                all_organisms = GenomeFile.get_all_organisms()
            else:
                all_organisms = list(GenomeFile.objects.values_list('organism', flat=True).distinct())
                tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
                all_organisms = [org for org in all_organisms if org not in tissue_types]

            # 检查每个生物体是否有注释文件
            organisms_with_annotation = []
            manual_files_dir = settings.MANUAL_FILES_DIR

            for organism in all_organisms:
                annotation_file_path = os.path.join(manual_files_dir, f'annotation.{organism}.gff')
                if os.path.exists(annotation_file_path):
                    organisms_with_annotation.append(organism)

            # 排序结果
            organisms_with_annotation.sort()
            logger.info(f"有注释文件的生物体列表: {organisms_with_annotation}")

            return Response(organisms_with_annotation)
        except Exception as e:
            logger.error(f"获取有注释文件的生物体列表时发生错误: {str(e)}")
            # 出错时返回空列表
            return Response([])

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
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    logger.info(f"ZIP文件已解压到: {extract_dir}")

                    # 列出解压后的文件
                    extracted_files = []
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            extracted_files.append(os.path.join(root, file))
                    logger.info(f"解压后的文件: {extracted_files}")

                except zipfile.BadZipFile:
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
        """获取分页的数据一览表"""
        try:
            # 获取查询参数
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            search = request.query_params.get('search', '')
            # 获取亚群筛选参数，支持多个亚群，用逗号分隔
            sub_populations = request.query_params.get('sub_populations', '')

            # 定义已知的组织类型，这些不应该被当作生物体
            tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']

            # 获取所有文件，按生物体分组，排除组织类型和无效的organism值
            files = GenomeFile.objects.exclude(organism__in=tissue_types).exclude(
                organism__isnull=True
            ).exclude(organism='').exclude(organism='unknown')

            # 如果有搜索条件，过滤生物体
            if search:
                files = files.filter(organism__icontains=search)

            # 按生物体分组处理
            organism_map = {}
            for file in files:
                organism = file.organism
                if organism not in organism_map:
                    organism_map[organism] = {
                        'accession': organism,
                        'genome': None,
                        'annotation': None,
                        'hasTranscriptome': False,
                        'codon': None,
                        'centromere': None,
                        'TEs': None,
                        'coreBlocks': None,
                        'miRNA': None,
                        'tRNA': None,
                        'rRNA': None,
                        'subPopulation': None,
                        'seqData': None,
                        'longitude': None,
                        'latitude': None
                    }

                organism_data = organism_map[organism]

                # 处理转录组特殊类型
                if file.category.startswith('transcriptome.'):
                    organism_data['hasTranscriptome'] = True
                else:
                    # 对应类别的文件
                    organism_data[file.category] = {
                        'id': file.id,
                        'name': file.name,
                        'file_path': file.file_path,
                        'size': file.size,
                        'created_at': file.created_at
                    }

            # 获取补充数据
            supplementary_data = self._load_supplementary_data()

            # 合并补充数据
            for organism_data in organism_map.values():
                supplementary = supplementary_data.get(organism_data['accession'])
                if supplementary:
                    organism_data['subPopulation'] = supplementary.get('sub_population')
                    organism_data['seqData'] = supplementary.get('seq_data')
                    organism_data['longitude'] = supplementary.get('longitude')
                    organism_data['latitude'] = supplementary.get('latitude')
                else:
                    # 确保没有补充数据的organism也有这些字段，值为None
                    organism_data['subPopulation'] = None
                    organism_data['seqData'] = None
                    organism_data['longitude'] = None
                    organism_data['latitude'] = None

            # 转换为列表并排序
            organisms_list = list(organism_map.values())
            organisms_list.sort(key=lambda x: x['accession'])

            # 亚群筛选
            if sub_populations:
                if sub_populations == 'NONE':
                    # 如果前端发送 'NONE'，表示没有选择任何亚群，返回空结果
                    organisms_list = []
                else:
                    selected_populations = [pop.strip() for pop in sub_populations.split(',') if pop.strip()]
                    if selected_populations:
                        filtered_organisms = []
                        for organism in organisms_list:
                            organism_sub_pop = organism.get('subPopulation')

                            # 检查是否匹配选中的亚群
                            if organism_sub_pop in selected_populations:
                                filtered_organisms.append(organism)
                            # 检查是否选中了"未知亚群"且当前生物体没有亚群信息
                            elif '未知亚群' in selected_populations and not organism_sub_pop:
                                filtered_organisms.append(organism)

                        organisms_list = filtered_organisms

            # 手动分页
            total = len(organisms_list)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = organisms_list[start_index:end_index]

            # 返回分页结果
            return Response({
                'count': total,
                'next': f"?page={page + 1}&page_size={page_size}" if end_index < total else None,
                'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
                'results': paginated_data
            })

        except Exception as e:
            logger.error(f"获取分页数据失败: {str(e)}")
            return Response(
                {"error": f"获取分页数据失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取所有文件类别列表"""
        categories = GenomeFile.get_all_categories()
        return Response(categories)

    @action(detail=False, methods=['get'])
    def all_files(self, request):
        """获取所有文件（不分页，用于特殊页面如转录组概览）"""
        try:
            # 定义已知的组织类型，这些不应该被当作生物体
            tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']

            # 获取所有文件，排除组织类型
            files = GenomeFile.objects.exclude(organism__in=tissue_types)

            # 序列化数据
            serializer = GenomeFileListSerializer(files, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"获取所有文件失败: {str(e)}")
            return Response(
                {"error": f"获取所有文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def sub_populations(self, request):
        """获取所有可用的亚群列表"""
        try:
            supplementary_data = self._load_supplementary_data()

            # 提取所有不为空的亚群
            sub_populations = set()
            for data in supplementary_data.values():
                sub_pop = data.get('sub_population')
                if sub_pop and sub_pop.strip():
                    sub_populations.add(sub_pop.strip())

            # 转换为排序后的列表
            sub_populations_list = sorted(list(sub_populations))

            # 添加"未知亚群"选项
            sub_populations_list.append('未知亚群')

            return Response(sub_populations_list)

        except Exception as e:
            logger.error(f"获取亚群列表失败: {str(e)}")
            return Response(
                {"error": f"获取亚群列表失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def transcriptome_types(self, request):
        """获取所有转录组类型"""
        types = GenomeFile.get_transcriptome_types()
        return Response(types)

    @action(detail=False, methods=['get'])
    def paginated_transcriptome_overview(self, request):
        """获取分页的转录组一览表"""
        try:
            # 获取查询参数
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            search = request.query_params.get('search', '')
            # 获取亚群筛选参数，支持多个亚群，用逗号分隔
            sub_populations = request.query_params.get('sub_populations', '')

            # 定义已知的组织类型，这些不应该被当作生物体
            tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']

            # 获取所有转录组文件，按生物体分组，排除组织类型和无效的organism值
            files = GenomeFile.objects.filter(
                category__startswith='transcriptome.'
            ).exclude(organism__in=tissue_types).exclude(
                organism__isnull=True
            ).exclude(organism='').exclude(organism='unknown')

            # 如果有搜索条件，过滤生物体
            if search:
                files = files.filter(organism__icontains=search)

            # 按生物体分组
            organism_map = {}
            for file in files:
                organism = file.organism
                if organism not in organism_map:
                    organism_map[organism] = {
                        'accession': organism,
                        'transcriptomeTypes': set()
                    }

                # 提取转录组类型
                type_part = file.category.split('.')[1] if '.' in file.category else 'all'
                organism_map[organism]['transcriptomeTypes'].add(type_part)

            # 获取补充数据（亚群信息）
            try:
                supplementary_data_file = os.path.join(settings.MEDIA_ROOT, 'genome-files', 'supplementary_data', 'supplementary_data.json')
                if os.path.exists(supplementary_data_file):
                    with open(supplementary_data_file, 'r', encoding='utf-8') as f:
                        supplementary_data = json.load(f)
                else:
                    supplementary_data = {}
            except Exception as e:
                logger.warning(f"读取补充数据失败: {str(e)}")
                supplementary_data = {}

            # 构建结果列表
            organisms_list = []
            for organism, data in organism_map.items():
                # 获取亚群信息
                sub_population = supplementary_data.get(organism, {}).get('sub_population', None)

                organism_data = {
                    'accession': organism,
                    'subPopulation': sub_population,
                    'transcriptomeTypes': list(data['transcriptomeTypes'])
                }
                organisms_list.append(organism_data)

            # 亚群筛选
            if sub_populations and sub_populations != 'NONE':
                if sub_populations == '':
                    # 如果参数为空字符串，返回所有数据
                    pass
                else:
                    # 解析亚群筛选参数
                    selected_sub_populations = [sp.strip() for sp in sub_populations.split(',') if sp.strip()]
                    if selected_sub_populations:
                        organisms_list = [
                            org for org in organisms_list
                            if org['subPopulation'] in selected_sub_populations
                        ]
            elif sub_populations == 'NONE':
                # 如果参数为'NONE'，返回空结果
                organisms_list = []

            # 按accession排序
            organisms_list.sort(key=lambda x: x['accession'])

            # 手动分页
            total = len(organisms_list)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = organisms_list[start_index:end_index]

            # 返回分页结果
            return Response({
                'count': total,
                'next': f"?page={page + 1}&page_size={page_size}" if end_index < total else None,
                'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
                'results': paginated_data
            })

        except Exception as e:
            logger.error(f"获取分页转录组数据失败: {str(e)}")
            return Response(
                {"error": f"获取分页转录组数据失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


# ==================== 管理后台API ====================

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


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_files_list(request):
    """获取文件列表（管理后台）"""
    try:
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')
        category = request.GET.get('category', '')
        organism = request.GET.get('organism', '')

        # 构建查询
        queryset = GenomeFile.objects.all()

        if search:
            queryset = queryset.filter(name__icontains=search)
        if category:
            queryset = queryset.filter(category=category)
        if organism:
            queryset = queryset.filter(organism=organism)

        # 排序
        queryset = queryset.order_by('-id')

        # 分页
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        files = queryset[start:end]

        # 序列化数据
        files_data = []
        for file_obj in files:
            files_data.append({
                'id': file_obj.id,
                'name': file_obj.name,
                'organism': file_obj.organism,
                'category': file_obj.category,
                'file_type': file_obj.file_type.name if file_obj.file_type else '',
                'size': file_obj.size,
                'file_path': file_obj.file_path,
                'created_at': file_obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(file_obj, 'created_at') else '',
                'exists': os.path.exists(file_obj.file_path) if file_obj.file_path else False
            })

        return Response({
            'success': True,
            'data': files_data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })

    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        return Response({
            'success': False,
            'message': '获取文件列表失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def admin_delete_file(request, file_id):
    """删除文件"""
    try:
        file_obj = GenomeFile.objects.get(id=file_id)

        # 删除物理文件
        if file_obj.file_path and os.path.exists(file_obj.file_path):
            os.remove(file_obj.file_path)
            logger.info(f"删除物理文件: {file_obj.file_path}")

        # 删除数据库记录
        file_name = file_obj.name
        file_obj.delete()

        return Response({
            'success': True,
            'message': f'文件 {file_name} 删除成功'
        })

    except GenomeFile.DoesNotExist:
        return Response({
            'success': False,
            'message': '文件不存在'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'删除文件失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_batch_delete(request):
    """批量删除文件"""
    try:
        data = json.loads(request.body)
        file_ids = data.get('file_ids', [])

        if not file_ids:
            return Response({
                'success': False,
                'message': '请选择要删除的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        deleted_count = 0
        failed_files = []

        for file_id in file_ids:
            try:
                file_obj = GenomeFile.objects.get(id=file_id)

                # 删除物理文件
                if file_obj.file_path and os.path.exists(file_obj.file_path):
                    os.remove(file_obj.file_path)

                # 删除数据库记录
                file_obj.delete()
                deleted_count += 1

            except GenomeFile.DoesNotExist:
                failed_files.append(f"ID {file_id}: 文件不存在")
            except Exception as e:
                failed_files.append(f"ID {file_id}: {str(e)}")

        message = f"成功删除 {deleted_count} 个文件"
        if failed_files:
            message += f"，失败 {len(failed_files)} 个"

        return Response({
            'success': True,
            'message': message,
            'deleted_count': deleted_count,
            'failed_files': failed_files
        })

    except Exception as e:
        logger.error(f"批量删除失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'批量删除失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_batch_download(request):
    """批量下载文件"""
    try:
        data = json.loads(request.body)
        file_ids = data.get('file_ids', [])

        if not file_ids:
            return Response({
                'success': False,
                'message': '请选择要下载的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 获取文件对象
        files_to_download = []
        failed_files = []

        for file_id in file_ids:
            try:
                file_obj = GenomeFile.objects.get(id=file_id)

                # 检查文件是否存在
                if file_obj.file_path and os.path.exists(file_obj.file_path):
                    files_to_download.append(file_obj)
                else:
                    failed_files.append(f"ID {file_id}: 文件不存在")

            except GenomeFile.DoesNotExist:
                failed_files.append(f"ID {file_id}: 文件不存在")
            except Exception as e:
                failed_files.append(f"ID {file_id}: {str(e)}")

        if not files_to_download:
            return Response({
                'success': False,
                'message': '没有可下载的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 创建ZIP文件
        import zipfile
        import tempfile
        from datetime import datetime

        # 创建临时ZIP文件
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')

        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_obj in files_to_download:
                try:
                    # 添加文件到ZIP，使用原始文件名
                    zipf.write(file_obj.file_path, file_obj.name)
                except Exception as e:
                    failed_files.append(f"{file_obj.name}: {str(e)}")

        # 生成下载文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'batch_download_{timestamp}.zip'

        # 返回文件响应
        response = FileResponse(
            open(temp_zip.name, 'rb'),
            as_attachment=True,
            filename=zip_filename
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
        logger.error(f"批量下载失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'批量下载失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_upload_file(request):
    """文件上传"""
    try:
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'message': '请选择要上传的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['file']
        filename = uploaded_file.name

        # 保存文件到manual_files目录
        manual_files_dir = settings.MANUAL_FILES_DIR
        if not os.path.exists(manual_files_dir):
            os.makedirs(manual_files_dir)

        file_path = os.path.join(manual_files_dir, filename)

        # 检查文件是否已存在
        if os.path.exists(file_path):
            return Response({
                'success': False,
                'message': f'文件 {filename} 已存在'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 保存文件
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # 自动识别文件类型和分类
        file_info = _analyze_uploaded_file(filename, file_path)

        # 创建数据库记录
        file_type = None
        if file_info['extension']:
            file_type = FileType.objects.filter(extension=file_info['extension']).first()

        genome_file = GenomeFile.objects.create(
            name=filename,
            organism=file_info['organism'],
            category=file_info['category'],
            file_path=file_path,
            file_type=file_type,
            size=os.path.getsize(file_path)
        )

        return Response({
            'success': True,
            'message': f'文件 {filename} 上传成功',
            'file_info': {
                'id': genome_file.id,
                'name': filename,
                'organism': file_info['organism'],
                'category': file_info['category'],
                'size': genome_file.size
            }
        })

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'文件上传失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        elif len(parts) >= 3 and parts[0] == 'coreBlocks':
            organism = parts[1]
            category = 'coreBlocks'

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
    """获取统计信息"""
    try:
        # 文件总数
        total_files = GenomeFile.objects.count()

        # 按类别统计
        category_stats = {}

        # 获取补充数据以统计Accession数量
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
                    if len(parts) >= 1:  # 至少要有accession
                        accession = parts[0].strip()
                        supplementary_data[accession] = True

        for choice in GenomeFile.FILE_CATEGORY_CHOICES:
            category = choice[0]
            category_name = choice[1]

            # 文件数量
            files = GenomeFile.objects.filter(category=category)
            file_count = files.count()

            if file_count > 0:
                # 文件总大小
                total_size = 0
                for file_obj in files:
                    if file_obj.size:
                        total_size += file_obj.size

                # Accession数量（除了"其他"类型，所有类型都统计）
                accession_count = 0
                if category != 'other':
                    # 从文件名中提取Accession
                    accessions = set()
                    for file_obj in files:
                        # 提取文件名中的Accession部分
                        filename = file_obj.name
                        parts = filename.split('.')
                        potential_accession = None

                        # 处理不同的文件命名格式
                        if category.startswith('transcriptome.'):
                            # 转录组文件格式: transcriptome.type.accession.extension
                            # 例如: transcriptome.root.IR64.tar.gz
                            if len(parts) >= 3:
                                potential_accession = parts[2]
                        else:
                            # 其他文件格式: category.accession.extension
                            # 例如: genome.IR64.fasta, miRNA.IR64.bed
                            if len(parts) >= 2:
                                potential_accession = parts[1]

                        # 检查是否在补充数据中存在
                        if potential_accession and potential_accession in supplementary_data:
                            accessions.add(potential_accession)

                    accession_count = len(accessions)

                category_stats[category_name] = {
                    'file_count': file_count,
                    'total_size': total_size,
                    'accession_count': accession_count if category != 'other' else None
                }

        # 按生物体统计
        organism_stats = {}
        organisms = GenomeFile.objects.values_list('organism', flat=True).distinct()
        for organism in organisms:
            count = GenomeFile.objects.filter(organism=organism).count()
            organism_stats[organism] = count

        # 文件大小统计
        total_size = 0
        for file_obj in GenomeFile.objects.all():
            if file_obj.size:
                total_size += file_obj.size

        # 检查文件存在性
        existing_files = 0
        missing_files = 0
        for file_obj in GenomeFile.objects.all():
            if file_obj.file_path and os.path.exists(file_obj.file_path):
                existing_files += 1
            else:
                missing_files += 1

        return Response({
            'success': True,
            'data': {
                'total_files': total_files,
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'existing_files': existing_files,
                'missing_files': missing_files,
                'category_stats': category_stats,
                'organism_stats': organism_stats
            }
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return Response({
            'success': False,
            'message': '获取统计信息失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_rescan_files(request):
    """重新扫描文件目录"""
    try:
        directory = settings.MANUAL_FILES_DIR
        files_added = 0
        files_removed = 0

        if not os.path.exists(directory):
            return Response({
                'success': False,
                'message': f'目录不存在: {directory}'
            }, status=status.HTTP_404_NOT_FOUND)

        # 获取所有现存文件的路径集合
        existing_files = set()
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                existing_files.add(file_path)

        # 清理数据库中不存在的文件记录
        for file_obj in GenomeFile.objects.all():
            if file_obj.file_path not in existing_files:
                file_obj.delete()
                files_removed += 1

        # 扫描新文件并添加到数据库
        for file_path in existing_files:
            if not GenomeFile.objects.filter(file_path=file_path).exists():
                filename = os.path.basename(file_path)
                file_info = _analyze_uploaded_file(filename, file_path)

                # 获取文件类型
                file_type = None
                if file_info['extension']:
                    file_type = FileType.objects.filter(extension=file_info['extension']).first()

                # 创建数据库记录
                GenomeFile.objects.create(
                    name=filename,
                    organism=file_info['organism'],
                    category=file_info['category'],
                    file_path=file_path,
                    file_type=file_type,
                    size=os.path.getsize(file_path)
                )
                files_added += 1

        return Response({
            'success': True,
            'message': f'扫描完成：新增 {files_added} 个文件，清理 {files_removed} 个无效记录',
            'files_added': files_added,
            'files_removed': files_removed
        })

    except Exception as e:
        logger.error(f"重新扫描失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'重新扫描失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_download_file(request, file_id):
    """下载文件（管理后台）"""
    try:
        file_obj = GenomeFile.objects.get(id=file_id)
        file_path = file_obj.file_path

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return Response({
                'success': False,
                'message': '文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        # 获取文件类型
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        # 创建文件响应
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

    except GenomeFile.DoesNotExist:
        return Response({
            'success': False,
            'message': '文件不存在'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        return Response({
            'success': False,
            'message': '下载文件失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    """下载数据文件"""
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

        # 查找文件
        file_path = None
        for pattern in file_patterns[file_type]:
            potential_path = os.path.join(manual_files_dir, pattern)
            if os.path.exists(potential_path):
                file_path = potential_path
                break

        if not file_path:
            return Response({
                'success': False,
                'message': f'未找到 {accession} 的 {file_type} 文件'
            }, status=status.HTTP_404_NOT_FOUND)

        # 获取文件类型
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        # 创建文件响应
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        return Response({
            'success': False,
            'message': f'文件下载失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
