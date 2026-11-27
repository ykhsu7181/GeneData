import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


CORE_AUDIT_MEMBER_EVENTS = (
    "membership_added",
    "membership_role_changed",
    "membership_removed",
)
CORE_AUDIT_CONTEXT_EVENTS = (
    "context_created",
    "context_updated",
    "context_activated",
    "context_archived",
)
CORE_AUDIT_ASSET_EVENTS = (
    "asset_created",
    "asset_updated",
    "asset_submitted",
    "asset_returned",
    "asset_approved",
    "asset_approval_withdrawn",
    "asset_released",
    "asset_archived",
)
CORE_AUDIT_EVENT_TYPES = (
    *CORE_AUDIT_MEMBER_EVENTS,
    *CORE_AUDIT_CONTEXT_EVENTS,
    *CORE_AUDIT_ASSET_EVENTS,
)
CORE_AUDIT_ROLES = ("owner", "manager", "contributor", "viewer")


class CoreAuditEventImmutableError(RuntimeError):
    pass


class CoreAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise CoreAuditEventImmutableError("Core audit events cannot be updated.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise CoreAuditEventImmutableError("Core audit events cannot be updated.")

    def delete(self):
        raise CoreAuditEventImmutableError("Core audit events cannot be deleted.")


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
    view_count = models.PositiveBigIntegerField(default=0, db_index=True)
    last_viewed_at = models.DateTimeField(blank=True, null=True)
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


class ProjectMembership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_CONTRIBUTOR = "contributor"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_CONTRIBUTOR, "Contributor"),
        (ROLE_VIEWER, "Viewer"),
    ]

    project = models.ForeignKey(
        "Project",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_project_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_membership"
        ordering = ["project_id", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                name="uniq_project_membership_user",
            ),
            models.CheckConstraint(
                check=models.Q(
                    role__in=[
                        "owner",
                        "manager",
                        "contributor",
                        "viewer",
                    ]
                ),
                name="project_membership_valid_role",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "role"], name="project_member_role_idx"),
            models.Index(fields=["user", "role"], name="user_project_role_idx"),
        ]

    def __str__(self):
        return f"{self.project.project_code}:{self.user_id}:{self.role}"


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


class DataAsset(models.Model):
    """Target identity for a versioned, publishable scientific data unit."""

    VISIBILITY_PRIVATE = "private"
    VISIBILITY_INTERNAL = "lab_internal"
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "Private"),
        (VISIBILITY_INTERNAL, "Lab internal"),
        (VISIBILITY_PUBLIC, "Public"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_RELEASED = "released"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_RELEASED, "Released"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    asset_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    project = models.ForeignKey(
        "Project",
        on_delete=models.PROTECT,
        related_name="data_assets",
    )
    data_type_key = models.CharField(max_length=100)
    profile_key = models.CharField(max_length=100)
    schema_version = models.CharField(max_length=50)
    schema_digest = models.CharField(max_length=64)
    version = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    visibility = models.CharField(
        max_length=50,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PRIVATE,
    )
    metadata = models.JSONField(default=dict)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="created_data_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "data_asset"
        ordering = ["asset_code"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_da_project_status"),
            models.Index(fields=["project", "data_type_key"], name="idx_da_project_type"),
            models.Index(fields=["visibility", "status"], name="idx_da_visibility_status"),
        ]
        constraints = [
            models.CheckConstraint(check=~Q(asset_code=""), name="chk_da_code_nonempty"),
            models.CheckConstraint(check=~Q(data_type_key=""), name="chk_da_type_nonempty"),
            models.CheckConstraint(check=~Q(profile_key=""), name="chk_da_profile_nonempty"),
            models.CheckConstraint(check=~Q(schema_version=""), name="chk_da_schema_ver_nonempty"),
            models.CheckConstraint(check=~Q(schema_digest=""), name="chk_da_schema_hash_nonempty"),
            models.CheckConstraint(
                check=Q(status__in=["draft", "submitted", "approved", "released", "archived"]),
                name="dataasset_valid_status",
            ),
            models.CheckConstraint(
                check=Q(visibility__in=["private", "lab_internal", "public"]),
                name="dataasset_valid_visibility",
            ),
        ]

    def __str__(self):
        return self.name or self.asset_code


class AssetFileMembership(models.Model):
    """Explicit membership between a DataAsset and the canonical DataFile."""

    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="file_memberships",
    )
    data_file = models.ForeignKey(
        "DataFile",
        on_delete=models.PROTECT,
        related_name="asset_memberships",
    )
    file_role = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    primary_slot = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="created_asset_file_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_file_membership"
        ordering = ["asset_id", "file_role", "position", "id"]
        indexes = [
            models.Index(
                fields=["asset", "file_role", "position"],
                name="idx_afm_asset_role_pos",
            ),
            models.Index(fields=["data_file", "asset"], name="idx_afm_file_asset"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "data_file"],
                name="uniq_asset_data_file",
            ),
            models.UniqueConstraint(
                fields=["asset", "file_role", "position"],
                name="uniq_asset_role_position",
            ),
            models.UniqueConstraint(
                fields=["asset", "file_role", "primary_slot"],
                name="uniq_asset_role_primary_file",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(is_primary=True)
                        & Q(primary_slot__isnull=False)
                        & Q(primary_slot=1)
                    )
                    | (Q(is_primary=False) & Q(primary_slot__isnull=True))
                ),
                name="chk_afm_primary_guard",
            ),
            models.CheckConstraint(check=Q(position__gte=0), name="chk_afm_position_gte_0"),
            models.CheckConstraint(check=~Q(file_role=""), name="chk_afm_role_nonempty"),
        ]

    def __str__(self):
        return f"{self.asset_id}:{self.data_file_id}:{self.file_role}"


