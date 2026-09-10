import csv
import hashlib
from pathlib import Path

from files.models import (
    Accession, Annotation, Assembly, Dataset, DatasetAccession, Sample, Species,
)
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata
from files.services.ingestion.roles import validate_file_role


MANIFEST_SPECS = {
    "accessions": {"accession", "species_code"},
    "assemblies": {
        "assembly_code", "accession", "assembly_name", "species_code",
        "assembly_level", "reference", "source_database", "external_project",
        "file_name", "file_type", "description",
    },
    "annotations": {
        "annotation_code", "accession", "assembly_code", "annotation_name",
        "species_code", "source_database", "external_project", "file_name",
        "file_type", "description",
    },
    "samples": {"sample_code", "species_code", "accession"},
    "datasets": {"accession", "project_code", "dataset_code", "dataset_type"},
    "dataset_accessions": {"accession", "dataset_code"},
    "external_mappings": {"accession", "ena_study"},
    "raw_data": {"file_path", "file_role"},
    "files": {
        "file_path", "file_role", "accession", "assembly_code",
        "annotation_code", "sample_code", "dataset_code", "md5",
    },
}

IDENTITY_FIELDS = {
    "accessions": ("accession",),
    "assemblies": ("assembly_code",),
    "annotations": ("annotation_code",),
    "samples": ("sample_code",),
    "datasets": ("dataset_code",),
    "dataset_accessions": ("dataset_code", "accession"),
    "raw_data": ("file_path", "file_role", "accession_code", "sample_code"),
    "files": (
        "file_path", "file_role", "accession", "assembly_code",
        "annotation_code", "sample_code", "dataset_code",
    ),
}


