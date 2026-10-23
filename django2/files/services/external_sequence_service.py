"""Random-access FASTA regions for the external API."""

import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from files.models import Assembly, DataFile, FileRelation
from files.parsers.fasta import (
    fetch_sequence_region,
    read_fai_entries,
)
from files.services.assembly_visibility import public_assembly_list_queryset
from files.services.datafile_access_service import (
    ACTION_SEQUENCE,
    resolve_datafile_access,
    resolve_datafile_access_level,
    resolve_protected_datafile_path,
)
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_primary_genome_file_for_assembly,
)
from files.services.reference_name_service import (
    ReferenceNameError,
    load_current_refname_mapping,
    resolve_refname,
)


class SequenceRegionError(RuntimeError):
    def __init__(self, code, message, http_status):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class SequenceRegionResult:
    assembly_code: str
    sequence_id: str
    start: int
    end: int
    content: bytes


def find_external_assembly(identifier):
    queryset = public_assembly_list_queryset(
        Assembly.objects.select_related("accession")
    )
    exact_code = list(queryset.filter(assembly_code=identifier)[:2])
    if len(exact_code) == 1:
        return exact_code[0]
    if len(exact_code) > 1:
        raise SequenceRegionError(
            "assembly_ambiguous", "Multiple assemblies match this code.", 409
        )
    accessions = list(queryset.filter(assembly_accession=identifier)[:2])
    if len(accessions) == 1:
        return accessions[0]
    if len(accessions) > 1:
        raise SequenceRegionError(
            "assembly_ambiguous", "Multiple assemblies match this accession.", 409
        )
    return None


