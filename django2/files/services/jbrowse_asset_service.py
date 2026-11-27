"""Resolve the DataAsset-only capability contract used by JBrowse."""

from dataclasses import dataclass

from files.models import AssetFileMembership, DataAsset, DataAssetRelation
from files.services.data_asset_access_service import (
    resolve_data_asset_access,
    resolve_data_asset_file_content_access,
    resolve_data_asset_relation_access,
)
from files.services.data_asset_registry_service import (
    DataAssetRegistryError,
    load_data_asset_registry,
)


JBROWSE_BROWSER_ROLES = {
    "reference_genome": frozenset({"genome_fasta", "fasta_index"}),
    "genome_annotation": frozenset({"annotation_gff", "tabix_index"}),
}


class JBrowseAssetError(RuntimeError):
    def __init__(self, message, *, code="asset_unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class JBrowseAssetContext:
    annotation_asset: DataAsset
    reference_asset: DataAsset
    annotation_gff: object
    genome_fasta: object
    fasta_index: object = None
    tabix_index: object = None


def resolve_jbrowse_asset_context(
    annotation_asset_or_code,
    *,
    user=None,
    registry=None,
    roots=None,
    require_indexes=False,
):
    """Resolve and authorize an Annotation -> Reference Genome capability graph."""
    registry = registry or load_data_asset_registry()
    annotation_asset = _resolve_asset(annotation_asset_or_code)
    _require_visible(annotation_asset, user=user, code="annotation_unavailable")
    _require_profile_family(
        annotation_asset, "genome_annotation", registry, code="annotation_profile_invalid"
    )

    relations = list(
        DataAssetRelation.objects.select_related("source_asset", "target_asset")
        .filter(source_asset=annotation_asset, relation_type="uses_reference")
        .order_by("id")[:2]
    )
    if not relations:
        raise JBrowseAssetError(
            "Annotation asset has no uses_reference relation",
            code="reference_missing",
        )
    if len(relations) > 1:
        raise JBrowseAssetError(
            "Annotation asset has multiple uses_reference relations",
            code="reference_ambiguous",
        )
    relation = relations[0]
    relation_decision = resolve_data_asset_relation_access(relation, user=user)
    if not relation_decision.allowed:
        raise JBrowseAssetError(
            "Reference asset is not authorized", code=relation_decision.reason
        )
    reference_asset = relation.target_asset
    if reference_asset.status != DataAsset.STATUS_RELEASED:
        raise JBrowseAssetError(
            "Reference asset is not released", code="reference_not_released"
        )
    _require_profile_family(
        reference_asset, "reference_genome", registry, code="reference_profile_invalid"
    )

    annotation_gff = _single_authorized_file(
        annotation_asset,
        "annotation_gff",
        user=user,
        registry=registry,
        roots=roots,
        required=True,
    )
    genome_fasta = _single_authorized_file(
        reference_asset,
        "genome_fasta",
        user=user,
        registry=registry,
        roots=roots,
        required=True,
    )
    fasta_index = _single_authorized_file(
        reference_asset,
        "fasta_index",
        user=user,
        registry=registry,
        roots=roots,
        required=require_indexes,
    )
    tabix_index = _single_authorized_file(
        annotation_asset,
        "tabix_index",
        user=user,
        registry=registry,
        roots=roots,
        required=require_indexes,
    )
    return JBrowseAssetContext(
        annotation_asset=annotation_asset,
        reference_asset=reference_asset,
        annotation_gff=annotation_gff,
        genome_fasta=genome_fasta,
        fasta_index=fasta_index,
        tabix_index=tabix_index,
    )


def resolve_jbrowse_reference_asset(
    reference_asset_or_code, *, user=None, registry=None, roots=None, require_index=False
):
    registry = registry or load_data_asset_registry()
    reference_asset = _resolve_asset(reference_asset_or_code)
    _require_visible(reference_asset, user=user, code="reference_unavailable")
    if reference_asset.status != DataAsset.STATUS_RELEASED:
        raise JBrowseAssetError("Reference asset is not released", code="reference_not_released")
    _require_profile_family(
        reference_asset, "reference_genome", registry, code="reference_profile_invalid"
    )
    genome_fasta = _single_authorized_file(
        reference_asset, "genome_fasta", user=user, registry=registry, roots=roots, required=True
    )
    fasta_index = _single_authorized_file(
        reference_asset, "fasta_index", user=user, registry=registry, roots=roots,
        required=require_index,
    )
    return reference_asset, genome_fasta, fasta_index


def resolve_jbrowse_browser_file(
    asset_code, file_id, *, user=None, registry=None, roots=None
):
    """Authorize one browser file through an explicit DataAsset membership."""
    asset = DataAsset.objects.filter(asset_code=asset_code).first()
    if asset is None:
        raise JBrowseAssetError("Browser asset is unavailable")
    membership = (
        AssetFileMembership.objects.select_related("data_file")
        .filter(asset=asset, data_file_id=file_id)
        .first()
    )
    if membership is None:
        raise JBrowseAssetError("Browser asset is unavailable")
    registry = registry or load_data_asset_registry()
    try:
        profile = registry.resolve_exact_asset_profile(
            asset.data_type_key,
            asset.profile_key,
            asset.schema_version,
            asset.schema_digest,
        )
    except DataAssetRegistryError as exc:
        raise JBrowseAssetError("Browser asset is unavailable") from exc
    if membership.file_role not in JBROWSE_BROWSER_ROLES.get(
        profile.profile_family, frozenset()
    ):
        raise JBrowseAssetError("Browser asset is unavailable", code="role_not_browser_safe")
    decision = resolve_data_asset_file_content_access(
        asset,
        membership.data_file,
        user=user,
        registry=registry,
        roots=roots,
    )
    if not decision.allowed:
        raise JBrowseAssetError("Browser asset is unavailable", code=decision.reason)
    return asset, membership.data_file


def _resolve_asset(asset_or_code):
    if isinstance(asset_or_code, DataAsset):
        return asset_or_code
    if not isinstance(asset_or_code, str) or not asset_or_code:
        raise JBrowseAssetError("Annotation asset is unavailable", code="invalid_asset")
    asset = DataAsset.objects.filter(asset_code=asset_or_code).first()
    if asset is None:
        raise JBrowseAssetError("Annotation asset is unavailable")
    return asset


def _require_visible(asset, *, user, code):
    decision = resolve_data_asset_access(asset, user=user)
    if not decision.allowed:
        raise JBrowseAssetError("DataAsset is not authorized", code=code)


def _require_profile_family(asset, family, registry, *, code):
    try:
        profile = registry.resolve_exact_asset_profile(
            asset.data_type_key,
            asset.profile_key,
            asset.schema_version,
            asset.schema_digest,
        )
    except DataAssetRegistryError as exc:
        raise JBrowseAssetError("DataAsset Profile is unknown", code=code) from exc
    if profile.profile_family != family:
        raise JBrowseAssetError("DataAsset Profile family is invalid", code=code)
    return profile


def _single_authorized_file(
    asset, role, *, user, registry, roots, required
):
    memberships = list(
        AssetFileMembership.objects.select_related("data_file")
        .filter(asset=asset, file_role=role)
        .order_by("position", "id")[:2]
    )
    if not memberships:
        if required:
            raise JBrowseAssetError(
                f"DataAsset has no {role} member", code=f"{role}_missing"
            )
        return None
    if len(memberships) > 1:
        raise JBrowseAssetError(
            f"DataAsset has multiple {role} members", code=f"{role}_ambiguous"
        )
    data_file = memberships[0].data_file
    decision = resolve_data_asset_file_content_access(
        asset,
        data_file,
        user=user,
        registry=registry,
        roots=roots,
    )
    if not decision.allowed:
        raise JBrowseAssetError(
            f"DataAsset {role} member is unavailable", code=decision.reason
        )
    return data_file
