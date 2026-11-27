from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from files.models import DataAsset
from files.services.data_asset_access_service import filter_visible_data_assets
from files.services.data_asset_auxiliary_service import can_maintain_data_asset
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)


def command_user(username):
    user = get_user_model().objects.filter(username=username, is_active=True).first()
    if user is None:
        raise CommandError("--username must identify one active Django user")
    return user


def profile_assets(*, user, family, asset_codes=None):
    registry = load_data_asset_registry()
    queryset = filter_visible_data_assets(
        DataAsset.objects.select_related("project"), user=user
    ).order_by("id")
    if asset_codes:
        queryset = queryset.filter(asset_code__in=asset_codes)
    matches = []
    for asset in queryset.iterator():
        if not can_maintain_data_asset(asset=asset, actor=user):
            continue
        try:
            profile = registry.resolve_exact_asset_profile(
                asset.data_type_key,
                asset.profile_key,
                asset.schema_version,
                asset.schema_digest,
            )
        except DataAssetRegistryError:
            continue
        if profile.profile_family == family:
            matches.append(asset)
    return matches, registry
