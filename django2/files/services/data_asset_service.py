"""Validated creation boundary for DataAsset and its explicit relations."""

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from files.models import (
    Annotation,
    Assembly,
    AssetFileMembership,
    DataAsset,
    DataAssetAccession,
    DataAssetAnnotation,
    DataAssetAssembly,
    DataAssetSample,
    Sample,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)


class DataAssetServiceError(ValueError):
    """Raised when a requested DataAsset write violates domain rules."""


class DataAssetConflictError(DataAssetServiceError):
    """Raised when a concurrent or duplicate write violates an invariant."""


@dataclass(frozen=True)
class AssetFileInput:
    data_file: object
    file_role: str
    position: int = 0
    is_primary: bool = False


@dataclass(frozen=True)
class AssetAccessionInput:
    accession: object
    relation_role: str = DataAssetAccession.ROLE_PRIMARY
    source: str = ""


def create_data_asset(
    *,
    asset_code,
    project,
    data_type_key,
    profile_key,
    created_by,
    metadata=None,
    file_memberships=(),
    accession_links=(),
    sample_links=(),
    assembly_links=(),
    annotation_links=(),
    name="",
    version=None,
    description="",
    visibility=DataAsset.VISIBILITY_PRIVATE,
    registry=None,
):
    """Create one draft asset atomically without writing legacy Dataset paths."""
    asset_code = _required_text(asset_code, "asset_code")
    if project is None or project.pk is None:
        raise DataAssetServiceError("project must be a saved Project")
    if created_by is None or created_by.pk is None:
        raise DataAssetServiceError("created_by must be a saved user")
    if visibility not in dict(DataAsset.VISIBILITY_CHOICES):
        raise DataAssetServiceError(f"Unsupported DataAsset visibility: {visibility}")

    file_memberships = tuple(file_memberships)
    accession_links = tuple(accession_links)
    sample_links = tuple(sample_links)
    assembly_links = tuple(assembly_links)
    annotation_links = tuple(annotation_links)
    _validate_file_inputs(file_memberships)
    _validate_accession_inputs(accession_links)
    _validate_context_objects(sample_links, Sample, "sample_links")
    _validate_context_objects(assembly_links, Assembly, "assembly_links")
    _validate_context_objects(annotation_links, Annotation, "annotation_links")

    registry = registry or load_data_asset_registry()
    metadata = {} if metadata is None else metadata
    context_counts = {
        name: count
        for name, count in (
            ("accession", len(accession_links)),
            ("sample", len(sample_links)),
            ("assembly", len(assembly_links)),
            ("annotation", len(annotation_links)),
        )
        if count
    }
    try:
        profile = registry.validate_asset_contract(
            data_type_key,
            profile_key,
            metadata=metadata,
            file_roles=[item.file_role for item in file_memberships],
            context_counts=context_counts,
        )
    except DataAssetRegistryError as exc:
        raise DataAssetServiceError(str(exc)) from exc
    if profile.deprecated:
        raise DataAssetServiceError(
            f"Deprecated DataAsset profile: {data_type_key}/{profile_key}"
        )

    try:
        with transaction.atomic():
            _reject_reused_profile_version(profile)
            asset = DataAsset.objects.create(
                asset_code=asset_code,
                name=name or "",
                project=project,
                data_type_key=profile.data_type_key,
                profile_key=profile.profile_key,
                schema_version=profile.schema_version,
                schema_digest=profile.schema_digest,
                version=version,
                visibility=visibility,
                metadata=metadata,
                description=description or "",
                created_by=created_by,
            )
            for item in file_memberships:
                AssetFileMembership.objects.create(
                    asset=asset,
                    data_file=item.data_file,
                    file_role=item.file_role,
                    position=item.position,
                    is_primary=item.is_primary,
                    primary_slot=1 if item.is_primary else None,
                    created_by=created_by,
                )
            for item in accession_links:
                DataAssetAccession.objects.create(
                    asset=asset,
                    accession=item.accession,
                    relation_role=item.relation_role,
                    source=item.source or "",
                    primary_slot=(
                        1
                        if item.relation_role == DataAssetAccession.ROLE_PRIMARY
                        else None
                    ),
                )
            for sample in sample_links:
                DataAssetSample.objects.create(
                    asset=asset,
                    sample=sample,
                    created_by=created_by,
                )
            for assembly in assembly_links:
                DataAssetAssembly.objects.create(
                    asset=asset,
                    assembly=assembly,
                    created_by=created_by,
                )
            for annotation in annotation_links:
                DataAssetAnnotation.objects.create(
                    asset=asset,
                    annotation=annotation,
                    created_by=created_by,
                )
    except DataAssetConflictError:
        raise
    except (IntegrityError, ValueError) as exc:
        raise DataAssetConflictError("DataAsset creation violated a database invariant") from exc
    return asset


