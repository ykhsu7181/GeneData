"""Path-free JBrowse status and config for the ADR-005 DataAsset path."""

import os
from urllib.parse import quote

from files.services.jbrowse_asset_service import (
    JBrowseAssetError,
    resolve_jbrowse_asset_context,
)
from files.services.reference_name_core import (
    ReferenceNameError,
    build_reference_name_payload,
)


def get_jbrowse_asset_status(annotation_asset_or_code, *, user=None, registry=None, roots=None):
    context, status = _resolve_ready_context(
        annotation_asset_or_code, user=user, registry=registry, roots=roots
    )
    return status


def get_jbrowse_asset_config(annotation_asset_or_code, *, user=None, registry=None, roots=None):
    context, status = _resolve_ready_context(
        annotation_asset_or_code, user=user, registry=registry, roots=roots
    )
    if context is None:
        return None, status
    annotation = context.annotation_asset
    reference = context.reference_asset
    assembly_name = f"asset-{reference.asset_code}"
    track_id = f"annotation-{annotation.asset_code}-features"
    config = {
        "plugins": [{
            "name": "GeneDataResponsiveLayout",
            "umdLoc": {"uri": "/jbrowse2/plugins/genedata-responsive-layout.js?v=5"},
        }],
        "assemblies": [{
            "name": assembly_name,
            "displayName": reference.name or reference.asset_code,
            "sequence": {
                "type": "ReferenceSequenceTrack",
                "trackId": f"reference-{reference.asset_code}",
                "name": f"{reference.name or reference.asset_code} reference",
                "assemblyNames": [assembly_name],
                "adapter": {
                    "type": "IndexedFastaAdapter",
                    "fastaLocation": {"uri": _asset_uri(reference, context.genome_fasta)},
                    "faiLocation": {"uri": _asset_uri(reference, context.fasta_index)},
                },
            },
        }],
        "tracks": [{
            "type": "FeatureTrack",
            "trackId": track_id,
            "name": annotation.name or annotation.asset_code,
            "assemblyNames": [assembly_name],
            "adapter": {
                "type": "Gff3TabixAdapter",
                "gffGzLocation": {"uri": _asset_uri(annotation, context.annotation_gff)},
                "index": {
                    "indexType": "TBI",
                    "location": {"uri": _asset_uri(annotation, context.tabix_index)},
                },
            },
        }],
        "defaultSession": {
            "name": f"{reference.name or reference.asset_code} browser",
            "views": [{
                "id": f"asset-{annotation.asset_code}-linear-view",
                "type": "LinearGenomeView",
                "init": {
                    "assembly": assembly_name,
                    "loc": status["default_location"],
                    "tracks": [track_id],
                },
            }],
        },
    }
    return config, status


def _resolve_ready_context(annotation_asset_or_code, *, user, registry, roots):
    try:
        context = resolve_jbrowse_asset_context(
            annotation_asset_or_code,
            user=user,
            registry=registry,
            roots=roots,
            require_indexes=True,
        )
        _validate_index_freshness(context)
        payload = build_reference_name_payload(context.genome_fasta, context.fasta_index)
        first_name = next(iter(payload["reference_lengths"]), "")
        if not first_name:
            raise ReferenceNameError("FAI has no references", code="reference_invalid")
        default_location = f"{first_name}:1..{min(payload['reference_lengths'][first_name], 100000)}"
    except (JBrowseAssetError, ReferenceNameError, OSError) as exc:
        return None, {
            "status": getattr(exc, "code", "asset_unavailable"),
            "ready": False,
        }
    return context, {
        "status": "ready",
        "ready": True,
        "annotation_asset_code": context.annotation_asset.asset_code,
        "reference_asset_code": context.reference_asset.asset_code,
        "default_location": default_location,
    }


def _validate_index_freshness(context):
    if os.path.getmtime(context.fasta_index.file_path) < os.path.getmtime(
        context.genome_fasta.file_path
    ):
        raise JBrowseAssetError("FASTA index is stale", code="fasta_index_stale")
    if os.path.getmtime(context.tabix_index.file_path) < os.path.getmtime(
        context.annotation_gff.file_path
    ):
        raise JBrowseAssetError("Tabix index is stale", code="tabix_index_stale")
    normalized = context.annotation_gff.file_path.lower()
    if not normalized.endswith((".gff.gz", ".gff3.gz")):
        raise JBrowseAssetError(
            "Annotation GFF is not bgzip-compressed", code="annotation_gff_not_bgzip"
        )
    if not context.tabix_index.file_path.lower().endswith(".tbi"):
        raise JBrowseAssetError("Tabix index suffix is invalid", code="tabix_index_invalid")


def _asset_uri(asset, data_file):
    return (
        f"/gd/api/files/browser-assets/{data_file.id}/"
        f"?asset_code={quote(asset.asset_code, safe='')}"
    )
