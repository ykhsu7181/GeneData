"""Controlled maintenance writes for generated DataAsset auxiliary files."""

import hashlib
from pathlib import Path

from django.db import transaction

from files.models import AssetFileMembership, DataAsset, DataFile
from files.services.core_audit_service import append_core_audit_event
from files.services.core_content_snapshot import asset_content_snapshot
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.project_service import get_project_role, lock_project_for_core_write


class DataAssetAuxiliaryError(ValueError):
    pass


class DataAssetAuxiliaryPermissionDenied(DataAssetAuxiliaryError):
    pass


MAINTENANCE_ROLES = frozenset({"owner", "manager"})
MAINTENANCE_STATUSES = frozenset({DataAsset.STATUS_DRAFT, DataAsset.STATUS_RELEASED})


def can_maintain_data_asset(*, asset, actor):
    return get_project_role(project=asset.project, user=actor) in MAINTENANCE_ROLES


def require_data_asset_maintenance_permission(*, asset, actor):
    if actor is None or actor.pk is None or not actor.is_active:
        raise DataAssetAuxiliaryPermissionDenied("An active persisted actor is required.")
    if not can_maintain_data_asset(asset=asset, actor=actor):
        raise DataAssetAuxiliaryPermissionDenied(
            "Only a Project owner or manager can maintain generated asset data."
        )
    if asset.status not in MAINTENANCE_STATUSES:
        raise DataAssetAuxiliaryError(
            "Generated asset data can only be maintained for draft or released assets."
        )


@transaction.atomic
def register_generated_auxiliary_file(
    *, asset, actor, file_role, path, registry=None
):
    """Register one generated auxiliary without weakening core asset write rules."""
    lock_project_for_core_write(asset.project_id)
    locked = DataAsset.objects.select_for_update().select_related("project").get(pk=asset.pk)
    require_data_asset_maintenance_permission(asset=locked, actor=actor)
    registry = registry or load_data_asset_registry()
    try:
        profile = registry.resolve_exact_asset_profile(
            locked.data_type_key,
            locked.profile_key,
            locked.schema_version,
            locked.schema_digest,
        )
    except DataAssetRegistryError as exc:
        raise DataAssetAuxiliaryError("The DataAsset Profile is unavailable.") from exc
    role_rule = profile.file_role_rules.get(file_role)
    if role_rule is None or role_rule.role_class != "auxiliary":
        raise DataAssetAuxiliaryError(
            "Generated files can only use an auxiliary role declared by the exact Profile."
        )
    if role_rule.maximum != 1:
        raise DataAssetAuxiliaryError(
            "Generated auxiliary registration requires a role with maximum cardinality one."
        )

    target = Path(path)
    payload = target.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    code = f"JB_{locked.pk}_{file_role}"[:100]
    code_match = DataFile.objects.select_for_update().filter(file_code=code).first()
    path_match = DataFile.objects.select_for_update().filter(file_path=str(target)).first()
    if code_match is not None and code_match.file_path != str(target):
        raise DataAssetAuxiliaryError("Derived DataFile code conflicts with another path.")
    if path_match is not None and path_match.file_code != code:
        raise DataAssetAuxiliaryError("Derived path is already owned by another DataFile.")
    if code_match is not None and path_match is not None and code_match.pk != path_match.pk:
        raise DataAssetAuxiliaryError("Derived DataFile identity is inconsistent.")

    before = asset_content_snapshot(locked)
    data_file = code_match or path_match
    if data_file is None:
        data_file = DataFile.objects.create(
            file_code=code,
            file_path=str(target),
            file_name=target.name,
            original_name=target.name,
            file_size=len(payload),
            sha256=digest,
            is_current=True,
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
            description=f"JBrowse {file_role} for DataAsset {locked.asset_code}",
        )
    else:
        data_file.file_name = target.name
        data_file.original_name = target.name
        data_file.file_size = len(payload)
        data_file.sha256 = digest
        data_file.is_current = True
        data_file.availability_status = DataFile.AVAILABILITY_AVAILABLE
        data_file.description = f"JBrowse {file_role} for DataAsset {locked.asset_code}"
        data_file.save(update_fields=[
            "file_name", "original_name", "file_size", "sha256", "is_current",
            "availability_status", "description", "updated_at",
        ])

    memberships = list(
        AssetFileMembership.objects.select_for_update()
        .filter(asset=locked, file_role=file_role)
        .order_by("position", "id")[:2]
    )
    if len(memberships) > 1:
        raise DataAssetAuxiliaryError("Generated auxiliary role is ambiguous.")
    if not memberships:
        AssetFileMembership.objects.create(
            asset=locked,
            data_file=data_file,
            file_role=file_role,
            position=0,
            created_by=actor,
        )
    elif memberships[0].data_file_id != data_file.pk:
        memberships[0].data_file = data_file
        memberships[0].created_by = actor
        memberships[0].save(update_fields=["data_file", "created_by"])

    after = asset_content_snapshot(locked)
    if before != after:
        append_core_audit_event(
            project=locked.project,
            actor=actor,
            event_type="asset_updated",
            asset=locked,
            before_content=before,
            after_content=after,
            reason=f"Registered generated auxiliary role {file_role}.",
        )
    return data_file
