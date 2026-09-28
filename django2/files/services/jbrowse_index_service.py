"""Preflight checks and safe artifact generation for JBrowse indexes."""

import heapq
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction

from files.models import DataFile, FileRelation
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.fasta_index_service import build_fasta_index
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_primary_genome_file_for_assembly,
)
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)


ANNOTATION_SOURCE_ROLE = "annotation"
JBROWSE_GFF3_ROLE = "jbrowse_annotation_gff3"
JBROWSE_TABIX_ROLE = "jbrowse_annotation_tabix"
SORT_CHUNK_SIZE = 100000


class JBrowseIndexBuildError(RuntimeError):
    pass


def inspect_jbrowse_assembly(assembly_id, output_root=None):
    """Inspect one visible Assembly without changing files or database rows."""
    assembly = (
        visible_assembly_queryset()
        .select_related("accession")
        .filter(id=assembly_id)
        .first()
    )
    if assembly is None:
        return _result(assembly_id, "assembly_not_found")

    result = _result(
        assembly.id,
        "checking",
        assembly_code=assembly.assembly_code or "",
        accession=assembly.accession.accession,
    )

    try:
        genome = get_primary_genome_file_for_assembly(assembly.id)
    except GenomeFileSelectionError as exc:
        result.update(status="ambiguous_genome", error=str(exc))
        return result
    if genome is None:
        result.update(status="missing_genome")
        return result

    result.update(
        fasta_file_id=genome["file_id"],
        fasta_path=genome["file_path"],
        fasta_role=genome["file_role"],
    )
    file_error = _file_error(genome["file_path"])
    if file_error:
        result.update(status="invalid_genome_file", error=file_error)
        return result

    try:
        fasta_seqids = _read_fasta_seqids(genome["file_path"])
    except (OSError, UnicodeError, ValueError) as exc:
        result.update(status="invalid_genome_file", error=str(exc))
        return result
    result["fasta_sequence_count"] = len(fasta_seqids)

    annotation = assembly.annotations.filter(is_default=True).order_by("id").first()
    root = _resolve_output_root(output_root)
    result["planned_fasta_index"] = str(
        root / "assemblies" / f"assembly-{assembly.id}" / "reference.fasta.fai"
    )
    if annotation is None and assembly.annotations.exists():
        result.update(status="missing_default_annotation")
        return result
    if annotation is None:
        result.update(status="reference_only", write_performed=False)
        return result

    result.update(
        annotation_id=annotation.id,
        annotation_code=annotation.annotation_code or "",
    )
    source, source_error = _select_annotation_source(annotation.id)
    if source_error:
        result.update(status=source_error)
        return result

    result.update(
        annotation_file_id=source.file_id,
        annotation_path=source.file.file_path,
    )
    file_error = _file_error(source.file.file_path)
    if file_error:
        result.update(status="invalid_annotation_file", error=file_error)
        return result

    try:
        annotation_info = _inspect_gff(source.file.file_path)
    except (OSError, UnicodeError, ValueError) as exc:
        result.update(status="invalid_annotation_file", error=str(exc))
        return result
    result.update(annotation_info)

    if annotation_info["malformed_count"]:
        result.update(status="invalid_annotation_format")
        return result
    if annotation_info["detected_format"] not in {
        "declared_gff3",
        "likely_gff3_without_header",
    }:
        result.update(status="invalid_annotation_format")
        return result

    gff_seqids = set(annotation_info.pop("gff_seqids"))
    missing = sorted(gff_seqids - fasta_seqids)
    unannotated = sorted(fasta_seqids - gff_seqids)
    result.update(
        gff_seqid_count=len(gff_seqids),
        gff_seqids_missing_from_fasta=missing,
        unannotated_fasta_seqids=unannotated,
    )
    if missing:
        result.update(status="seqid_mismatch")
        return result

    annotation_dir = root / "annotations" / f"annotation-{annotation.id}"
    result.update(
        planned_annotation_gff3=str(annotation_dir / "features.sorted.gff3.gz"),
        planned_annotation_tabix=str(annotation_dir / "features.sorted.gff3.gz.tbi"),
        status="ready_for_build",
        write_performed=False,
    )
    return result