def fetch_assembly_sequence_region(
    assembly,
    *,
    principal,
    sequence_id,
    start,
    end,
):
    start, end = _validate_coordinates(start, end)
    genome_file, fasta_path, index_file, index_path = _resolve_reference_files(
        assembly,
        principal,
    )
    try:
        entries = read_fai_entries(index_path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SequenceRegionError(
            "fasta_index_invalid", "The FASTA index is invalid.", 409
        ) from exc

    canonical_id = _resolve_sequence_id(
        assembly,
        genome_file,
        index_file,
        sequence_id,
        entries,
    )
    entry = entries.get(canonical_id)
    if entry is None:
        raise SequenceRegionError(
            "sequence_not_found", "The requested sequence does not exist.", 404
        )
    if end > entry.length:
        raise SequenceRegionError(
            "invalid_region", "The region exceeds the sequence length.", 400
        )

    base_count = end - start + 1
    max_bases = getattr(settings, "GENEDATA_SEQUENCE_MAX_BASES", 1_000_000)
    if base_count > max_bases:
        raise SequenceRegionError(
            "region_too_large",
            f"The region exceeds the {max_bases} base limit.",
            413,
        )
    try:
        sequence = fetch_sequence_region(
            fasta_path,
            canonical_id,
            start,
            end,
            index_path,
        )
    except (OSError, ValueError) as exc:
        raise SequenceRegionError(
            "reference_read_failed", "The indexed FASTA region cannot be read.", 409
        ) from exc

    assembly_code = assembly.assembly_code or str(assembly.id)
    header = f">{assembly_code}|{canonical_id}:{start}-{end}\n".encode("utf-8")
    body = _wrap_fasta(sequence)
    content = header + body
    max_bytes = getattr(
        settings,
        "GENEDATA_SEQUENCE_MAX_RESPONSE_BYTES",
        1_100_000,
    )
    if len(content) > max_bytes:
        raise SequenceRegionError(
            "response_too_large",
            f"The FASTA response exceeds the {max_bytes} byte limit.",
            413,
        )
    return SequenceRegionResult(
        assembly_code=assembly_code,
        sequence_id=canonical_id,
        start=start,
        end=end,
        content=content,
    )


def _resolve_reference_files(assembly, principal):
    genome_file, index_file = _select_reference_files(assembly)
    fasta_path = _public_sequence_path(genome_file, principal, "genome_not_found")
    index_path = _public_sequence_path(
        index_file,
        principal,
        "fasta_index_required",
    )
    if os.path.getmtime(index_path) < os.path.getmtime(fasta_path):
        raise SequenceRegionError(
            "fasta_index_stale", "The FASTA index is older than the FASTA.", 409
        )
    return genome_file, fasta_path, index_file, index_path


def _select_reference_files(assembly):
    try:
        selected = get_primary_genome_file_for_assembly(assembly.id)
    except GenomeFileSelectionError as exc:
        raise SequenceRegionError("genome_ambiguous", str(exc), 409) from exc
    if not selected:
        raise SequenceRegionError(
            "genome_not_found", "No current genome FASTA is configured.", 404
        )
    try:
        genome_file = DataFile.objects.select_related("dataset").get(
            id=selected["file_id"]
        )
    except DataFile.DoesNotExist as exc:
        raise SequenceRegionError(
            "genome_not_found", "No current genome FASTA is configured.", 404
        ) from exc
    if genome_file.file_name.lower().endswith(".gz"):
        raise SequenceRegionError(
            "unsupported_fasta_compression",
            "Compressed FASTA random access is not supported.",
            409,
        )

    expected_names = {
        f"{genome_file.file_name}.fai",
        f"{Path(genome_file.file_path).name}.fai",
    }
    relations = list(
        FileRelation.objects.select_related("file", "file__dataset")
        .filter(
            related_type="assembly",
            related_id=str(assembly.id),
            file_role__in=("genome_index", "fai"),
            file__is_current=True,
            file__file_name__in=expected_names,
        )
        .order_by("id")
    )
    primary = [relation for relation in relations if relation.is_primary]
    if len(primary) > 1 or (not primary and len(relations) > 1):
        raise SequenceRegionError(
            "fasta_index_ambiguous", "Multiple current FASTA indexes match.", 409
        )
    relation = primary[0] if primary else (relations[0] if relations else None)
    if relation is None:
        raise SequenceRegionError(
            "fasta_index_required", "A current FASTA index is required.", 409
        )
    return genome_file, relation.file


def inspect_public_fasta_index(assembly):
    """Return the deployment-gate status for one public Assembly FASTA."""
    try:
        genome_file, index_file = _select_reference_files(assembly)
    except SequenceRegionError as exc:
        status_map = {
            "genome_not_found": "MISSING_FILE",
            "genome_ambiguous": "INVALID_INDEX",
            "fasta_index_required": "MISSING_INDEX",
            "fasta_index_ambiguous": "INVALID_INDEX",
            "unsupported_fasta_compression": "INVALID_INDEX",
        }
        return {
            "status": status_map.get(exc.code, "INVALID_INDEX"),
            "detail": exc.code,
        }
    for data_file, missing_status in (
        (genome_file, "MISSING_FILE"),
        (index_file, "MISSING_INDEX"),
    ):
        level, _reason = resolve_datafile_access_level(data_file)
        if (
            not data_file.is_current
            or data_file.publication_status != DataFile.PUBLICATION_RELEASED
            or data_file.published_at is None
            or data_file.content_version is None
            or level != DataFile.ACCESS_LEVEL_PUBLIC
        ):
            return {"status": missing_status, "detail": "not_publicly_released"}
    fasta_location = resolve_protected_datafile_path(genome_file)
    index_location = resolve_protected_datafile_path(index_file)
    if not fasta_location.allowed:
        return {"status": "MISSING_FILE", "detail": fasta_location.reason}
    if not index_location.allowed:
        return {"status": "MISSING_INDEX", "detail": index_location.reason}
    if os.path.getmtime(index_location.resolved_path) < os.path.getmtime(
        fasta_location.resolved_path
    ):
        return {"status": "STALE_INDEX", "detail": "fasta_index_stale"}
    try:
        entries = read_fai_entries(index_location.resolved_path)
    except (OSError, UnicodeError, ValueError):
        return {"status": "INVALID_INDEX", "detail": "fasta_index_invalid"}
    return {
        "status": "PASS",
        "detail": "ready",
        "genome_file_id": genome_file.id,
        "index_file_id": index_file.id,
        "sequence_count": len(entries),
    }


def _public_sequence_path(data_file, principal, missing_code):
    decision = resolve_datafile_access(
        data_file,
        principal=principal,
        action=ACTION_SEQUENCE,
    )
    if not decision.allowed:
        if decision.reason in {
            "authentication_required",
            "invalid_or_inactive_token",
            "insufficient_scope",
            "insufficient_access_tier",
        }:
            raise SequenceRegionError(decision.reason, "Access denied.", 403)
        raise SequenceRegionError(missing_code, "Reference data is unavailable.", 404)
    if decision.effective_access_level != DataFile.ACCESS_LEVEL_PUBLIC:
        raise SequenceRegionError(missing_code, "Reference data is unavailable.", 404)
    location = resolve_protected_datafile_path(data_file)
    if not location.allowed:
        raise SequenceRegionError(missing_code, "Reference data is unavailable.", 404)
    return location.resolved_path


def _resolve_sequence_id(assembly, genome_file, index_file, requested, entries):
    requested = str(requested or "").strip()
    if not requested:
        raise SequenceRegionError(
            "invalid_region", "The sequence parameter is required.", 400
        )
    if requested in entries:
        return requested
    try:
        mapping = load_current_refname_mapping(assembly, genome_file, index_file)
        canonical, _length = resolve_refname(mapping, requested)
    except ReferenceNameError:
        canonical = None
    if canonical not in entries:
        raise SequenceRegionError(
            "sequence_not_found", "The requested sequence does not exist.", 404
        )
    return canonical


def _validate_coordinates(start, end):
    try:
        start = int(start)
        end = int(end)
    except (TypeError, ValueError) as exc:
        raise SequenceRegionError(
            "invalid_region", "start and end must be integers.", 400
        ) from exc
    if start < 1 or end < start:
        raise SequenceRegionError(
            "invalid_region",
            "Coordinates must satisfy 1 <= start <= end.",
            400,
        )
    return start, end


def _wrap_fasta(sequence, width=60):
    return b"\n".join(
        sequence[offset:offset + width]
        for offset in range(0, len(sequence), width)
    ) + b"\n"
