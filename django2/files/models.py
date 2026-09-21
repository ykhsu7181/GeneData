from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class FileType(models.Model):
    """文件类型模型"""

    code = models.CharField(max_length=50, unique=True, db_index=True, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    format = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=100, verbose_name='类型名称')
    extension = models.CharField(max_length=20, verbose_name='文件扩展名')
    description = models.TextField(blank=True, null=True, verbose_name='描述')

    class Meta:
        verbose_name = '文件类型'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Species(models.Model):
    species_code = models.CharField(max_length=100, unique=True, db_index=True)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    chinese_name = models.CharField(max_length=255, blank=True, null=True)
    common_name = models.CharField(max_length=255, blank=True, null=True)
    taxonomy_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'species'
        ordering = ['species_code']

    def __str__(self):
        return self.scientific_name or self.common_name or self.species_code


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
    species = models.ForeignKey(
        'Species',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accessions',
    )
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


class AccessionExternalMapping(models.Model):
    """External study and sequencing identifiers associated with an accession."""

    accession = models.ForeignKey(
        'Accession',
        on_delete=models.CASCADE,
        related_name='external_mappings',
    )
    external_database = models.CharField(max_length=50)
    external_study_accession = models.CharField(max_length=100, db_index=True)
    biosample_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    experiment_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    run_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    library_strategy = models.CharField(max_length=100, blank=True, null=True)
    instrument_platform = models.CharField(max_length=100, blank=True, null=True)
    instrument_model = models.CharField(max_length=255, blank=True, null=True)
    fastq_url = models.TextField(blank=True, null=True)
    fastq_md5 = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accession_external_mapping'
        ordering = ['external_study_accession', 'run_accession', 'id']

    def __str__(self):
        return self.run_accession or self.experiment_accession or self.external_study_accession


class Sample(models.Model):
    sample_code = models.CharField(max_length=100, unique=True, db_index=True)
    sample_name = models.CharField(max_length=255, blank=True, null=True)
    biosample_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    experiment_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    species = models.ForeignKey(
        'Species',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='samples',
    )
    accession = models.ForeignKey(
        'Accession',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='samples',
    )
    tissue = models.CharField(max_length=100, blank=True, null=True)
    treatment = models.CharField(max_length=255, blank=True, null=True)
    replicate = models.CharField(max_length=100, blank=True, null=True)
    data_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sample'
        ordering = ['sample_code']

    def __str__(self):
        return self.sample_name or self.sample_code


class Project(models.Model):
    project_code = models.CharField(max_length=100, unique=True, db_index=True)
    project_name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project'
        ordering = ['project_code']

    def __str__(self):
        return self.project_name or self.project_code


class Dataset(models.Model):
    DATASET_TYPE_CHOICES = [
        ('genome', 'Genome'),
        ('annotation', 'Annotation'),
        ('transcriptome', 'Transcriptome'),
        ('hic', 'Hi-C'),
        ('population_genetics', 'Population genetics'),
        ('variant', 'Variant'),
        ('phenotype', 'Phenotype'),
        ('other', 'Other'),
    ]
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('lab_internal', 'Lab internal'),
        ('public', 'Public'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('released', 'Released'),
        ('archived', 'Archived'),
    ]

    dataset_code = models.CharField(max_length=100, unique=True, db_index=True)
    dataset_name = models.CharField(max_length=255, blank=True, null=True)
    bioproject_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    dataset_type = models.CharField(
        max_length=50,
        choices=DATASET_TYPE_CHOICES,
        default='other',
    )
    species = models.ForeignKey(
        'Species',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='datasets',
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='datasets',
    )
    version = models.CharField(max_length=100, blank=True, null=True)
    visibility = models.CharField(
        max_length=50,
        choices=VISIBILITY_CHOICES,
        default='private',
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='draft',
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dataset'
        ordering = ['dataset_code']

    def __str__(self):
        return self.dataset_name or self.dataset_code


class DatasetAccession(models.Model):
    """Explicit ownership link between a dataset and one or more accessions."""

    RELATION_ROLE_CHOICES = [
        ("primary", "Primary"),
        ("derived", "Derived"),
        ("reference", "Reference"),
    ]

    dataset = models.ForeignKey(
        "Dataset",
        on_delete=models.CASCADE,
        related_name="accession_links",
    )
    accession = models.ForeignKey(
        "Accession",
        on_delete=models.CASCADE,
        related_name="dataset_links",
    )
    relation_role = models.CharField(
        max_length=50,
        choices=RELATION_ROLE_CHOICES,
        default="primary",
    )
    source = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dataset_accession"
        ordering = ["dataset__dataset_code", "accession__accession"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "accession"],
                name="uniq_dataset_accession",
            ),
        ]

    def __str__(self):
        return f"{self.dataset.dataset_code}:{self.accession.accession}"