def build_jbrowse_assembly_indexes(
    assembly_id,
    output_root=None,
    bgzip_command=None,
    tabix_command=None,
):
    """Build and register JBrowse artifacts after a successful preflight."""
    preflight = inspect_jbrowse_assembly(assembly_id, output_root=output_root)
    if preflight["status"] not in {"ready_for_build", "reference_only"}:
        raise JBrowseIndexBuildError(f"preflight failed: {preflight['status']}")

    bgzip_path = tabix_path = None
    if preflight["status"] == "ready_for_build":
        bgzip_path = _resolve_tool(
            bgzip_command or getattr(settings, "GENEDATA_BGZIP_COMMAND", "bgzip")
        )
        tabix_path = _resolve_tool(
            tabix_command or getattr(settings, "GENEDATA_TABIX_COMMAND", "tabix")
        )

    root = _resolve_output_root(output_root)
    lock_dir = root / ".locks" / f"assembly-{assembly_id}.lock"
    _acquire_lock(lock_dir)
    workspace = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f".assembly-{assembly_id}-", dir=str(root)))
        staged_fai = workspace / "reference.fasta.fai"
        _, fasta_entries = build_fasta_index(preflight["fasta_path"], str(staged_fai))

        staged = {"fasta_index": staged_fai}
        if preflight["status"] == "ready_for_build":
            staged_sorted = workspace / "features.sorted.gff3"
            staged_gff3 = workspace / "features.sorted.gff3.gz"
            _write_sorted_gff3(
                preflight["annotation_path"],
                staged_sorted,
                fasta_seqids=[entry[0] for entry in fasta_entries],
                workspace=workspace,
            )
            _run_bgzip(bgzip_path, staged_sorted, staged_gff3)
            _run_tabix(tabix_path, staged_gff3)
            staged_tabix = Path(f"{staged_gff3}.tbi")
            if not staged_gff3.is_file() or staged_gff3.stat().st_size == 0:
                raise JBrowseIndexBuildError("bgzip did not create a non-empty GFF3 file")
            if not staged_tabix.is_file() or staged_tabix.stat().st_size == 0:
                raise JBrowseIndexBuildError("tabix did not create a non-empty TBI file")
            staged.update(annotation_gff3=staged_gff3, annotation_tabix=staged_tabix)

        targets = _artifact_targets(preflight)
        backups = _promote_with_backups(staged, targets, workspace)
        try:
            registered = _register_artifacts(preflight, targets)
        except Exception:
            _restore_promoted_files(targets, backups)
            raise
        _discard_backups(backups)
        return {
            **preflight,
            "status": "built",
            "write_performed": True,
            "artifacts": registered,
        }
    finally:
        if workspace:
            shutil.rmtree(workspace, ignore_errors=True)
        _release_lock(lock_dir)


def _resolve_tool(command):
    resolved = shutil.which(str(command))
    if not resolved:
        raise JBrowseIndexBuildError(f"required command is unavailable: {command}")
    return resolved


def _acquire_lock(lock_dir):
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_dir.mkdir()
    except FileExistsError as exc:
        raise JBrowseIndexBuildError(
            f"another JBrowse build is active for {lock_dir.stem}"
        ) from exc


def _release_lock(lock_dir):
    try:
        lock_dir.rmdir()
    except FileNotFoundError:
        pass


def _write_sorted_gff3(source_path, target_path, *, fasta_seqids, workspace):
    order = {seqid: index for index, seqid in enumerate(fasta_seqids)}
    chunks = []
    records = []
    with open(source_path, "rt", encoding="utf-8-sig") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) != 9:
                raise JBrowseIndexBuildError(f"invalid GFF column count at line {line_number}")
            try:
                start = int(columns[3])
                end = int(columns[4])
            except ValueError as exc:
                raise JBrowseIndexBuildError(
                    f"invalid GFF coordinates at line {line_number}"
                ) from exc
            if columns[0] not in order:
                raise JBrowseIndexBuildError(
                    f"GFF seqid is absent from FASTA at line {line_number}: {columns[0]}"
                )
            records.append((order[columns[0]], start, end, line_number, line))
            if len(records) >= SORT_CHUNK_SIZE:
                chunks.append(_write_sort_chunk(records, workspace, len(chunks)))
                records = []
    if records:
        chunks.append(_write_sort_chunk(records, workspace, len(chunks)))

    with open(target_path, "wt", encoding="utf-8", newline="\n") as target:
        target.write("##gff-version 3\n")
        handles = [open(path, "rt", encoding="utf-8") for path in chunks]
        try:
            iterators = (_iter_sort_chunk(handle) for handle in handles)
            for _, _, _, _, line in heapq.merge(*iterators):
                target.write(line)
                target.write("\n")
        finally:
            for handle in handles:
                handle.close()