def load_batch_config(path):
    """Read the flat key/value subset required by the batch contract."""
    values = {}
    for line_number, raw_line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "{", "[")) or ":" not in line:
            raise ValueError(f"batch.yaml line {line_number}: only flat key: value entries are supported")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in values:
            raise ValueError(f"batch.yaml line {line_number}: invalid or duplicate key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    missing = {"batch_id", "source", "source_version"} - set(values)
    if missing:
        raise ValueError(f"batch.yaml missing keys: {', '.join(sorted(missing))}")
    return values


def load_tsv(path, required_columns):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = set(reader.fieldnames or [])
        missing = required_columns - columns
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_batch_file(batch_dir, value):
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    files_root = (Path(batch_dir) / "files").resolve()
    if path.parts and path.parts[0] == "files":
        resolved = (Path(batch_dir) / path).resolve()
    else:
        resolved = (files_root / path).resolve()
    if not resolved.is_relative_to(files_root):
        raise ValueError("relative file_path escapes the batch files directory")
    return resolved


def validate_batch(batch_dir):
    batch_dir = Path(batch_dir).resolve()
    metadata_dir = batch_dir / "metadata"
    errors, conflicts, unmapped, warnings = [], [], [], []
    manifests = {}

    for name, required in MANIFEST_SPECS.items():
        path = metadata_dir / f"{name}.tsv"
        if not path.exists():
            continue
        try:
            rows = load_tsv(path, required)
        except ValueError as exc:
            errors.append(_issue(name, "", "invalid_manifest", str(exc)))
            continue
        manifests[name] = {"path": path, "rows": rows}
        _validate_duplicates(name, rows, errors)

    if not manifests:
        errors.append(_issue("batch", "", "", "no supported manifests found"))

    species_codes = set(Species.objects.values_list("species_code", flat=True))
    accessions = {item.accession: item for item in Accession.objects.all()}
    accession_codes = set(accessions)
    assembly_objects = {
        item.assembly_code: item
        for item in Assembly.objects.select_related("accession")
        if item.assembly_code
    }
    assembly_owners = {code: item.accession.accession for code, item in assembly_objects.items()}
    annotation_objects = {
        item.annotation_code: item
        for item in Annotation.objects.select_related("assembly", "accession")
        if item.annotation_code
    }
    annotation_owners = dict(
        Annotation.objects.values_list("annotation_code", "assembly__assembly_code")
    )
    sample_codes = set(Sample.objects.values_list("sample_code", flat=True))
    dataset_codes = set(Dataset.objects.values_list("dataset_code", flat=True))

    for line, row in _rows(manifests, "accessions"):
        code, species = row.get("accession"), row.get("species_code")
        if not code:
            errors.append(_issue("accessions", line, "missing_identity", "accession is required"))
        elif species not in species_codes:
            unmapped.append(_issue("accessions", line, code, f"species not found: {species}"))
        else:
            accession_codes.add(code)

    for line, row in _rows(manifests, "assemblies"):
        code, accession = row.get("assembly_code"), row.get("accession")
        if row.get("species_code") and row.get("species_code") not in species_codes:
            unmapped.append(_issue("assemblies", line, code, f"species not found: {row.get('species_code')}"))
        if accession not in accession_codes:
            unmapped.append(_issue("assemblies", line, code, f"accession not found: {accession}"))
            continue
        owner = assembly_owners.get(code)
        if owner and owner != accession:
            conflicts.append(_issue("assemblies", line, code, "assembly identity belongs to another accession"))
        elif code:
            existing = assembly_objects.get(code)
            if existing:
                _, field_conflicts = plan_fill_blank_metadata(existing, _assembly_metadata(row))
                if field_conflicts:
                    conflicts.append(_issue(
                        "assemblies", line, code,
                        "metadata conflict: " + ", ".join(item["field"] for item in field_conflicts),
                    ))
            assembly_owners[code] = accession

    for line, row in _rows(manifests, "annotations"):
        code, accession, assembly = row.get("annotation_code"), row.get("accession"), row.get("assembly_code")
        if row.get("species_code") and row.get("species_code") not in species_codes:
            unmapped.append(_issue("annotations", line, code, f"species not found: {row.get('species_code')}"))
        if accession not in accession_codes:
            unmapped.append(_issue("annotations", line, code, f"accession not found: {accession}"))
            continue
        if assembly_owners.get(assembly) != accession:
            unmapped.append(_issue("annotations", line, code, "assembly missing or belongs to another accession"))
            continue
        owner = annotation_owners.get(code)
        if owner and owner != assembly:
            conflicts.append(_issue("annotations", line, code, "annotation identity belongs to another assembly"))
        elif code:
            existing = annotation_objects.get(code)
            if existing:
                _, field_conflicts = plan_fill_blank_metadata(
                    existing,
                    _annotation_metadata(row, accessions.get(accession)),
                )
                if field_conflicts:
                    conflicts.append(_issue(
                        "annotations", line, code,
                        "metadata conflict: " + ", ".join(item["field"] for item in field_conflicts),
                    ))
            annotation_owners[code] = assembly

    for line, row in _rows(manifests, "samples"):
        code = row.get("sample_code")
        accession = row.get("accession") or row.get("accession_code")
        if row.get("species_code") not in species_codes:
            unmapped.append(_issue("samples", line, code, f"species not found: {row.get('species_code')}"))
        elif accession not in accession_codes:
            unmapped.append(_issue("samples", line, code, f"accession not found: {accession}"))
        elif code:
            sample_codes.add(code)

    for line, row in _rows(manifests, "datasets"):
        code = row.get("dataset_code")
        valid_types = {choice[0] for choice in Dataset.DATASET_TYPE_CHOICES}
        if not row.get("project_code"):
            errors.append(_issue("datasets", line, code, "project_code is required"))
        if row.get("dataset_type") not in valid_types:
            errors.append(_issue("datasets", line, code, "invalid dataset_type"))
        if row.get("accession") not in accession_codes:
            unmapped.append(_issue("datasets", line, code, f"accession not found: {row.get('accession')}"))
        elif code:
            dataset_codes.add(code)

    for line, row in _rows(manifests, "dataset_accessions"):
        relation_role = row.get("relation_role") or "primary"
        valid_roles = {choice[0] for choice in DatasetAccession.RELATION_ROLE_CHOICES}
        if relation_role not in valid_roles:
            errors.append(_issue("dataset_accessions", line, row.get("dataset_code"), "invalid relation_role"))
        if row.get("dataset_code") not in dataset_codes:
            unmapped.append(_issue("dataset_accessions", line, row.get("dataset_code"), "dataset not found"))
        if row.get("accession") not in accession_codes:
            unmapped.append(_issue("dataset_accessions", line, row.get("accession"), "accession not found"))

    for line, row in _rows(manifests, "external_mappings"):
        if not row.get("ena_study"):
            errors.append(_issue("external_mappings", line, row.get("accession"), "ena_study is required"))
        if row.get("accession") not in accession_codes:
            unmapped.append(_issue("external_mappings", line, row.get("accession"), "accession not found"))

    for name in ("raw_data", "files"):
        for line, row in _rows(manifests, name):
            role = row.get("file_role")
            try:
                validate_file_role(role)
            except ValueError:
                errors.append(_issue(name, line, role, "unknown file_role"))
                continue
            accession = row.get("accession") or row.get("accession_code")
            sample = row.get("sample_code")
            dataset = row.get("dataset_code")
            if accession and accession not in accession_codes:
                unmapped.append(_issue(name, line, accession, "accession not found"))
            if sample and sample not in sample_codes:
                unmapped.append(_issue(name, line, sample, "sample not found"))
            if dataset and dataset not in dataset_codes:
                unmapped.append(_issue(name, line, dataset, "dataset not found"))
            if not any((accession, sample, dataset)):
                errors.append(_issue(name, line, row.get("file_path"), "no relation target"))
            if name == "files":
                _validate_file_context(
                    line, row, batch_dir, accession, assembly_owners,
                    annotation_owners, errors, conflicts, unmapped,
                )
            else:
                try:
                    path = resolve_batch_file(batch_dir, row.get("file_path", ""))
                except ValueError as exc:
                    errors.append(_issue("raw_data", line, row.get("file_path"), str(exc)))
                    continue
                row["resolved_file_path"] = str(path)
                if not path.is_file():
                    errors.append(_issue("raw_data", line, row.get("file_path"), "physical file not found"))

    return {
        "manifests": manifests,
        "errors": errors,
        "conflicts": conflicts,
        "unmapped": unmapped,
        "warnings": warnings,
    }


def _validate_file_context(line, row, batch_dir, accession, assembly_owners, annotation_owners, errors, conflicts, unmapped):
    role = row.get("file_role")
    try:
        path = resolve_batch_file(batch_dir, row.get("file_path", ""))
    except ValueError as exc:
        errors.append(_issue("files", line, row.get("file_path"), str(exc)))
        return
    row["resolved_file_path"] = str(path)
    if not path.is_file():
        errors.append(_issue("files", line, row.get("file_path"), "physical file not found"))
    if role in {"genome", "annotation"} and not accession:
        errors.append(_issue("files", line, role, "accession is required"))
    assembly = row.get("assembly_code")
    candidates = [code for code, owner in assembly_owners.items() if owner == accession and code]
    if assembly and assembly_owners.get(assembly) != accession:
        unmapped.append(_issue("files", line, assembly, "assembly missing or belongs to another accession"))
    elif not assembly and len(candidates) > 1:
        conflicts.append(_issue("files", line, accession, "ambiguous assembly; assembly_code is required"))
    elif not assembly and len(candidates) == 1:
        assembly = candidates[0]
        row["resolved_assembly_code"] = assembly
    annotation = row.get("annotation_code")
    if annotation and not assembly:
        annotation_assembly = annotation_owners.get(annotation)
        if annotation_assembly and assembly_owners.get(annotation_assembly) == accession:
            assembly = annotation_assembly
            row["resolved_assembly_code"] = assembly
    if annotation and annotation_owners.get(annotation) != assembly:
        unmapped.append(_issue("files", line, annotation, "annotation missing or belongs to another assembly"))


def _validate_duplicates(name, rows, errors):
    fields = IDENTITY_FIELDS.get(name)
    if not fields:
        return
    seen = set()
    for line, row in enumerate(rows, 2):
        identity = tuple(row.get(field, "") for field in fields)
        required_identity = identity[:2] if name in {"files", "raw_data"} else identity
        if not all(required_identity):
            errors.append(_issue(name, line, "", f"missing identity: {', '.join(fields)}"))
        elif identity in seen:
            errors.append(_issue(name, line, "|".join(identity), "duplicate identity in manifest"))
        seen.add(identity)


def _rows(manifests, name):
    return enumerate(manifests.get(name, {}).get("rows", []), 2)


def _issue(manifest, line_number, identity, message):
    return {
        "manifest": manifest,
        "line_number": line_number,
        "identity": identity or "",
        "message": message,
    }


def _assembly_metadata(row):
    name = row.get("assembly_name")
    external_id = row.get("assembly_accession")
    return {
        "name": name or None,
        "assembly_name": name or None,
        "display_name": name or None,
        "assembly_accession": external_id or None,
        "standard_id": external_id or None,
        "species_code": row.get("species_code") or None,
        "assembly_level": row.get("assembly_level") or None,
        "reference": row.get("reference") or None,
        "source_database": row.get("source_database") or None,
        "external_project": row.get("external_project") or None,
        "bio_project": row.get("external_project") or None,
        "file_name": row.get("file_name") or None,
        "file_type": row.get("file_type") or None,
        "description": row.get("description") or None,
    }


def _annotation_metadata(row, accession):
    name = row.get("annotation_name")
    version = row.get("annotation_version")
    source = row.get("source_database")
    return {
        "accession": accession,
        "name": name or None,
        "annotation_name": name or None,
        "display_name": name or None,
        "standard_id": row.get("annotation_code") or None,
        "annotation_version": version or None,
        "release_version": version or None,
        "species_code": row.get("species_code") or None,
        "source_database": source or None,
        "source_name": source or None,
        "external_project": row.get("external_project") or None,
        "file_name": row.get("file_name") or None,
        "file_type": row.get("file_type") or None,
        "description": row.get("description") or None,
    }
