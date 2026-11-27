"""Fail-closed read authorization for the ADR-005 new warehouse core."""

from dataclasses import dataclass, field
from typing import Optional

from django.db.models import Q

from files.models import (
    AssetContextLink,
    AssetFileMembership,
    ContextEntity,
    DataAsset,
    DataFile,
    ProjectMembership,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)
from files.services.protected_asset_service import (
    build_protected_file_response,
    resolve_protected_datafile_path,
)


KNOWN_ASSET_STATUSES = frozenset(
    {
        DataAsset.STATUS_DRAFT,
        DataAsset.STATUS_SUBMITTED,
        DataAsset.STATUS_APPROVED,
        DataAsset.STATUS_RELEASED,
        DataAsset.STATUS_ARCHIVED,
    }
)
KNOWN_ASSET_VISIBILITIES = frozenset(
    {
        DataAsset.VISIBILITY_PRIVATE,
        DataAsset.VISIBILITY_INTERNAL,
        DataAsset.VISIBILITY_PUBLIC,
    }
)
PROJECT_ROLES = frozenset(
    {
        ProjectMembership.ROLE_OWNER,
        ProjectMembership.ROLE_MANAGER,
        ProjectMembership.ROLE_CONTRIBUTOR,
        ProjectMembership.ROLE_VIEWER,
    }
)
PRIVILEGED_READ_ROLES = frozenset(
    {ProjectMembership.ROLE_OWNER, ProjectMembership.ROLE_MANAGER}
)


@dataclass(frozen=True)
class DataAssetAccessDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ContextAccessProjection:
    allowed: bool
    reason: str
    metadata: dict = field(default_factory=dict)
    full: bool = False


@dataclass(frozen=True)
class DataAssetFileAccessDecision:
    allowed: bool
    reason: str
    membership: Optional[AssetFileMembership] = None


def resolve_data_asset_access(asset, *, user=None):
    """Authorize one DataAsset for a real Django user or anonymous caller."""
    if asset.project_id is None:
        return _deny("asset_project_missing")
    if asset.status not in KNOWN_ASSET_STATUSES:
        return _deny("asset_status_unknown")
    if asset.visibility not in KNOWN_ASSET_VISIBILITIES:
        return _deny("asset_visibility_unknown")

    if (
        asset.status == DataAsset.STATUS_RELEASED
        and asset.visibility == DataAsset.VISIBILITY_PUBLIC
    ):
        return _allow("public_released")

    user_id = _active_user_id(user)
    if user_id is None:
        return _deny("authentication_required")

    role = _project_role(asset.project_id, user_id)
    if asset.visibility == DataAsset.VISIBILITY_INTERNAL:
        if role in PROJECT_ROLES:
            return _allow("project_member")
        return _deny("project_membership_required")

    # A non-released public asset and an archived public asset use the private
    # read rule. Archiving must never expand anonymous visibility.
    if asset.visibility in {
        DataAsset.VISIBILITY_PRIVATE,
        DataAsset.VISIBILITY_PUBLIC,
    }:
        if asset.created_by_id == user_id:
            return _allow("asset_creator")
        if role in PRIVILEGED_READ_ROLES:
            return _allow("project_privileged")
        return _deny("asset_private")

    return _deny("asset_visibility_unknown")


def filter_visible_data_assets(queryset, *, user=None):
    """Filter a DataAsset queryset with the same rules as single-object access."""
    known = Q(status__in=KNOWN_ASSET_STATUSES)
    public_released = Q(
        status=DataAsset.STATUS_RELEASED,
        visibility=DataAsset.VISIBILITY_PUBLIC,
    )
    user_id = _active_user_id(user)
    if user_id is None:
        return queryset.filter(known & public_released)

    member_projects = ProjectMembership.objects.filter(
        user_id=user_id,
        role__in=PROJECT_ROLES,
    ).values_list("project_id", flat=True)
    privileged_projects = ProjectMembership.objects.filter(
        user_id=user_id,
        role__in=PRIVILEGED_READ_ROLES,
    ).values_list("project_id", flat=True)
    private_rule = Q(visibility=DataAsset.VISIBILITY_PRIVATE) | (
        Q(visibility=DataAsset.VISIBILITY_PUBLIC)
        & ~Q(status=DataAsset.STATUS_RELEASED)
    )
    visible = (
        public_released
        | Q(
            visibility=DataAsset.VISIBILITY_INTERNAL,
            project_id__in=member_projects,
        )
        | (Q(created_by_id=user_id) & private_rule)
        | (Q(project_id__in=privileged_projects) & private_rule)
    )
    return queryset.filter(known & visible).distinct()