def _write_sort_chunk(records, workspace, chunk_number):
    records.sort(key=lambda item: item[:4])
    path = workspace / f"sort-{chunk_number:06d}.chunk"
    with open(path, "wt", encoding="utf-8", newline="\n") as handle:
        for seq_order, start, end, line_number, line in records:
            handle.write(f"{seq_order}\t{start}\t{end}\t{line_number}\t{line}\n")
    return path


def _iter_sort_chunk(handle):
    for raw_line in handle:
        seq_order, start, end, line_number, line = raw_line.rstrip("\n").split("\t", 4)
        yield int(seq_order), int(start), int(end), int(line_number), line


def _run_bgzip(command, source_path, target_path):
    with open(target_path, "wb") as output:
        completed = subprocess.run(
            [command, "-c", str(source_path)],
            stdout=output,
            stderr=subprocess.PIPE,
            check=False,
        )
    if completed.returncode:
        raise JBrowseIndexBuildError(
            f"bgzip failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )


def _run_tabix(command, gff3_path):
    completed = subprocess.run(
        [command, "-f", "-p", "gff", str(gff3_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise JBrowseIndexBuildError(
            f"tabix failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )


def _artifact_targets(preflight):
    targets = {"fasta_index": Path(preflight["planned_fasta_index"])}
    if preflight["status"] == "ready_for_build":
        targets.update(
            annotation_gff3=Path(preflight["planned_annotation_gff3"]),
            annotation_tabix=Path(preflight["planned_annotation_tabix"]),
        )
    return targets


def _promote_with_backups(staged, targets, workspace):
    backups = {}
    affected = []
    try:
        for name, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            affected.append(name)
            if target.exists():
                backup = workspace / f"backup-{name}"
                os.replace(target, backup)
                backups[name] = backup
            os.replace(staged[name], target)
    except Exception:
        _restore_promoted_files(
            {name: targets[name] for name in affected},
            backups,
        )
        raise
    return backups


def _restore_promoted_files(targets, backups):
    for name, target in targets.items():
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        backup = backups.get(name)
        if backup and backup.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, target)


def _discard_backups(backups):
    for backup in backups.values():
        try:
            backup.unlink()
        except FileNotFoundError:
            pass


@transaction.atomic
def _register_artifacts(preflight, targets):
    specifications = [
        (
            "fasta_index",
            "assembly",
            preflight["assembly_id"],
            preflight["assembly_code"],
            "genome_index",
        )
    ]
    if preflight["status"] == "ready_for_build":
        specifications.extend(
            [
                (
                    "annotation_gff3",
                    "annotation",
                    preflight["annotation_id"],
                    preflight["annotation_code"],
                    JBROWSE_GFF3_ROLE,
                ),
                (
                    "annotation_tabix",
                    "annotation",
                    preflight["annotation_id"],
                    preflight["annotation_code"],
                    JBROWSE_TABIX_ROLE,
                ),
            ]
        )

    registered = []
    for name, related_type, related_id, related_code, role in specifications:
        path = targets[name]
        data_file, _, _, _ = create_or_get_datafile_from_path(
            file_path=str(path),
            file_name=path.name,
            file_size=path.stat().st_size,
            description=f"JBrowse artifact for {related_type} {related_id}",
        )
        DataFile.objects.filter(id=data_file.id).update(
            file_size=path.stat().st_size,
            is_current=True,
        )
        relation, _, _ = create_or_get_file_relation(
            data_file=data_file,
            related_type=related_type,
            related_id=related_id,
            related_code=related_code,
            file_role=role,
        )
        FileRelation.objects.filter(
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=True,
        ).exclude(id=relation.id).update(is_primary=False)
        if not relation.is_primary:
            relation.is_primary = True
            relation.save(update_fields=["is_primary", "updated_at"])
        registered.append(
            {
                "file_id": data_file.id,
                "file_role": role,
                "file_path": str(path),
                "file_size": path.stat().st_size,
            }
        )
    return registered


def _result(assembly_id, status, **extra):
    value = {
        "assembly_id": assembly_id,
        "status": status,
        "write_performed": False,
    }
    value.update(extra)
    return value


def _resolve_output_root(output_root):
    configured = output_root or getattr(settings, "GENEDATA_JBROWSE_DATA_DIR", None)
    if not configured:
        configured = os.environ.get("GENEDATA_JBROWSE_DATA_DIR")
    if not configured:
        configured = Path(settings.BASE_DIR) / "derived_data" / "jbrowse"
    return Path(configured).resolve()


def _file_error(file_path):
    if not file_path:
        return "file path is empty"
    if not os.path.isfile(file_path):
        return f"file does not exist: {file_path}"
    if not os.access(file_path, os.R_OK):
        return f"file is not readable: {file_path}"
    if os.path.getsize(file_path) <= 0:
        return f"file is empty: {file_path}"
    return ""


def _read_fasta_seqids(file_path):
    seqids = set()
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
                seqid = line[1:].strip().split()[0] if line[1:].strip() else ""
                if not seqid:
                    raise ValueError(f"empty FASTA header at line {line_number}")
                if seqid in seqids:
                    raise ValueError(f"duplicate FASTA sequence ID: {seqid}")
                seqids.add(seqid)
                current_seqid = seqid
                sequence_bases = 0
                continue
            if current_seqid is None:
                raise ValueError(f"FASTA sequence encountered before header at line {line_number}")
            sequence_bases += len(stripped)
    if not seqids:
        raise ValueError("FASTA contains no sequence headers")
    if current_seqid is not None and sequence_bases == 0:
        raise ValueError(f"FASTA sequence has no bases: {current_seqid}")
    return seqids


def _select_annotation_source(annotation_id):
    relations = list(
        FileRelation.objects.select_related("file")
        .filter(
            related_type="annotation",
            related_id=str(annotation_id),
            file_role=ANNOTATION_SOURCE_ROLE,
            file__is_current=True,
        )
        .order_by("id")
    )
    primary = [relation for relation in relations if relation.is_primary]
    if len(primary) > 1:
        return None, "ambiguous_annotation_source"
    if primary:
        return primary[0], ""
    if len(relations) == 1:
        return relations[0], ""
    if not relations:
        return None, "missing_annotation_source"
    return None, "ambiguous_annotation_source"


def _inspect_gff(file_path):
    seqids = set()
    feature_count = 0
    malformed_count = 0
    declared_gff3 = False
    gff3_attribute_count = 0
    gtf_attribute_count = 0

    with open(file_path, "rt", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("##gff-version"):
                declared_gff3 = line.split(maxsplit=1)[-1].strip() == "3"
                continue
            if line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) != 9:
                malformed_count += 1
                continue
            try:
                start = int(columns[3])
                end = int(columns[4])
            except ValueError:
                malformed_count += 1
                continue
            if not columns[0] or start < 1 or end < start:
                malformed_count += 1
                continue
            feature_count += 1
            seqids.add(columns[0])
            attributes = columns[8].strip()
            if "=" in attributes:
                gff3_attribute_count += 1
            elif attributes not in {"", "."} and '"' in attributes:
                gtf_attribute_count += 1

    if feature_count == 0:
        raise ValueError("annotation contains no valid nine-column features")
    if declared_gff3:
        detected_format = "declared_gff3"
    elif gff3_attribute_count:
        detected_format = "likely_gff3_without_header"
    elif gtf_attribute_count:
        detected_format = "likely_gtf"
    else:
        detected_format = "unknown"
    return {
        "gff_feature_count": feature_count,
        "gff_version": "3" if declared_gff3 else None,
        "detected_format": detected_format,
        "malformed_count": malformed_count,
        "gff_seqids": sorted(seqids),
    }