class DataAssetAccession(models.Model):
    """Optional biological context for a DataAsset."""

    ROLE_PRIMARY = "primary"
    ROLE_DERIVED = "derived"
    ROLE_REFERENCE = "reference"
    RELATION_ROLE_CHOICES = [
        (ROLE_PRIMARY, "Primary"),
        (ROLE_DERIVED, "Derived"),
        (ROLE_REFERENCE, "Reference"),
    ]

    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="accession_links",
    )
    accession = models.ForeignKey(
        "Accession",
        on_delete=models.PROTECT,
        related_name="data_asset_links",
    )
    relation_role = models.CharField(
        max_length=50,
        choices=RELATION_ROLE_CHOICES,
        default=ROLE_PRIMARY,
    )
    source = models.CharField(max_length=100, blank=True, default="")
    primary_slot = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_asset_accession"
        ordering = ["asset_id", "accession_id"]
        indexes = [
            models.Index(fields=["accession", "asset"], name="idx_daa_accession_asset"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "accession"],
                name="uniq_data_asset_accession",
            ),
            models.UniqueConstraint(
                fields=["asset", "primary_slot"],
                name="uniq_asset_primary_accession",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(relation_role="primary")
                        & Q(primary_slot__isnull=False)
                        & Q(primary_slot=1)
                    )
                    | (
                        Q(relation_role__in=["derived", "reference"])
                        & Q(primary_slot__isnull=True)
                    )
                ),
                name="chk_daa_primary_guard",
            ),
            models.CheckConstraint(
                check=Q(relation_role__in=["primary", "derived", "reference"]),
                name="chk_daa_relation_role",
            ),
        ]

    def __str__(self):
        return f"{self.asset_id}:{self.accession_id}:{self.relation_role}"


class DataAssetSample(models.Model):
    """Explicit Sample context for a DataAsset."""

    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="sample_links",
    )
    sample = models.ForeignKey(
        "Sample",
        on_delete=models.PROTECT,
        related_name="data_asset_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_data_asset_sample_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_asset_sample"
        ordering = ["asset_id", "sample_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "sample"],
                name="uniq_data_asset_sample",
            ),
        ]

    def __str__(self):
        return f"{self.asset_id}:{self.sample_id}"


class DataAssetAssembly(models.Model):
    """Explicit Assembly context for a DataAsset."""

    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="assembly_links",
    )
    assembly = models.ForeignKey(
        "Assembly",
        on_delete=models.PROTECT,
        related_name="data_asset_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_data_asset_assembly_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_asset_assembly"
        ordering = ["asset_id", "assembly_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "assembly"],
                name="uniq_data_asset_assembly",
            ),
        ]

    def __str__(self):
        return f"{self.asset_id}:{self.assembly_id}"


