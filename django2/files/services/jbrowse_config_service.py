"""Resolve JBrowse readiness and produce path-free browser configurations."""

import os
from pathlib import Path

from django.conf import settings

from files.models import Annotation, DataFile, FileRelation
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_primary_genome_file_for_assembly,
)


class JBrowseAssemblyNotFound(LookupError):
    pass


def get_jbrowse_status(assembly_id, annotation_id=None):
    context = _resolve_context(assembly_id, annotation_id=annotation_id)
    return _public_status(context)


def get_jbrowse_config(assembly_id, annotation_id=None):
    context = _resolve_context(assembly_id, annotation_id=annotation_id)
    public_status = _public_status(context)
    if context["status"] not in {"ready", "reference_only"}:
        return None, public_status

    assembly = context["assembly"]
    assembly_name = f"assembly-{assembly.id}"
    sequence_track = {
        "type": "ReferenceSequenceTrack",
        "trackId": f"assembly-{assembly.id}-reference",
        "name": f"{_assembly_display_name(assembly)} reference",
        "assemblyNames": [assembly_name],
        "adapter": {
            "type": "IndexedFastaAdapter",
            "fastaLocation": {"uri": _asset_uri(context["genome_file"].id)},
            "faiLocation": {"uri": _asset_uri(context["fasta_index"].id)},
        },
    }
    tracks = []
    annotation = context.get("annotation")
    if annotation is not None and context["status"] == "ready":
        tracks.append(
            {
                "type": "FeatureTrack",
                "trackId": f"annotation-{annotation.id}-features",
                "name": annotation.display_name or annotation.name,
                "assemblyNames": [assembly_name],
                "adapter": {
                    "type": "Gff3TabixAdapter",
                    "gffGzLocation": {"uri": _asset_uri(context["annotation_gff3"].id)},
                    "index": {
                        "indexType": "TBI",
                        "location": {"uri": _asset_uri(context["annotation_tabix"].id)},
                    },
                },
            }
        )

    config = {
        "assemblies": [{
            "name": assembly_name,
            "displayName": _assembly_display_name(assembly),
            "sequence": sequence_track,
        }],
        "tracks": tracks,
    }
    return config, public_status


def _resolve_context(assembly_id, annotation_id=None):
    assembly = (
        visible_assembly_queryset()
        .select_related("accession")
        .filter(id=assembly_id)
        .first()
    )
    if assembly is None:
        raise JBrowseAssemblyNotFound(assembly_id)

    context = {
        "assembly": assembly,
        "status": "checking",
        "message": "",
        "reference_ready": False,
        "annotation_ready": False,
    }
    try:
        genome_info = get_primary_genome_file_for_assembly(assembly.id)
    except GenomeFileSelectionError as exc:
        return _failed(context, "ambiguous_genome", str(exc))
    if genome_info is None:
        return _failed(context, "missing_genome", "No current genome FASTA is related.")

    genome_file = DataFile.objects.filter(id=genome_info["file_id"], is_current=True).first()
    if not _valid_file(genome_file, (".fa", ".fasta", ".fna")):
        return _failed(context, "missing_genome", "The selected genome FASTA is unavailable.")
    context["genome_file"] = genome_file

    fasta_index, relation_status = _select_artifact(
        "assembly", assembly.id, "genome_index"
    )
    if relation_status:
        status_value = (
            "ambiguous_fasta_index"
            if relation_status.startswith("ambiguous_")
            else "missing_fasta_index"
        )
        return _failed(context, status_value, "A unique current FASTA index is required.")
    if not _valid_file(fasta_index, (".fai",)):
        return _failed(context, "missing_fasta_index", "The FASTA index is unavailable.")
    if _is_stale(fasta_index.file_path, genome_file.file_path):
        return _failed(context, "stale_index", "The FASTA index is older than its source.")

    default_location = _default_location(fasta_index.file_path)
    if not default_location:
        return _failed(context, "invalid_fasta_index", "The FASTA index is invalid.")
    context.update(
        fasta_index=fasta_index,
        default_location=default_location,
        reference_ready=True,
    )

    annotation, annotation_status = _select_annotation(assembly, annotation_id)
    if annotation_status:
        return _failed(context, annotation_status, "A valid Annotation could not be selected.")
    if annotation is None:
        context.update(status="reference_only", message="No Annotation is registered.")
        return context
    context["annotation"] = annotation

    annotation_source, source_status = _select_artifact(
        "annotation", annotation.id, "annotation"
    )
    if source_status:
        status_value = (
            "ambiguous_annotation_source"
            if source_status.startswith("ambiguous_")
            else "missing_annotation_source"
        )
        return _failed(
            context,
            status_value,
            "A unique current annotation source is required.",
        )
    if not _valid_file(annotation_source, (".gff", ".gff3")):
        return _failed(
            context,
            "missing_annotation_source",
            "The annotation source is unavailable.",
        )

    annotation_gff3, gff_status = _select_artifact(
        "annotation", annotation.id, "jbrowse_annotation_gff3"
    )
    annotation_tabix, tabix_status = _select_artifact(
        "annotation", annotation.id, "jbrowse_annotation_tabix"
    )
    if gff_status or tabix_status:
        status_value = "ambiguous_annotation_index" if (
            "ambiguous" in (gff_status or "") or "ambiguous" in (tabix_status or "")
        ) else "missing_annotation_index"
        return _failed(context, status_value, "The JBrowse annotation index is incomplete.")
    if not _valid_file(annotation_gff3, (".gff.gz", ".gff3.gz")) or not _valid_file(
        annotation_tabix, (".tbi",)
    ):
        return _failed(
            context,
            "missing_annotation_index",
            "The JBrowse annotation index files are unavailable.",
        )
    if _is_stale(annotation_gff3.file_path, annotation_source.file_path) or _is_stale(
        annotation_tabix.file_path, annotation_gff3.file_path
    ):
        return _failed(context, "stale_index", "The annotation index is stale.")

    context.update(
        annotation_source=annotation_source,
        annotation_gff3=annotation_gff3,
        annotation_tabix=annotation_tabix,
        annotation_ready=True,
        status="ready",
    )
    return context


