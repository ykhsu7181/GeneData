"""Resolve AnnotationFeature coordinates for the DataAsset JBrowse path."""

import math

from files.models import AnnotationFeature
from files.services.annotation_asset_feature_index_service import (
    get_ready_annotation_asset_index,
)
from files.services.annotation_feature_index_core import (
    AnnotationIndexUnavailable,
    feature_index_version,
)
from files.services.jbrowse_asset_config_service import get_jbrowse_asset_status
from files.services.jbrowse_asset_service import (
    JBrowseAssetError,
    resolve_jbrowse_asset_context,
)
from files.services.reference_name_core import (
    ReferenceNameError,
    build_reference_name_payload,
    resolve_refname,
)


class JBrowseAssetLocationError(RuntimeError):
    def __init__(self, message, *, code, http_status):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def resolve_jbrowse_asset_location(
    annotation_asset_or_code,
    feature_id,
    *,
    user=None,
    registry=None,
    roots=None,
    expected_index_version=None,
):
    if not isinstance(feature_id, int) or feature_id < 1:
        raise JBrowseAssetLocationError(
            "Feature identifier must be positive.", code="invalid_id", http_status=400
        )
    status = get_jbrowse_asset_status(
        annotation_asset_or_code, user=user, registry=registry, roots=roots
    )
    if status.get("status") != "ready":
        raise JBrowseAssetLocationError(
            "The requested assets are not ready for JBrowse.",
            code="jbrowse_not_ready",
            http_status=503,
        )
    try:
        context = resolve_jbrowse_asset_context(
            annotation_asset_or_code,
            user=user,
            registry=registry,
            roots=roots,
            require_indexes=True,
        )
        feature_index = get_ready_annotation_asset_index(
            context.annotation_asset,
            {"file_id": context.annotation_gff.id, "file_path": context.annotation_gff.file_path},
        )
    except (JBrowseAssetError, AnnotationIndexUnavailable) as exc:
        raise JBrowseAssetLocationError(
            "The annotation feature index is unavailable or stale.",
            code="annotation_index_unavailable",
            http_status=503,
        ) from exc
    current_version = feature_index_version(feature_index)
    if expected_index_version and expected_index_version != current_version:
        raise JBrowseAssetLocationError(
            "The annotation feature index version changed.",
            code="feature_index_version_conflict",
            http_status=409,
        )
    feature = AnnotationFeature.objects.filter(
        id=feature_id, feature_index=feature_index
    ).first()
    if feature is None:
        raise JBrowseAssetLocationError("Not found.", code="not_found", http_status=404)
    try:
        mapping = build_reference_name_payload(context.genome_fasta, context.fasta_index)
        ref_name, sequence_length = resolve_refname(mapping, feature.seqid)
    except ReferenceNameError as exc:
        http_status = 409 if exc.code == "alias_ambiguous" else 422
        raise JBrowseAssetLocationError(
            str(exc), code=exc.code, http_status=http_status
        ) from exc
    if feature.start < 1 or feature.end < feature.start or feature.end > sequence_length:
        raise JBrowseAssetLocationError(
            "The feature coordinates are invalid for the mapped reference.",
            code="coordinate_out_of_bounds",
            http_status=422,
        )
    padding = max(math.ceil(feature.length * 0.2), 500)
    view_start = max(1, feature.start - padding)
    view_end = min(sequence_length, feature.end + padding)
    return {
        "annotation_asset_code": context.annotation_asset.asset_code,
        "reference_asset_code": context.reference_asset.asset_code,
        "feature_id": feature.id,
        "feature_index_version": current_version,
        "ref_name": ref_name,
        "feature_start": feature.start,
        "feature_end": feature.end,
        "view_start": view_start,
        "view_end": view_end,
        "loc": f"{ref_name}:{view_start}-{view_end}",
        "assembly_name": f"asset-{context.reference_asset.asset_code}",
        "track_id": f"annotation-{context.annotation_asset.asset_code}-features",
    }