class DataAssetAnnotation(models.Model):
    """Explicit Annotation context for a DataAsset."""

    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="annotation_links",
    )
    annotation = models.ForeignKey(
        "Annotation",
        on_delete=models.PROTECT,
        related_name="data_asset_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_data_asset_annotation_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_asset_annotation"
        ordering = ["asset_id", "annotation_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "annotation"],
                name="uniq_data_asset_annotation",
            ),
        ]

    def __str__(self):
        return f"{self.asset_id}:{self.annotation_id}"


class ContextEntity(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    context_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    project = models.ForeignKey(
        "Project",
        on_delete=models.PROTECT,
        related_name="context_entities",
    )
    context_type_key = models.CharField(max_length=100)
    profile_key = models.CharField(max_length=100)
    schema_version = models.CharField(max_length=50)
    schema_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    metadata = models.JSONField(default=dict)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_context_entities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "context_entity"
        ordering = ["context_code"]
        indexes = [
            models.Index(fields=["project", "status"], name="context_project_status_idx"),
            models.Index(fields=["project", "context_type_key"], name="context_project_type_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=~Q(context_code=""), name="context_code_nonempty"),
            models.CheckConstraint(check=~Q(context_type_key=""), name="context_type_nonempty"),
            models.CheckConstraint(check=~Q(profile_key=""), name="context_profile_nonempty"),
            models.CheckConstraint(check=~Q(schema_version=""), name="context_version_nonempty"),
            models.CheckConstraint(check=~Q(schema_digest=""), name="context_digest_nonempty"),
            models.CheckConstraint(
                check=Q(status__in=["draft", "active", "archived"]),
                name="context_valid_status",
            ),
        ]

    def __str__(self):
        return self.name or self.context_code


class DataAssetRelation(models.Model):
    source_asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="outgoing_asset_relations",
    )
    target_asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="incoming_asset_relations",
    )
    relation_type = models.CharField(max_length=100)
    relation_rule_version = models.CharField(max_length=50)
    relation_rule_digest = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_data_asset_relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_asset_relation"
        ordering = ["source_asset_id", "relation_type", "target_asset_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_asset", "target_asset", "relation_type"],
                name="uniq_data_asset_relation",
            ),
            models.CheckConstraint(
                check=~Q(source_asset=models.F("target_asset")),
                name="asset_relation_no_self",
            ),
            models.CheckConstraint(check=~Q(relation_type=""), name="asset_relation_type_nonempty"),
            models.CheckConstraint(
                check=~Q(relation_rule_version=""),
                name="asset_relation_ver_nonempty",
            ),
            models.CheckConstraint(
                check=~Q(relation_rule_digest=""),
                name="asset_relation_hash_nonempty",
            ),
        ]


class AssetContextLink(models.Model):
    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.CASCADE,
        related_name="context_links",
    )
    context = models.ForeignKey(
        "ContextEntity",
        on_delete=models.CASCADE,
        related_name="asset_links",
    )
    relation_type = models.CharField(max_length=100)
    relation_rule_version = models.CharField(max_length=50)
    relation_rule_digest = models.CharField(max_length=64)
    position = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_asset_context_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_context_link"
        ordering = ["asset_id", "relation_type", "position", "context_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "context", "relation_type"],
                name="uniq_asset_context_relation",
            ),
            models.UniqueConstraint(
                fields=["asset", "relation_type", "position"],
                name="uniq_asset_context_position",
            ),
            models.CheckConstraint(check=Q(position__gte=0), name="asset_context_position_gte_0"),
            models.CheckConstraint(check=~Q(relation_type=""), name="asset_context_type_nonempty"),
            models.CheckConstraint(
                check=~Q(relation_rule_version=""),
                name="asset_context_ver_nonempty",
            ),
            models.CheckConstraint(
                check=~Q(relation_rule_digest=""),
                name="asset_context_hash_nonempty",
            ),
        ]