class Assembly(models.Model):
    accession = models.ForeignKey(
        'Accession',
        on_delete=models.CASCADE,
        related_name='assemblies',
        verbose_name='Accession',
    )
    name = models.CharField(max_length=255, default='default')
    # Manifest-facing fields. ``name`` remains the legacy display key used by
    # existing pages, while these retain the external assembly metadata.
    assembly_code = models.CharField(max_length=255, unique=True, blank=True, null=True)
    assembly_name = models.CharField(max_length=255, blank=True, null=True)
    assembly_accession = models.CharField(max_length=255, blank=True, null=True)
    species_code = models.CharField(max_length=100, blank=True, null=True)
    assembly_level = models.CharField(max_length=100, blank=True, null=True)
    biosample_accession = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    assembly_type = models.CharField(max_length=100, blank=True, null=True)
    assembly_method = models.CharField(max_length=255, blank=True, null=True)
    sequencing_technology = models.CharField(max_length=255, blank=True, null=True)
    genome_size = models.BigIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    chromosome_count = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    contig_count = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    n50 = models.BigIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    gc_content = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    at_content = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    n_count = models.BigIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    n_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    sequence_count = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    sequence_md5 = models.CharField(max_length=32, blank=True, null=True)
    gap_count = models.BigIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    source_database = models.CharField(max_length=100, blank=True, null=True)
    external_project = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    file_name = models.CharField(max_length=500, blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
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
    # Stored explicitly for manifest imports and fast Accession-level queries.
    # The importer always keeps it aligned with ``assembly.accession``.
    accession = models.ForeignKey(
        'Accession',
        on_delete=models.CASCADE,
        related_name='direct_annotations',
        blank=True,
        null=True,
        verbose_name='Accession',
    )
    name = models.CharField(max_length=255, default='default-annotation')
    annotation_code = models.CharField(max_length=255, unique=True, blank=True, null=True)
    annotation_name = models.CharField(max_length=255, blank=True, null=True)
    annotation_version = models.CharField(max_length=100, blank=True, null=True)
    species_code = models.CharField(max_length=100, blank=True, null=True)
    source_database = models.CharField(max_length=100, blank=True, null=True)
    external_project = models.CharField(max_length=100, blank=True, null=True)
    file_name = models.CharField(max_length=500, blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
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


class DataFile(models.Model):
    file_code = models.CharField(max_length=100, unique=True, db_index=True)
    dataset = models.ForeignKey(
        'Dataset',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='data_files',
    )
    file_type = models.ForeignKey(
        FileType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='data_files',
    )
    file_name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True, null=True)
    file_path = models.CharField(max_length=500, unique=True, db_index=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    md5 = models.CharField(max_length=64, blank=True, null=True)
    is_current = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'data_file'
        ordering = ['file_code']

    def __str__(self):
        return self.file_name


class FileRelation(models.Model):
    RELATED_TYPE_CHOICES = [
        ('accession', 'Accession'),
        ('assembly', 'Assembly'),
        ('annotation', 'Annotation'),
        ('dataset', 'Dataset'),
        ('sample', 'Sample'),
        ('expression_matrix', 'Expression matrix'),
        ('variant_set', 'Variant set'),
        ('population_analysis', 'Population analysis'),
        ('other', 'Other'),
    ]

    file = models.ForeignKey(
        'DataFile',
        on_delete=models.CASCADE,
        related_name='relations',
    )
    related_type = models.CharField(max_length=50, choices=RELATED_TYPE_CHOICES)
    related_id = models.CharField(max_length=100)
    related_code = models.CharField(max_length=255, blank=True, null=True)
    file_role = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'file_relation'
        ordering = ['related_type', 'related_id', 'file_role', 'id']
        indexes = [
            models.Index(fields=['related_type', 'related_id'], name='idx_fr_related'),
            models.Index(fields=['related_type', 'related_id', 'file_role'], name='idx_fr_related_role'),
            models.Index(fields=['file', 'related_type', 'related_id', 'file_role'], name='idx_fr_file_related_role'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['file', 'related_type', 'related_id', 'file_role'],
                name='uniq_file_relation_role',
            ),
        ]

    def __str__(self):
        return f"{self.file_id}:{self.related_type}:{self.related_id}:{self.file_role}"


class GenomeFile(models.Model):
    """基因组文件模型"""

    FILE_CATEGORY_CHOICES = [
        ('variableBlocks', 'Variable Blocks'),
        ('genome', 'Genome'),
        ('transcriptome.all', 'Transcriptome-All'),
        ('transcriptome.root', 'Transcriptome-Root'),
        ('transcriptome.stem', 'Transcriptome-Stem'),
        ('transcriptome.leaf', 'Transcriptome-Leaf'),
        ('transcriptome.panicles', 'Transcriptome-Panicles'),
        ('transcriptome.shoot', 'Transcriptome-Shoot'),
        ('miRNA', 'miRNA'),
        ('tRNA', 'tRNA'),
        ('rRNA', 'rRNA'),
        ('codon', 'Codon'),
        ('centromere', 'Centromere'),
        ('TEs', 'TEs'),
        ('annotation', 'Annotation'),
        ('coreBlocks', 'Core Blocks'),
        ('other', 'Other'),
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
    category = models.CharField(max_length=50, choices=FILE_CATEGORY_CHOICES, verbose_name='File Category')
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