def _select_annotation(assembly, annotation_id):
    if annotation_id is not None:
        annotation = assembly.annotations.filter(id=annotation_id).first()
        return (annotation, "" if annotation else "annotation_not_found")
    annotation = assembly.annotations.filter(is_default=True).order_by("id").first()
    if annotation is not None:
        return annotation, ""
    if assembly.annotations.exists():
        return None, "missing_default_annotation"
    return None, ""


def _select_artifact(related_type, related_id, role):
    relations = list(
        FileRelation.objects.select_related("file")
        .filter(
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            file__is_current=True,
        )
        .order_by("id")
    )
    primary = [relation for relation in relations if relation.is_primary]
    if len(primary) > 1:
        return None, f"ambiguous_{role}"
    if primary:
        return primary[0].file, ""
    if len(relations) == 1:
        return relations[0].file, ""
    if not relations:
        return None, f"missing_{role}"
    return None, f"ambiguous_{role}"


def _valid_file(data_file, suffixes):
    if data_file is None or not data_file.is_current:
        return False
    normalized = str(data_file.file_path or "").lower()
    if not any(normalized.endswith(suffix) for suffix in suffixes):
        return False
    if not os.path.isfile(data_file.file_path) or not os.access(data_file.file_path, os.R_OK):
        return False
    if os.path.getsize(data_file.file_path) <= 0:
        return False
    return _is_under_allowed_root(data_file.file_path)


def _is_under_allowed_root(file_path):
    candidate = Path(file_path).resolve()
    roots = (
        Path(settings.MANUAL_FILES_DIR).resolve(),
        Path(settings.GENEDATA_DERIVED_DATA_DIR).resolve(),
    )
    return any(_is_relative_to(candidate, root) for root in roots)


def _is_relative_to(candidate, root):
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _is_stale(generated_path, source_path):
    return os.path.getmtime(generated_path) < os.path.getmtime(source_path)


def _default_location(fai_path):
    try:
        with open(fai_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                columns = line.rstrip("\r\n").split("\t")
                if len(columns) < 2:
                    continue
                length = int(columns[1])
                if not columns[0] or length < 1:
                    return ""
                return f"{columns[0]}:1..{min(length, 100000)}"
    except (OSError, UnicodeError, ValueError):
        return ""
    return ""


def _public_status(context):
    assembly = context["assembly"]
    annotation = context.get("annotation")
    payload = {
        "assembly_id": assembly.id,
        "assembly_code": assembly.assembly_code or "",
        "annotation_id": annotation.id if annotation else None,
        "status": context["status"],
        "reference_ready": context["reference_ready"],
        "annotation_ready": context["annotation_ready"],
        "message": context["message"],
    }
    if context["reference_ready"]:
        payload["default_location"] = context["default_location"]
        payload["assembly_name"] = f"assembly-{assembly.id}"
    if context["annotation_ready"] and annotation is not None:
        payload["track_ids"] = [f"annotation-{annotation.id}-features"]
    else:
        payload["track_ids"] = []
    return payload


def _failed(context, status_value, message):
    context.update(status=status_value, message=message)
    return context


def _assembly_display_name(assembly):
    return assembly.display_name or assembly.assembly_name or assembly.name


def _asset_uri(file_id):
    return f"/gd/api/files/browser-assets/{file_id}/"