class ContextRelation(models.Model):
    source_context = models.ForeignKey(
        "ContextEntity",
        on_delete=models.CASCADE,
        related_name="outgoing_context_relations",
    )
    target_context = models.ForeignKey(
        "ContextEntity",
        on_delete=models.CASCADE,
        related_name="incoming_context_relations",
    )
    relation_type = models.CharField(max_length=100)
    relation_rule_version = models.CharField(max_length=50)
    relation_rule_digest = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_context_relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "context_relation"
        ordering = ["source_context_id", "relation_type", "target_context_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_context", "target_context", "relation_type"],
                name="uniq_context_relation",
            ),
            models.CheckConstraint(
                check=~Q(source_context=models.F("target_context")),
                name="context_relation_no_self",
            ),
            models.CheckConstraint(check=~Q(relation_type=""), name="context_relation_type_nonempty"),
            models.CheckConstraint(
                check=~Q(relation_rule_version=""),
                name="context_relation_ver_nonempty",
            ),
            models.CheckConstraint(
                check=~Q(relation_rule_digest=""),
                name="context_relation_hash_nonempty",
            ),
        ]


class ExternalIdentifier(models.Model):
    namespace_key = models.CharField(max_length=100)
    namespace_version = models.CharField(max_length=50)
    namespace_digest = models.CharField(max_length=64)
    normalized_value = models.CharField(max_length=255)
    display_value = models.CharField(max_length=255)
    project = models.ForeignKey(
        "Project",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="external_identifiers",
    )
    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="external_identifiers",
    )
    context = models.ForeignKey(
        "ContextEntity",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="external_identifiers",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_external_identifiers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "external_identifier"
        ordering = ["namespace_key", "normalized_value"]
        constraints = [
            models.UniqueConstraint(
                fields=["namespace_key", "normalized_value"],
                name="uniq_external_identifier",
            ),
            models.CheckConstraint(
                check=(
                    (Q(project__isnull=False) & Q(asset__isnull=True) & Q(context__isnull=True))
                    | (Q(project__isnull=True) & Q(asset__isnull=False) & Q(context__isnull=True))
                    | (Q(project__isnull=True) & Q(asset__isnull=True) & Q(context__isnull=False))
                ),
                name="external_identifier_one_target",
            ),
            models.CheckConstraint(check=~Q(namespace_key=""), name="external_namespace_nonempty"),
            models.CheckConstraint(check=~Q(namespace_version=""), name="external_version_nonempty"),
            models.CheckConstraint(check=~Q(namespace_digest=""), name="external_digest_nonempty"),
            models.CheckConstraint(check=~Q(normalized_value=""), name="external_value_nonempty"),
            models.CheckConstraint(check=~Q(display_value=""), name="external_display_nonempty"),
        ]


class CoreAuditEvent(models.Model):
    EVENT_TYPE_CHOICES = [(event_type, event_type) for event_type in CORE_AUDIT_EVENT_TYPES]

    project = models.ForeignKey(
        "Project",
        on_delete=models.PROTECT,
        related_name="core_audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="performed_core_audit_events",
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    asset = models.ForeignKey(
        "DataAsset",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="core_audit_events",
    )
    context = models.ForeignKey(
        "ContextEntity",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="core_audit_events",
    )
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="subject_core_audit_events",
    )
    from_value = models.CharField(max_length=50, blank=True, default="")
    to_value = models.CharField(max_length=50, blank=True, default="")
    before_digest = models.CharField(max_length=64, blank=True, default="")
    after_digest = models.CharField(max_length=64, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CoreAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "core_audit_event"
        ordering = ["created_at", "id"]
        base_manager_name = "objects"
        default_manager_name = "objects"
        indexes = [
            models.Index(fields=["project", "event_type", "created_at"], name="core_audit_project_event_idx"),
            models.Index(fields=["asset", "created_at"], name="core_audit_asset_idx"),
            models.Index(fields=["context", "created_at"], name="core_audit_context_idx"),
            models.Index(fields=["subject_user", "created_at"], name="core_audit_subject_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(asset__isnull=False) & Q(context__isnull=True) & Q(subject_user__isnull=True))
                    | (Q(asset__isnull=True) & Q(context__isnull=False) & Q(subject_user__isnull=True))
                    | (Q(asset__isnull=True) & Q(context__isnull=True) & Q(subject_user__isnull=False))
                ),
                name="core_audit_one_target",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(event_type__in=CORE_AUDIT_ASSET_EVENTS)
                        & Q(asset__isnull=False)
                        & Q(context__isnull=True)
                        & Q(subject_user__isnull=True)
                    )
                    | (
                        Q(event_type__in=CORE_AUDIT_CONTEXT_EVENTS)
                        & Q(asset__isnull=True)
                        & Q(context__isnull=False)
                        & Q(subject_user__isnull=True)
                    )
                    | (
                        Q(event_type__in=CORE_AUDIT_MEMBER_EVENTS)
                        & Q(asset__isnull=True)
                        & Q(context__isnull=True)
                        & Q(subject_user__isnull=False)
                    )
                ),
                name="core_audit_event_target",
            ),
            models.CheckConstraint(
                check=(
                    (Q(event_type="membership_added") & Q(from_value="") & Q(to_value__in=CORE_AUDIT_ROLES))
                    | (
                        Q(event_type="membership_role_changed")
                        & Q(from_value__in=CORE_AUDIT_ROLES)
                        & Q(to_value__in=CORE_AUDIT_ROLES)
                        & ~Q(from_value=models.F("to_value"))
                    )
                    | (Q(event_type="membership_removed") & Q(from_value__in=CORE_AUDIT_ROLES) & Q(to_value=""))
                    | (Q(event_type="context_created") & Q(from_value="") & Q(to_value="draft"))
                    | (Q(event_type="context_updated") & Q(from_value="") & Q(to_value=""))
                    | (Q(event_type="context_activated") & Q(from_value="draft") & Q(to_value="active"))
                    | (Q(event_type="context_archived") & Q(from_value="active") & Q(to_value="archived"))
                    | (Q(event_type="asset_created") & Q(from_value="") & Q(to_value="draft"))
                    | (Q(event_type="asset_updated") & Q(from_value="") & Q(to_value=""))
                    | (Q(event_type="asset_submitted") & Q(from_value="draft") & Q(to_value="submitted"))
                    | (Q(event_type="asset_returned") & Q(from_value="submitted") & Q(to_value="draft"))
                    | (Q(event_type="asset_approved") & Q(from_value="submitted") & Q(to_value="approved"))
                    | (Q(event_type="asset_approval_withdrawn") & Q(from_value="approved") & Q(to_value="draft"))
                    | (Q(event_type="asset_released") & Q(from_value="approved") & Q(to_value="released"))
                    | (Q(event_type="asset_archived") & Q(from_value="released") & Q(to_value="archived"))
                ),
                name="core_audit_valid_transition",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(event_type__in=["asset_created", "context_created"])
                        & Q(before_digest="")
                        & ~Q(after_digest="")
                    )
                    | (
                        Q(event_type__in=["asset_updated", "context_updated"])
                        & ~Q(before_digest="")
                        & ~Q(after_digest="")
                        & ~Q(before_digest=models.F("after_digest"))
                    )
                    | (
                        ~Q(
                            event_type__in=[
                                "asset_created",
                                "context_created",
                                "asset_updated",
                                "context_updated",
                            ]
                        )
                        & Q(before_digest="")
                        & Q(after_digest="")
                    )
                ),
                name="core_audit_digest_shape",
            ),
            models.CheckConstraint(
                check=(
                    ~Q(
                        event_type__in=[
                            "asset_returned",
                            "asset_approval_withdrawn",
                            "asset_archived",
                            "context_archived",
                        ]
                    )
                    | ~Q(reason="")
                ),
                name="core_audit_reason_required",
            ),
            models.CheckConstraint(
                check=(
                    ~(
                        (
                            Q(event_type="membership_added")
                            & Q(to_value__in=["owner", "manager"])
                        )
                        | (
                            Q(event_type="membership_role_changed")
                            & (
                                Q(from_value__in=["owner", "manager"])
                                | Q(to_value__in=["owner", "manager"])
                            )
                        )
                        | (
                            Q(event_type="membership_removed")
                            & Q(from_value__in=["owner", "manager"])
                        )
                    )
                    | ~Q(reason="")
                ),
                name="core_audit_privileged_reason",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise CoreAuditEventImmutableError("Core audit events cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise CoreAuditEventImmutableError("Core audit events cannot be deleted.")


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
    ACCESS_LEVEL_INHERITED = 'inherited'
    ACCESS_LEVEL_PRIVATE = 'private'
    ACCESS_LEVEL_INTERNAL = 'internal'
    ACCESS_LEVEL_PUBLIC = 'public'
    ACCESS_LEVEL_CHOICES = [
        (ACCESS_LEVEL_INHERITED, 'Inherited'),
        (ACCESS_LEVEL_PRIVATE, 'Private'),
        (ACCESS_LEVEL_INTERNAL, 'Internal'),
        (ACCESS_LEVEL_PUBLIC, 'Public'),
    ]
    PUBLICATION_DRAFT = 'draft'
    PUBLICATION_APPROVED = 'approved'
    PUBLICATION_RELEASED = 'released'
    PUBLICATION_WITHDRAWN = 'withdrawn'
    PUBLICATION_STATUS_CHOICES = [
        (PUBLICATION_DRAFT, 'Draft'),
        (PUBLICATION_APPROVED, 'Approved'),
        (PUBLICATION_RELEASED, 'Released'),
        (PUBLICATION_WITHDRAWN, 'Withdrawn'),
    ]
    AVAILABILITY_AVAILABLE = 'available'
    AVAILABILITY_QUARANTINED = 'quarantined'
    AVAILABILITY_BLOCKED = 'blocked'
    AVAILABILITY_MISSING = 'missing'
    AVAILABILITY_STATUS_CHOICES = [
        (AVAILABILITY_AVAILABLE, 'Available'),
        (AVAILABILITY_QUARANTINED, 'Quarantined'),
        (AVAILABILITY_BLOCKED, 'Blocked'),
        (AVAILABILITY_MISSING, 'Missing'),
    ]

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
    sha256 = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    is_current = models.BooleanField(default=True)
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_STATUS_CHOICES,
        default=AVAILABILITY_BLOCKED,
        db_index=True,
    )
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default=ACCESS_LEVEL_INHERITED,
        db_index=True,
    )
    publication_status = models.CharField(
        max_length=20,
        choices=PUBLICATION_STATUS_CHOICES,
        default=PUBLICATION_DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='published_data_files',
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'data_file'
        ordering = ['file_code']
        constraints = [
            models.CheckConstraint(
                check=Q(
                    availability_status__in=[
                        'available',
                        'quarantined',
                        'blocked',
                        'missing',
                    ]
                ),
                name='datafile_valid_availability',
            ),
        ]

    def __str__(self):
        return self.file_name

    @property
    def content_version(self):
        digest = (self.sha256 or '').strip().lower()
        return f'sha256:{digest}' if re.fullmatch(r'[0-9a-f]{64}', digest) else None


class DataAccessToken(models.Model):
    ACCESS_TIER_PUBLIC = 'public'
    ACCESS_TIER_INTERNAL = 'internal'
    ACCESS_TIER_CHOICES = [
        (ACCESS_TIER_PUBLIC, 'Public data'),
        (ACCESS_TIER_INTERNAL, 'Public and internal data'),
    ]

    SCOPE_METADATA_READ = 'metadata:read'
    SCOPE_FILE_READ = 'file:read'
    SCOPE_SEQUENCE_READ = 'sequence:read'
    SCOPE_DATASET_MANIFEST = 'dataset:manifest'
    ALLOWED_SCOPES = frozenset({
        SCOPE_METADATA_READ,
        SCOPE_FILE_READ,
        SCOPE_SEQUENCE_READ,
        SCOPE_DATASET_MANIFEST,
    })

    name = models.CharField(max_length=255)
    token_prefix = models.CharField(max_length=16, unique=True, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    access_tier = models.CharField(
        max_length=20,
        choices=ACCESS_TIER_CHOICES,
        default=ACCESS_TIER_PUBLIC,
    )
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_data_access_tokens',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'data_access_token'
        ordering = ['name', 'id']

    def __str__(self):
        return f'{self.name} ({self.token_prefix})'

    @classmethod
    def issue(cls, *, name, scopes, access_tier=ACCESS_TIER_PUBLIC, **extra_fields):
        normalized_scopes = sorted(set(scopes))
        unknown_scopes = set(normalized_scopes) - cls.ALLOWED_SCOPES
        if unknown_scopes:
            raise ValueError(f'Unsupported data access scopes: {sorted(unknown_scopes)}')

        prefix = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        raw_token = f'gdt_{prefix}_{secret}'
        token = cls.objects.create(
            name=name,
            token_prefix=prefix,
            token_hash=cls.hash_raw_token(raw_token),
            scopes=normalized_scopes,
            access_tier=access_tier,
            **extra_fields,
        )
        return token, raw_token

    @classmethod
    def authenticate(cls, raw_token):
        try:
            marker, prefix, _secret = str(raw_token).split('_', 2)
        except ValueError:
            return None
        if marker != 'gdt':
            return None
        token = cls.objects.filter(token_prefix=prefix).first()
        if token is None or not token.is_active:
            return None
        expected = cls.hash_raw_token(raw_token)
        if not hmac.compare_digest(token.token_hash, expected):
            return None
        return token

    @staticmethod
    def hash_raw_token(raw_token):
        key = settings.SECRET_KEY.encode('utf-8')
        return hmac.new(key, str(raw_token).encode('utf-8'), hashlib.sha256).hexdigest()

    @property
    def is_active(self):
        now = timezone.now()
        return self.revoked_at is None and (self.expires_at is None or self.expires_at > now)

    def has_scope(self, scope):
        return scope in set(self.scopes or [])


class AnnotationFeatureIndex(models.Model):
    STATUS_BUILDING = 'building'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_BUILDING, 'Building'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    annotation = models.OneToOneField(
        'Annotation',
        on_delete=models.CASCADE,
        related_name='feature_index',
        blank=True,
        null=True,
    )
    annotation_asset = models.OneToOneField(
        'DataAsset',
        on_delete=models.CASCADE,
        related_name='annotation_feature_index',
        blank=True,
        null=True,
    )
    source_file = models.ForeignKey(
        'DataFile', on_delete=models.PROTECT, related_name='annotation_feature_indexes'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BUILDING)
    source_file_size = models.BigIntegerField()
    source_file_mtime_ns = models.BigIntegerField()
    source_file_md5 = models.CharField(max_length=64, blank=True, default='')
    feature_count = models.BigIntegerField(default=0)
    chromosomes = models.JSONField(default=list)
    feature_types = models.JSONField(default=list)
    error_message = models.TextField(blank=True, default='')
    indexed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'annotation_feature_index'
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(annotation__isnull=False, annotation_asset__isnull=True)
                    | Q(annotation__isnull=True, annotation_asset__isnull=False)
                ),
                name='annotation_index_single_target',
            ),
        ]


class AnnotationFeature(models.Model):
    feature_index = models.ForeignKey(
        'AnnotationFeatureIndex', on_delete=models.CASCADE, related_name='features'
    )
    source_line = models.BigIntegerField()
    seqid = models.CharField(max_length=255)
    source = models.CharField(max_length=255, blank=True, null=True)
    feature = models.CharField(max_length=100, blank=True, null=True)
    start = models.BigIntegerField()
    end = models.BigIntegerField()
    length = models.BigIntegerField()
    score = models.CharField(max_length=100, blank=True, null=True)
    strand = models.CharField(max_length=10, blank=True, null=True)
    phase = models.CharField(max_length=20, blank=True, null=True)
    attributes = models.JSONField(default=dict)
    sequence_ontology = models.CharField(max_length=100, blank=True, null=True)
    name = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'annotation_feature'
        ordering = ['source_line', 'id']
        indexes = [
            models.Index(fields=['feature_index', 'seqid', 'feature', 'start'], name='idx_af_seq_type_start'),
            models.Index(fields=['feature_index', 'feature'], name='idx_af_feature_type'),
            models.Index(fields=['feature_index', 'seqid', 'start', 'end'], name='idx_af_seq_interval'),
        ]


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