def resolve_context_access(context, *, user=None):
    """Authorize the complete ContextEntity; public projection is separate."""
    if context.project_id is None:
        return _deny("context_project_missing")
    user_id = _active_user_id(user)
    if user_id is None:
        return _deny("authentication_required")
    if _project_role(context.project_id, user_id) in PROJECT_ROLES:
        return _allow("project_member")
    return _deny("project_membership_required")


def filter_visible_contexts(queryset, *, user=None):
    """Filter ContextEntity rows for complete project-member access."""
    user_id = _active_user_id(user)
    if user_id is None:
        return queryset.none()
    member_projects = ProjectMembership.objects.filter(
        user_id=user_id,
        role__in=PROJECT_ROLES,
    ).values_list("project_id", flat=True)
    return queryset.filter(project_id__in=member_projects).distinct()


def project_context_for_asset(asset, context, *, user=None, registry=None):
    """Return full Context metadata or its Profile-approved public projection."""
    asset_decision = resolve_data_asset_access(asset, user=user)
    if not asset_decision.allowed:
        return _deny_context("asset_not_visible")
    if asset.project_id != context.project_id:
        return _deny_context("context_project_mismatch")
    if not AssetContextLink.objects.filter(asset=asset, context=context).exists():
        return _deny_context("context_not_asset_member")

    context_decision = resolve_context_access(context, user=user)
    if context_decision.allowed:
        return ContextAccessProjection(
            allowed=True,
            reason="context_full",
            metadata=dict(context.metadata),
            full=True,
        )

    if (
        asset.status != DataAsset.STATUS_RELEASED
        or asset.visibility != DataAsset.VISIBILITY_PUBLIC
        or context.status != ContextEntity.STATUS_ACTIVE
    ):
        return _deny_context("context_not_public")

    registry = registry or load_data_asset_registry()
    try:
        profile = registry.resolve_exact_context_profile(
            context.context_type_key,
            context.profile_key,
            context.schema_version,
            context.schema_digest,
        )
    except DataAssetRegistryError:
        return _deny_context("context_profile_unknown")
    metadata = {
        key: context.metadata[key]
        for key in profile.public_metadata_fields
        if key in context.metadata
    }
    return ContextAccessProjection(
        allowed=True,
        reason="context_public_projection",
        metadata=metadata,
        full=False,
    )


def resolve_data_asset_relation_access(relation, *, user=None):
    """Re-authorize both endpoints whenever an asset relation is used."""
    source = relation.source_asset
    target = relation.target_asset
    if not resolve_data_asset_access(source, user=user).allowed:
        return _deny("relation_source_not_visible")

    if source.project_id != target.project_id:
        if relation.relation_type != "uses_reference":
            return _deny("cross_project_relation_forbidden")
        if not (
            target.status == DataAsset.STATUS_RELEASED
            and target.visibility == DataAsset.VISIBILITY_PUBLIC
        ):
            return _deny("cross_project_target_not_public_released")

    if not resolve_data_asset_access(target, user=user).allowed:
        return _deny("relation_target_not_visible")
    return _allow("relation_endpoints_authorized")


def filter_visible_asset_file_memberships(queryset, *, user=None):
    """Filter memberships at the database boundary using DataAsset visibility."""
    visible_assets = filter_visible_data_assets(DataAsset.objects.all(), user=user)
    return queryset.filter(asset__in=visible_assets).distinct()


