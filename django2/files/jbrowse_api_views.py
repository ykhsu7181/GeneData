"""Protected browser-asset responses delegated to Nginx via X-Accel-Redirect."""

import os
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from files.models import Annotation, DataFile, FileRelation
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.jbrowse_config_service import (
    JBrowseAssemblyNotFound,
    get_jbrowse_config,
    get_jbrowse_status,
)


ROLE_SUFFIXES = {
    "genome": (".fa", ".fasta", ".fna"),
    "genome_fasta": (".fa", ".fasta", ".fna"),
    "genome_index": (".fai",),
    "jbrowse_annotation_gff3": (".gff.gz", ".gff3.gz"),
    "jbrowse_annotation_tabix": (".tbi",),
}


@api_view(["GET"])
@permission_classes([AllowAny])
def jbrowse_status(request, assembly_id):
    annotation_id, error_response = _annotation_id_parameter(request)
    if error_response is not None:
        return error_response
    try:
        payload = get_jbrowse_status(assembly_id, annotation_id=annotation_id)
    except JBrowseAssemblyNotFound:
        return _not_found()
    return Response(payload)


@api_view(["GET"])
@permission_classes([AllowAny])
def jbrowse_config(request, assembly_id):
    annotation_id, error_response = _annotation_id_parameter(request)
    if error_response is not None:
        return error_response
    try:
        config, status_payload = get_jbrowse_config(
            assembly_id,
            annotation_id=annotation_id,
        )
    except JBrowseAssemblyNotFound:
        return _not_found()
    if config is None:
        return Response(status_payload, status=status.HTTP_409_CONFLICT)
    return Response(config)


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def browser_asset(request, file_id):
    data_file = DataFile.objects.filter(id=file_id, is_current=True).first()
    if data_file is None:
        return _not_found()

    relation = _visible_jbrowse_relation(data_file)
    if relation is None:
        return _not_found()

    mapping = _internal_path_mapping(data_file.file_path)
    if mapping is None:
        return _not_found()
    internal_uri, content_type = mapping

    response = HttpResponse(status=status.HTTP_200_OK, content_type=content_type)
    response["X-Accel-Redirect"] = internal_uri
    response["Content-Disposition"] = _inline_content_disposition(data_file.file_name)
    response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _visible_jbrowse_relation(data_file):
    relations = list(
        FileRelation.objects.filter(
            file=data_file,
            file_role__in=ROLE_SUFFIXES,
        ).order_by("id")
    )
    if not relations:
        return None

    visible_assembly_ids = set(
        visible_assembly_queryset().values_list("id", flat=True)
    )
    annotation_ids = []
    for relation in relations:
        if relation.related_type == "assembly":
            related_id = _integer_id(relation.related_id)
            if related_id in visible_assembly_ids and _role_matches_path(
                relation.file_role, data_file.file_path
            ):
                return relation
        elif relation.related_type == "annotation":
            related_id = _integer_id(relation.related_id)
            if related_id is not None:
                annotation_ids.append(related_id)

    visible_annotation_ids = set(
        Annotation.objects.filter(
            id__in=annotation_ids,
            assembly_id__in=visible_assembly_ids,
        ).values_list("id", flat=True)
    )
    for relation in relations:
        if (
            relation.related_type == "annotation"
            and _integer_id(relation.related_id) in visible_annotation_ids
            and _role_matches_path(relation.file_role, data_file.file_path)
        ):
            return relation
    return None


def _internal_path_mapping(file_path):
    if not file_path or not os.path.isfile(file_path) or not os.access(file_path, os.R_OK):
        return None

    candidate = Path(file_path).resolve()
    roots = [
        (
            Path(settings.MANUAL_FILES_DIR).resolve(),
            getattr(
                settings,
                "GENEDATA_JBROWSE_MANUAL_INTERNAL_PREFIX",
                "/_protected_manual_files/",
            ),
        ),
        (
            Path(settings.GENEDATA_DERIVED_DATA_DIR).resolve(),
            getattr(
                settings,
                "GENEDATA_JBROWSE_DERIVED_INTERNAL_PREFIX",
                "/_protected_derived_data/",
            ),
        ),
    ]
    roots.sort(key=lambda item: len(str(item[0])), reverse=True)
    for root, prefix in roots:
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        normalized_prefix = f"/{str(prefix).strip('/')}/"
        relative_uri = quote(relative.as_posix(), safe="/")
        return f"{normalized_prefix}{relative_uri}", _content_type(candidate.name)
    return None


def _role_matches_path(role, file_path):
    normalized = str(file_path or "").lower()
    return any(normalized.endswith(suffix) for suffix in ROLE_SUFFIXES.get(role, ()))


def _content_type(file_name):
    normalized = file_name.lower()
    if normalized.endswith((".gff.gz", ".gff3.gz")):
        return "application/gzip"
    if normalized.endswith(".tbi"):
        return "application/octet-stream"
    return "text/plain; charset=utf-8"


def _inline_content_disposition(file_name):
    name = os.path.basename(file_name or "jbrowse-asset")
    ascii_name = name.encode("ascii", errors="ignore").decode("ascii")
    ascii_name = "".join(
        character for character in ascii_name if character >= " " and character not in {'"', "\\"}
    ) or "jbrowse-asset"
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


def _integer_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _annotation_id_parameter(request):
    raw_value = request.query_params.get("annotation_id")
    if raw_value in {None, ""}:
        return None, None
    value = _integer_id(raw_value)
    if value is None or value < 1:
        return None, Response(
            {"detail": "annotation_id must be a positive integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return value, None


def _not_found():
    return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
