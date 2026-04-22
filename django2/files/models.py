from django.db import models
from django.db.models import Q


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


class Accession(models.Model):
    accession = models.CharField(max_length=50, unique=True, db_index=True)
    genetic_stock_id = models.CharField(max_length=100, blank=True, null=True)
    sub_population = models.CharField(max_length=100, blank=True, null=True)
    seq_data = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accession'
        ordering = ['accession']

    def __str__(self):
        return self.accession

    @property
    def default_assembly(self):
        return self.assemblies.filter(is_default=True).first()


class Assembly(models.Model):
    accession = models.ForeignKey(
        'Accession',
        on_delete=models.CASCADE,
        related_name='assemblies',
        verbose_name='Accession',
    )
    name = models.CharField(max_length=255, default='default')
    display_name = models.CharField(max_length=255, blank=True, null=True)
    standard_id = models.CharField(max_length=255, blank=True, null=True)
    bio_project = models.CharField(max_length=255, blank=True, null=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assembly'
        ordering = ['accession__accession', '-is_default', 'name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['accession', 'name'],
                name='uniq_assembly_name_per_accession',
            ),
            models.UniqueConstraint(
                fields=['accession'],
                condition=Q(is_default=True),
                name='uniq_default_assembly_per_accession',
            ),
        ]

    def __str__(self):
        return f"{self.accession.accession}:{self.name}"

    @property
    def default_annotation(self):
        return self.annotations.filter(is_default=True).first()


class Annotation(models.Model):
    assembly = models.ForeignKey(
        'Assembly',
        on_delete=models.CASCADE,
        related_name='annotations',
        verbose_name='Assembly',
    )
    name = models.CharField(max_length=255, default='default-annotation')
    display_name = models.CharField(max_length=255, blank=True, null=True)
    standard_id = models.CharField(max_length=255, blank=True, null=True)
    source_name = models.CharField(max_length=255, blank=True, null=True)
    release_version = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'annotation'
        ordering = ['assembly__accession__accession', 'assembly__name', '-is_default', 'name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['assembly', 'name'],
                name='uniq_annotation_name_per_assembly',
            ),
            models.UniqueConstraint(
                fields=['assembly'],
                condition=Q(is_default=True),
                name='uniq_default_annotation_per_assembly',
            ),
        ]

    def __str__(self):
        return f"{self.assembly}:{self.name}"


class GenomeFile(models.Model):
    """基因组文件模型"""

    FILE_CATEGORY_CHOICES = [
        ('variableBlocks', 'Variable Blocks'),
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
    accession = models.ForeignKey(
        'Accession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='Accession',
    )
    assembly = models.ForeignKey(
        'Assembly',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='Assembly',
    )
    annotation = models.ForeignKey(
        'Annotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='Annotation',
    )
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
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']

        try:
            organisms_from_db = list(
                GenomeFile.objects.exclude(organism__isnull=True)
                .exclude(organism='')
                .exclude(organism='unknown')
                .values_list('organism', flat=True)
                .distinct()
            )
            organisms_from_db = [org for org in organisms_from_db if org not in tissue_types]

            all_organisms = [org for org in organisms_from_db if org and org != 'unknown']
            all_organisms.sort()
            return all_organisms
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"获取生物体列表时发生错误: {str(e)}")
            return []

    @staticmethod
    def get_all_categories():
        """获取所有可用的文件类别选项"""
        categories_from_db = list(FileCategory.objects.all().values_list('code', flat=True))
        fixed_categories = [choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES]
        all_categories = list(set(categories_from_db + fixed_categories))
        all_categories.sort()
        return all_categories

    @staticmethod
    def get_transcriptome_types():
        """获取所有转录组类型"""
        return ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