def resolve_data_asset_file_access(asset, data_file, *, user=None, registry=None):
    """Authorize one explicit membership and its versioned Profile file role."""
    asset_decision = resolve_data_asset_access(asset, user=user)
    if not asset_decision.allowed:
        return _deny_file("asset_not_visible")
    membership = AssetFileMembership.objects.filter(
        asset=asset,
        data_file=data_file,
    ).first()
    if membership is None:
        return _deny_file("file_not_asset_member")

    try:
        registry = registry or load_data_asset_registry()
        profile = registry.resolve_exact_asset_profile(
            asset.data_type_key,
            asset.profile_key,
            asset.schema_version,
            asset.schema_digest,
        )
    except DataAssetRegistryError:
        return _deny_file("asset_profile_unknown")
    if membership.file_role not in profile.file_role_rules:
        return _deny_file("file_role_not_allowed")
    return DataAssetFileAccessDecision(
        allowed=True,
        reason="asset_file_membership_authorized",
        membership=membership,
    )


def resolve_data_asset_file_content_access(
    asset,
    data_file,
    *,
    user=None,
    registry=None,
    roots=None,
):
    """Apply the single new-warehouse content gate after membership access."""
    decision = resolve_data_asset_file_access(
        asset,
        data_file,
        user=user,
        registry=registry,
    )
    if not decision.allowed:
        return decision
    if not data_file.is_current:
        return _deny_file("file_not_current")
    if data_file.availability_status != DataFile.AVAILABILITY_AVAILABLE:
        return _deny_file("file_not_available")
    if data_file.content_version is None:
        return _deny_file("file_checksum_unverified")

    location = resolve_protected_datafile_path(data_file, roots=roots)
    if not location.allowed:
        return _deny_file(location.reason)
    return DataAssetFileAccessDecision(
        allowed=True,
        reason="asset_file_content_authorized",
        membership=decision.membership,
    )


def resolve_file_code_content_access(
    file_code,
    *,
    user=None,
    asset_code=None,
    registry=None,
    roots=None,
):
    """Resolve a file code only through one visible, explicit membership."""
    data_file = DataFile.objects.filter(file_code=file_code).first()
    if data_file is None:
        return _deny_file("file_not_available"), None

    memberships = filter_visible_asset_file_memberships(
        AssetFileMembership.objects.filter(data_file=data_file).select_related("asset"),
        user=user,
    )
    if asset_code is not None:
        memberships = memberships.filter(asset__asset_code=asset_code)
    candidates = list(memberships[:2])
    if not candidates:
        return _deny_file("file_not_available"), None
    if asset_code is None and len(candidates) > 1:
        return _deny_file("asset_selection_required"), None

    asset = candidates[0].asset
    decision = resolve_data_asset_file_content_access(
        asset,
        data_file,
        user=user,
        registry=registry,
        roots=roots,
    )
    if not decision.allowed:
        return decision, None
    return decision, data_file


def build_data_asset_file_response(
    asset,
    data_file,
    *,
    user=None,
    registry=None,
    roots=None,
    disposition="attachment",
):
    """Authorize and build a checksum-free protected response for a new asset."""
    decision = resolve_data_asset_file_content_access(
        asset,
        data_file,
        user=user,
        registry=registry,
        roots=roots,
    )
    if not decision.allowed:
        return decision, None
    response = build_protected_file_response(
        data_file,
        roots=roots,
        disposition=disposition,
        include_etag=False,
    )
    if response is None:
        return _deny_file("file_missing"), None
    return decision, response


def _project_role(project_id, user_id):
    return (
        ProjectMembership.objects.filter(project_id=project_id, user_id=user_id)
        .values_list("role", flat=True)
        .first()
    )


def _active_user_id(user):
    if user is None:
        return None
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "pk", None) is None or not getattr(user, "is_active", False):
        return None
    return user.pk


def _allow(reason):
    return DataAssetAccessDecision(allowed=True, reason=reason)


def _deny(reason):
    return DataAssetAccessDecision(allowed=False, reason=reason)


def _deny_context(reason):
    return ContextAccessProjection(allowed=False, reason=reason)


def _deny_file(reason):
    return DataAssetFileAccessDecision(
        allowed=False,
        reason=reason,
    )