def _reject_reused_profile_version(profile):
    conflicting_digest = (
        DataAsset.objects.select_for_update()
        .filter(
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
        )
        .exclude(schema_digest=profile.schema_digest)
        .values_list("schema_digest", flat=True)
        .first()
    )
    if conflicting_digest is not None:
        profile_name = f"{profile.data_type_key}/{profile.profile_key}"
        raise DataAssetConflictError(
            f"Profile {profile_name} version {profile.schema_version} "
            "is already used with a different schema digest"
        )


def _validate_file_inputs(items):
    seen_files = set()
    seen_positions = set()
    primary_roles = set()
    for item in items:
        if not isinstance(item, AssetFileInput):
            raise DataAssetServiceError("file_memberships must contain AssetFileInput")
        if item.data_file is None or item.data_file.pk is None:
            raise DataAssetServiceError("DataAsset members must be saved DataFile objects")
        if isinstance(item.position, bool) or not isinstance(item.position, int) or item.position < 0:
            raise DataAssetServiceError("DataAsset member position must be a non-negative integer")
        if item.data_file.pk in seen_files:
            raise DataAssetServiceError("A DataFile may appear only once in one DataAsset")
        role_position = (item.file_role, item.position)
        if role_position in seen_positions:
            raise DataAssetServiceError("Duplicate file role and position in DataAsset")
        if item.is_primary and item.file_role in primary_roles:
            raise DataAssetServiceError("Only one primary file is allowed per file role")
        seen_files.add(item.data_file.pk)
        seen_positions.add(role_position)
        if item.is_primary:
            primary_roles.add(item.file_role)


def _validate_accession_inputs(items):
    allowed_roles = dict(DataAssetAccession.RELATION_ROLE_CHOICES)
    seen_accessions = set()
    primary_count = 0
    for item in items:
        if not isinstance(item, AssetAccessionInput):
            raise DataAssetServiceError("accession_links must contain AssetAccessionInput")
        if item.accession is None or item.accession.pk is None:
            raise DataAssetServiceError("DataAsset contexts must be saved Accession objects")
        if item.relation_role not in allowed_roles:
            raise DataAssetServiceError(
                f"Unsupported DataAsset Accession role: {item.relation_role}"
            )
        if item.accession.pk in seen_accessions:
            raise DataAssetServiceError("An Accession may appear only once in one DataAsset")
        seen_accessions.add(item.accession.pk)
        if item.relation_role == DataAssetAccession.ROLE_PRIMARY:
            primary_count += 1
    if primary_count > 1:
        raise DataAssetServiceError("Only one primary Accession is allowed per DataAsset")


def _validate_context_objects(items, expected_model, field_name):
    seen = set()
    for item in items:
        if not isinstance(item, expected_model) or item.pk is None:
            raise DataAssetServiceError(
                f"{field_name} must contain saved {expected_model.__name__} objects"
            )
        if item.pk in seen:
            raise DataAssetServiceError(
                f"A {expected_model.__name__} may appear only once in one DataAsset"
            )
        seen.add(item.pk)


def _required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DataAssetServiceError(f"{field} must be a non-empty string")
    return value.strip()
