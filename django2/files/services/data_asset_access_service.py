"""Fail-closed composition of DataAsset and DataFile access policies."""

from files.models import AssetFileMembership, DataAccessToken, DataAsset, DataFile
from files.services.datafile_access_service import (
    ACTION_SCOPES,
    DataFileAccessDecision,
    LEVEL_RANK,
    resolve_datafile_access,
)


ASSET_LEVELS = {
    DataAsset.VISIBILITY_PUBLIC: DataFile.ACCESS_LEVEL_PUBLIC,
    DataAsset.VISIBILITY_INTERNAL: DataFile.ACCESS_LEVEL_INTERNAL,
    DataAsset.VISIBILITY_PRIVATE: DataFile.ACCESS_LEVEL_PRIVATE,
}


def resolve_data_asset_file_access(asset, data_file, *, principal=None, action="metadata"):
    """Authorize one member file without allowing the asset to loosen file policy."""
    if action not in ACTION_SCOPES:
        raise ValueError(f"Unsupported DataFile access action: {action}")
    if asset.project_id is None:
        return _deny("asset_project_missing")
    if asset.status != DataAsset.STATUS_RELEASED:
        return _deny("asset_not_released")
    if asset.published_at is None:
        return _deny("asset_release_incomplete")

    asset_level = ASSET_LEVELS.get(asset.visibility)
    if asset_level is None:
        return _deny("asset_visibility_unknown")
    if not AssetFileMembership.objects.filter(asset=asset, data_file=data_file).exists():
        return _deny("file_not_asset_member", effective_level=asset_level)

    file_decision = resolve_datafile_access(
        data_file,
        principal=principal,
        action=action,
    )
    effective_level = _most_restrictive(
        asset_level,
        file_decision.effective_access_level,
    )
    if not file_decision.allowed:
        return _deny(
            file_decision.reason,
            effective_level=effective_level,
            required_scope=file_decision.required_scope,
        )
    if effective_level == DataFile.ACCESS_LEVEL_PRIVATE:
        return _deny("asset_or_file_private", effective_level=effective_level)
    if effective_level == DataFile.ACCESS_LEVEL_INTERNAL:
        required_scope = ACTION_SCOPES[action]
        if not isinstance(principal, DataAccessToken) or not principal.is_active:
            return _deny(
                "authentication_required",
                effective_level=effective_level,
                required_scope=required_scope,
            )
        if not principal.has_scope(required_scope):
            return _deny(
                "insufficient_scope",
                effective_level=effective_level,
                required_scope=required_scope,
            )
        if principal.access_tier != DataAccessToken.ACCESS_TIER_INTERNAL:
            return _deny(
                "insufficient_access_tier",
                effective_level=effective_level,
                required_scope=required_scope,
            )

    return DataFileAccessDecision(
        allowed=True,
        reason="asset_and_file_authorized",
        effective_access_level=effective_level,
        required_scope=ACTION_SCOPES[action],
    )


def _most_restrictive(*levels):
    return max(
        levels,
        key=lambda level: LEVEL_RANK.get(
            level,
            LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE],
        ),
    )


def _deny(reason, *, effective_level=DataFile.ACCESS_LEVEL_PRIVATE, required_scope=""):
    return DataFileAccessDecision(
        allowed=False,
        reason=reason,
        effective_access_level=effective_level,
        required_scope=required_scope,
    )
