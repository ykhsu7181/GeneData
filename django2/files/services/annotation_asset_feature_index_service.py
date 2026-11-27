"""AnnotationFeatureIndex adapter for the ADR-005 DataAsset path."""

from files.models import AssetFileMembership
from files.services.annotation_feature_index_core import (
    AnnotationIndexUnavailable,
    build_annotation_index_for_target,
    get_ready_annotation_index_for_target,
)
from files.services.data_asset_access_service import resolve_data_asset_file_content_access
from files.services.data_asset_auxiliary_service import (
    require_data_asset_maintenance_permission,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)


def select_annotation_asset_source_file(
    annotation_asset, *, user=None, registry=None, roots=None
):
    """Select the single authorized annotation_gff member for an asset."""
    try:
        registry = registry or load_data_asset_registry()
        profile = registry.resolve_exact_asset_profile(
            annotation_asset.data_type_key,
            annotation_asset.profile_key,
            annotation_asset.schema_version,
            annotation_asset.schema_digest,
        )
    except DataAssetRegistryError as exc:
        raise AnnotationIndexUnavailable(
            "Annotation asset Profile is unknown", index_status="profile_invalid"
        ) from exc
    if profile.profile_family != "genome_annotation":
        raise AnnotationIndexUnavailable(
            "DataAsset is not an Annotation asset", index_status="profile_invalid"
        )

    memberships = list(
        AssetFileMembership.objects.select_related("data_file")
        .filter(asset=annotation_asset, file_role="annotation_gff")
        .order_by("position", "id")[:2]
    )
    if not memberships:
        raise AnnotationIndexUnavailable(
            "Annotation asset has no annotation_gff member", index_status="source_missing"
        )
    if len(memberships) > 1:
        raise AnnotationIndexUnavailable(
            "Annotation asset has multiple annotation_gff members",
            index_status="source_ambiguous",
        )
    source_file = memberships[0].data_file
    decision = resolve_data_asset_file_content_access(
        annotation_asset,
        source_file,
        user=user,
        registry=registry,
        roots=roots,
    )
    if not decision.allowed:
        raise AnnotationIndexUnavailable(
            "Annotation source file is not available", index_status=decision.reason
        )
    return source_file


def get_ready_annotation_asset_index(annotation_asset, service_file):
    return get_ready_annotation_index_for_target(
        target_lookup={"annotation_asset": annotation_asset}, service_file=service_file
    )


def build_annotation_asset_feature_index(
    annotation_asset,
    *,
    user=None,
    registry=None,
    roots=None,
    force=False,
    batch_size=2000,
):
    require_data_asset_maintenance_permission(asset=annotation_asset, actor=user)
    source_file = select_annotation_asset_source_file(
        annotation_asset, user=user, registry=registry, roots=roots
    )
    return build_annotation_index_for_target(
        target_lookup={"annotation_asset": annotation_asset},
        target_defaults={"annotation": None},
        source_file=source_file,
        force=force,
        batch_size=batch_size,
    )
