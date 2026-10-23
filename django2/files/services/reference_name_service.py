"""Shared FASTA/JBrowse reference-name parsing and mapping assets."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from files.models import DataFile, FileRelation
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_primary_genome_file_for_assembly,
)
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)


REFNAME_MAPPING_ROLE = "jbrowse_refname_aliases"
REFNAME_MAPPING_SCHEMA_VERSION = 1
REFNAME_ALGORITHM_VERSION = "fasta-first-token-oriseqid-v1"


class ReferenceNameError(RuntimeError):
    def __init__(self, message, *, code="mapping_unavailable"):
        super().__init__(message)
        self.code = code


def read_fasta_reference_names(file_path):
    """Return JBrowse refNames, source aliases, and observed sequence lengths."""
    seqids = set()
    aliases = {}
    lengths = {}
    current_seqid = None
    sequence_bases = 0
    with open(file_path, "rt", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if line.startswith(">"):
                if current_seqid is not None and sequence_bases == 0:
                    raise ValueError(f"FASTA sequence has no bases: {current_seqid}")
                if current_seqid is not None:
                    lengths[current_seqid] = sequence_bases
                header = line[1:].strip()
                seqid = header.split()[0] if header else ""
                if not seqid:
                    raise ValueError(f"empty FASTA header at line {line_number}")
                if seqid in seqids:
                    raise ValueError(f"duplicate FASTA sequence ID: {seqid}")
                seqids.add(seqid)
                aliases.setdefault(seqid, set()).add(seqid)
                for token in header.split():
                    if token.startswith("OriSeqID=") and token[9:]:
                        aliases.setdefault(token[9:], set()).add(seqid)
                current_seqid = seqid
                sequence_bases = 0
                continue
            if current_seqid is None:
                raise ValueError(
                    f"FASTA sequence encountered before header at line {line_number}"
                )
            sequence_bases += len(stripped)
    if not seqids:
        raise ValueError("FASTA contains no sequence headers")
    if current_seqid is not None and sequence_bases == 0:
        raise ValueError(f"FASTA sequence has no bases: {current_seqid}")
    lengths[current_seqid] = sequence_bases
    return seqids, aliases, lengths


def read_fai_reference_lengths(file_path):
    lengths = {}
    with open(file_path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 2 or not columns[0]:
                raise ValueError(f"invalid FAI row at line {line_number}")
            try:
                length = int(columns[1])
            except ValueError as exc:
                raise ValueError(f"invalid FAI length at line {line_number}") from exc
            if length < 1 or columns[0] in lengths:
                raise ValueError(f"invalid or duplicate FAI refName at line {line_number}")
            lengths[columns[0]] = length
    if not lengths:
        raise ValueError("FAI contains no reference rows")
    return lengths


def build_mapping_payload(assembly, genome_file, fasta_index):
    try:
        fasta_seqids, aliases, fasta_lengths = read_fasta_reference_names(
            genome_file.file_path
        )
        fai_lengths = read_fai_reference_lengths(fasta_index.file_path)
    except OSError as exc:
        raise ReferenceNameError(
            "The FASTA or FAI cannot be read", code="reference_missing"
        ) from exc
    except (UnicodeError, ValueError) as exc:
        raise ReferenceNameError(
            "The FASTA or FAI is invalid", code="reference_invalid"
        ) from exc
    if fasta_seqids != set(fai_lengths):
        raise ReferenceNameError(
            "FASTA first-token refNames do not match the FAI first column",
            code="fasta_fai_mismatch",
        )
    mismatched_lengths = sorted(
        seqid for seqid in fasta_seqids if fasta_lengths[seqid] != fai_lengths[seqid]
    )
    if mismatched_lengths:
        raise ReferenceNameError(
            "FASTA sequence lengths do not match the FAI",
            code="fasta_fai_length_mismatch",
        )

    alias_records = {}
    ambiguous_count = 0
    for alias, candidates in sorted(aliases.items()):
        ref_names = sorted(candidates)
        status = "resolved" if len(ref_names) == 1 else "ambiguous"
        if status == "ambiguous":
            ambiguous_count += 1
        alias_records[alias] = {"status": status, "ref_names": ref_names}

    return {
        "schema_version": REFNAME_MAPPING_SCHEMA_VERSION,
        "algorithm_version": REFNAME_ALGORITHM_VERSION,
        "assembly_id": assembly.id,
        "generated_at": timezone.now().isoformat(),
        "fasta": _file_fingerprint(genome_file),
        "fai": _file_fingerprint(fasta_index),
        "reference_count": len(fasta_seqids),
        "alias_count": len(alias_records),
        "ambiguous_alias_count": ambiguous_count,
        "aliases": alias_records,
        "reference_lengths": fai_lengths,
    }


def inspect_refname_mapping(assembly, genome_file, fasta_index, *, output_root=None):
    payload = build_mapping_payload(assembly, genome_file, fasta_index)
    return {
        "assembly_id": assembly.id,
        "status": "ready_for_build",
        "write_performed": False,
        "reference_count": payload["reference_count"],
        "alias_count": payload["alias_count"],
        "ambiguous_alias_count": payload["ambiguous_alias_count"],
        "planned_path": str(_mapping_path(assembly.id, output_root=output_root)),
    }


def build_refname_mapping(assembly, genome_file, fasta_index, *, output_root=None):
    payload = build_mapping_payload(assembly, genome_file, fasta_index)
    target = _mapping_path(assembly.id, output_root=output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        json.loads(temporary_path.read_text(encoding="utf-8"))
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    digest = hashlib.md5(encoded).hexdigest()
    with transaction.atomic():
        data_file, _, _, _ = create_or_get_datafile_from_path(
            file_path=str(target),
            file_name=target.name,
            file_size=len(encoded),
            md5=digest,
            description=f"JBrowse refName mapping for Assembly {assembly.id}",
        )
        update_fields = []
        for field, value in (
            ("file_size", len(encoded)),
            ("md5", digest),
            ("is_current", True),
        ):
            if getattr(data_file, field) != value:
                setattr(data_file, field, value)
                update_fields.append(field)
        if update_fields:
            data_file.save(update_fields=update_fields + ["updated_at"])
        relation, _, _ = create_or_get_file_relation(
            data_file=data_file,
            related_type="assembly",
            related_id=assembly.id,
            related_code=assembly.assembly_code or "",
            file_role=REFNAME_MAPPING_ROLE,
        )
        FileRelation.objects.filter(
            related_type="assembly",
            related_id=str(assembly.id),
            file_role=REFNAME_MAPPING_ROLE,
            is_primary=True,
        ).exclude(id=relation.id).update(is_primary=False)
        if not relation.is_primary:
            relation.is_primary = True
            relation.save(update_fields=["is_primary", "updated_at"])

    return {
        "assembly_id": assembly.id,
        "status": "built",
        "write_performed": True,
        "file_id": data_file.id,
        "file_path": str(target),
        "reference_count": payload["reference_count"],
        "alias_count": payload["alias_count"],
        "ambiguous_alias_count": payload["ambiguous_alias_count"],
    }


def load_current_refname_mapping(assembly, genome_file, fasta_index):
    relations = list(
        FileRelation.objects.select_related("file")
        .filter(
            related_type="assembly",
            related_id=str(assembly.id),
            file_role=REFNAME_MAPPING_ROLE,
            file__is_current=True,
        )
        .order_by("id")
    )
    primary = [item for item in relations if item.is_primary]
    if len(primary) > 1 or (not primary and len(relations) > 1):
        raise ReferenceNameError("Multiple current refName mappings exist", code="mapping_ambiguous")
    relation = primary[0] if primary else (relations[0] if relations else None)
    if relation is None:
        raise ReferenceNameError("The refName mapping has not been built", code="mapping_missing")
    try:
        payload = json.loads(Path(relation.file.file_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceNameError("The refName mapping is unreadable", code="mapping_invalid") from exc
    _validate_mapping_payload(payload, assembly, genome_file, fasta_index)
    return payload


def resolve_refname(payload, alias):
    record = (payload.get("aliases") or {}).get(alias)
    if not record:
        raise ReferenceNameError("No JBrowse refName exists for this seqid", code="alias_missing")
    ref_names = record.get("ref_names") or []
    if record.get("status") == "ambiguous" or len(ref_names) != 1:
        raise ReferenceNameError("The seqid maps to multiple JBrowse refNames", code="alias_ambiguous")
    ref_name = ref_names[0]
    length = (payload.get("reference_lengths") or {}).get(ref_name)
    if not isinstance(length, int) or length < 1:
        raise ReferenceNameError("The mapped refName has no valid FAI length", code="mapping_invalid")
    return ref_name, length


def select_mapping_inputs(assembly):
    try:
        genome = get_primary_genome_file_for_assembly(assembly.id)
    except GenomeFileSelectionError as exc:
        raise ReferenceNameError(str(exc), code="genome_ambiguous") from exc
    if not genome:
        raise ReferenceNameError("No current Assembly FASTA exists", code="genome_missing")
    genome_file = DataFile.objects.filter(id=genome["file_id"], is_current=True).first()
    fasta_index = _select_single_file(assembly.id, "genome_index")
    if genome_file is None or fasta_index is None:
        raise ReferenceNameError("FASTA or FAI is unavailable", code="reference_missing")
    return genome_file, fasta_index


def _select_single_file(assembly_id, role):
    relations = list(
        FileRelation.objects.select_related("file")
        .filter(
            related_type="assembly",
            related_id=str(assembly_id),
            file_role=role,
            file__is_current=True,
        )
        .order_by("id")
    )
    primary = [item for item in relations if item.is_primary]
    if len(primary) > 1 or (not primary and len(relations) > 1):
        raise ReferenceNameError(f"Multiple current {role} files exist", code="reference_ambiguous")
    relation = primary[0] if primary else (relations[0] if relations else None)
    return relation.file if relation else None


def _file_fingerprint(data_file):
    try:
        stat = os.stat(data_file.file_path)
    except OSError as exc:
        raise ReferenceNameError("A reference source file is unavailable", code="reference_missing") from exc
    return {
        "data_file_id": data_file.id,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "md5": data_file.md5 or "",
    }


def _validate_mapping_payload(payload, assembly, genome_file, fasta_index):
    if payload.get("schema_version") != REFNAME_MAPPING_SCHEMA_VERSION:
        raise ReferenceNameError("The refName mapping schema is unsupported", code="mapping_stale")
    if payload.get("algorithm_version") != REFNAME_ALGORITHM_VERSION:
        raise ReferenceNameError("The refName mapping algorithm changed", code="mapping_stale")
    if payload.get("assembly_id") != assembly.id:
        raise ReferenceNameError("The refName mapping belongs to another Assembly", code="mapping_invalid")
    if payload.get("fasta") != _file_fingerprint(genome_file):
        raise ReferenceNameError("The FASTA changed after mapping generation", code="mapping_stale")
    if payload.get("fai") != _file_fingerprint(fasta_index):
        raise ReferenceNameError("The FAI changed after mapping generation", code="mapping_stale")


def _mapping_path(assembly_id, *, output_root=None):
    configured = output_root or getattr(settings, "GENEDATA_JBROWSE_DATA_DIR", None)
    if not configured:
        configured = Path(settings.GENEDATA_DERIVED_DATA_DIR) / "jbrowse"
    root = Path(configured).resolve()
    return root / "assemblies" / f"assembly-{assembly_id}" / "refname-aliases.json"
