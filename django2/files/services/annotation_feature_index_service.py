"""Legacy Annotation/FileRelation adapter for AnnotationFeatureIndex."""

from files.models import FileRelation
from files.services.annotation_feature_index_core import (
    AnnotationIndexUnavailable,
    annotation_cache_key,
    build_annotation_index_for_target,
    cached_value,
    feature_index_version,
    get_ready_annotation_index_for_target,
    serialize_feature,
)


def select_annotation_source_file(annotation_id):
    relations = list(
        FileRelation.objects.select_related("file")
        .filter(
            related_type="annotation",
            related_id=str(annotation_id),
            file_role="annotation",
            file__is_current=True,
        )
        .order_by("-is_primary", "id")
    )
    return relations[0].file if relations else None


def get_ready_annotation_index(annotation, service_file):
    return get_ready_annotation_index_for_target(
        target_lookup={"annotation": annotation}, service_file=service_file
    )


def build_annotation_feature_index(annotation, *, force=False, batch_size=2000):
    source_file = select_annotation_source_file(annotation.id)
    if not source_file:
        raise AnnotationIndexUnavailable(
            "No current annotation FileRelation exists", index_status="source_missing"
        )
    return build_annotation_index_for_target(
        target_lookup={"annotation": annotation},
        target_defaults={"annotation_asset": None},
        source_file=source_file,
        force=force,
        batch_size=batch_size,
    )
