from django.db import models

# Create your models here.

class FileType(models.Model):
    """文件类型模型"""
    name = models.CharField(max_length=100, verbose_name='类型名称')
    extension = models.CharField(max_length=20, verbose_name='文件扩展名')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    
    class Meta:
        verbose_name = '文件类型'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name

class Organism(models.Model):
    """生物体模型"""
    code = models.CharField(max_length=20, primary_key=True, verbose_name='生物体代码')
    name = models.CharField(max_length=100, verbose_name='生物体名称')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    
    class Meta:
        verbose_name = '生物体'
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return f"{self.code} ({self.name})"

class FileCategory(models.Model):
    """文件类别模型"""
    code = models.CharField(max_length=50, primary_key=True, verbose_name='类别代码')
    name = models.CharField(max_length=100, verbose_name='类别名称')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    
    class Meta:
        verbose_name = '文件类别'
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return self.name

class GenomeFile(models.Model):
    """基因组文件模型"""

    
    FILE_CATEGORY_CHOICES = [
        ('genome', '基因组序列'),
        ('transcriptome.all', '转录组-All'),
        ('transcriptome.root', '转录组-Root'),
        ('transcriptome.stem', '转录组-Stem'),
        ('transcriptome.leaf', '转录组-Leaf'),
        ('transcriptome.panicles', '转录组-Panicles'),
        ('transcriptome.shoot', '转录组-Shoot'),
        ('miRNA', '微RNA'),
        ('tRNA', '转运RNA'),
        ('rRNA', '核糖体RNA'),
        ('codon', '密码子'),
        ('centromere', '着丝粒'),
        ('TEs', '转座子'),
        ('annotation', '基因注释'),
        ('coreBlocks', '核心区块'),
        ('other', '其他'),
    ]
    
    name = models.CharField(max_length=255, verbose_name='文件名')
    organism = models.CharField(max_length=50, verbose_name='生物体')
    category = models.CharField(max_length=50, choices=FILE_CATEGORY_CHOICES, verbose_name='文件类别')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_type = models.ForeignKey(FileType, on_delete=models.SET_NULL, null=True, verbose_name='文件类型')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '基因组文件'
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return f"{self.organism}-{self.category}-{self.name}"
        
    @staticmethod
    def get_all_organisms():
        """获取所有可用的生物体选项"""
        # 定义已知的组织类型，这些不应该被当作生物体
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
        
        try:
            # 从数据库中获取现有的生物体列表，排除无效值
            organisms_from_db = list(GenomeFile.objects.exclude(
                organism__isnull=True
            ).exclude(organism='').exclude(organism='unknown').values_list('organism', flat=True).distinct())
            # 过滤掉组织类型
            organisms_from_db = [org for org in organisms_from_db if org not in tissue_types]

            # 只使用GenomeFile表中存在的生物体，不再从Organism表中获取
            # 这确保只返回实际有文件的生物体
            all_organisms = organisms_from_db

            # 移除None和空字符串（双重保险）
            all_organisms = [org for org in all_organisms if org and org != 'unknown']
            all_organisms.sort()  # 排序

            return all_organisms
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取生物体列表时发生错误: {str(e)}")
            return []
    
    @staticmethod
    def get_all_categories():
        """获取所有可用的文件类别选项"""
        # 先从FileCategory表获取
        categories_from_db = list(FileCategory.objects.all().values_list('code', flat=True))
        # 合并固定的选项
        fixed_categories = [choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES]
        # 合并结果并去重
        all_categories = list(set(categories_from_db + fixed_categories))
        all_categories.sort()  # 排序
        return all_categories
        
    @staticmethod
    def get_transcriptome_types():
        """获取所有转录组类型"""
        return ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
