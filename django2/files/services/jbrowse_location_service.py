"""Resolve an indexed AnnotationFeature to a trusted JBrowse location."""

import math

from files.models import Annotation, AnnotationFeature
from files.services.annotation_feature_index_service import (
    AnnotationIndexUnavailable,
    feature_index_version,
    get_ready_annotation_index,
    select_annotation_source_file,
)
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.jbrowse_config_service import get_jbrowse_status
from files.services.reference_name_service import (
    ReferenceNameError,
    load_current_refname_mapping,
    resolve_refname,
    select_mapping_inputs,
)


class JBrowseLocationError(RuntimeError):
    def __init__(self, message, *, code, http_status):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def resolve_jbrowse_location(
    assembly_id,
    annotation_id,
    feature_id,
    *,
    expected_index_version=None,
):
    if min(assembly_id, annotation_id, feature_id) < 1:
        raise JBrowseLocationError(
            "Identifiers must be positive integers.", code="invalid_id", http_status=400
        )

    assembly = visible_assembly_queryset().filter(id=assembly_id).first()
    annotation = Annotation.objects.filter(
        id=annotation_id, assembly_id=assembly_id
    ).first()
    if assembly is None or annotation is None:
        raise _not_found()

    status_payload = get_jbrowse_status(assembly.id, annotation_id=annotation.id)
    if status_payload.get("status") != "ready":
        raise JBrowseLocationError(
            "The requested Assembly and Annotation are not ready for JBrowse.",
            code="jbrowse_not_ready",
            http_status=503,
        )

    source_file = select_annotation_source_file(annotation.id)
    if source_file is None:
        raise JBrowseLocationError(
            "The current annotation source is unavailable.",
            code="annotation_index_unavailable",
            http_status=503,
        )
    try:
        feature_index = get_ready_annotation_index(
            annotation,
            {"file_id": source_file.id, "file_path": source_file.file_path},
        )
    except AnnotationIndexUnavailable as exc:
        raise JBrowseLocationError(
            "The annotation feature index is unavailable or stale.",
            code="annotation_index_unavailable",
            http_status=503,
        ) from exc

    current_version = feature_index_version(feature_index)
    if expected_index_version and expected_index_version != current_version:
        raise JBrowseLocationError(
            "The annotation feature index version changed.",
            code="feature_index_version_conflict",
            http_status=409,
        )
    feature = AnnotationFeature.objects.filter(
        id=feature_id, feature_index=feature_index
    ).first()
    if feature is None:
        raise _not_found()

    try:
        genome_file, fasta_index = select_mapping_inputs(assembly)
        mapping = load_current_refname_mapping(
            assembly, genome_file, fasta_index
        )
        ref_name, sequence_length = resolve_refname(mapping, feature.seqid)
    except ReferenceNameError as exc:
        if exc.code == "alias_ambiguous":
            http_status = 409
        elif exc.code == "alias_missing":
            http_status = 422
        else:
            http_status = 503
        raise JBrowseLocationError(
            str(exc), code=exc.code, http_status=http_status
        ) from exc

    if feature.start < 1 or feature.end < feature.start or feature.end > sequence_length:
        raise JBrowseLocationError(
            "The feature coordinates are invalid for the mapped reference.",
            code="coordinate_out_of_bounds",
            http_status=422,
        )

    padding = max(math.ceil(feature.length * 0.2), 500)
    view_start = max(1, feature.start - padding)
    view_end = min(sequence_length, feature.end + padding)
    return {
        "assembly_id": assembly.id,
        "annotation_id": annotation.id,
        "feature_id": feature.id,
        "feature_index_version": current_version,
        "ref_name": ref_name,
        "feature_start": feature.start,
        "feature_end": feature.end,
        "view_start": view_start,
        "view_end": view_end,
        "loc": f"{ref_name}:{view_start}-{view_end}",
        "assembly_name": status_payload["assembly_name"],
        "track_id": status_payload["track_ids"][0],
    }


def _not_found():
    return JBrowseLocationError("Not found.", code="not_found", http_status=404)
