import csv
import hashlib
import json
from pathlib import Path

from files.models import (
    Accession, AccessionExternalMapping, Annotation, Assembly, DataFile, Dataset,
    DatasetAccession, Sample, Species,
)
from files.services.ingestion.metadata_policy import (
    plan_fill_blank_mapping,
    plan_fill_blank_metadata,
)
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

    species_objects = {item.species_code: item for item in Species.objects.all()}
    species_codes = set(species_objects)
    accessions = {item.accession: item for item in Accession.objects.all()}
    accession_codes = set(accessions)
    accession_species = {
        code: item.species.species_code if item.species_id else ""
        for code, item in accessions.items()
    }
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
    sample_objects = {
        item.sample_code: item
        for item in Sample.objects.select_related("species", "accession")
    }
    sample_codes = set(sample_objects)
    dataset_objects = {
        item.dataset_code: item
        for item in Dataset.objects.select_related("species", "project")
    }
    dataset_codes = set(dataset_objects)

    for line, row in _rows(manifests, "accessions"):
        code, species = row.get("accession"), row.get("species_code")
        if not code:
            errors.append(_issue("accessions", line, "missing_identity", "accession is required"))
        elif species not in species_codes:
            unmapped.append(_issue("accessions", line, code, f"species not found: {species}"))
        else:
            existing = accessions.get(code)
            if existing:
                _, field_conflicts = plan_fill_blank_metadata(
                    existing,
                    _accession_metadata(row, species_objects.get(species)),
                )
                _append_metadata_conflict(conflicts, "accessions", line, code, field_conflicts)
            accession_codes.add(code)
            accession_species[code] = species

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
            existing = sample_objects.get(code)
            if existing:
                field_conflicts = _sample_conflicts(existing, row, species_code=row.get("species_code"), accession_code=accession)
                _append_metadata_conflict(conflicts, "samples", line, code, field_conflicts)
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
            existing = dataset_objects.get(code)
            if existing:
                field_conflicts = _dataset_conflicts(
                    existing,
                    row,
                    species_code=accession_species.get(row.get("accession"), ""),
                    project_code=row.get("project_code"),
                )
                _append_metadata_conflict(conflicts, "datasets", line, code, field_conflicts)
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
        else:
            _validate_external_mapping_conflicts(
                line, row, accessions.get(row.get("accession")), conflicts,
            )

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
                existing_file = DataFile.objects.filter(file_path=str(path)).first()
                if existing_file:
                    field_conflicts = _raw_data_conflicts(existing_file.description, row)
                    _append_metadata_conflict(
                        conflicts, "raw_data", line, row.get("file_path"), field_conflicts,
                    )

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


def _append_metadata_conflict(conflicts, manifest, line, identity, field_conflicts):
    if field_conflicts:
        conflicts.append(_issue(
            manifest,
            line,
            identity,
            "metadata conflict: " + ", ".join(item["field"] for item in field_conflicts),
        ))


def _relation_conflict(field, existing_code, incoming_code):
    if existing_code and incoming_code and existing_code != incoming_code:
        return {"field": field, "existing": existing_code, "incoming": incoming_code}
    return None


def _float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _accession_metadata(row, species):
    return {
        "species": species,
        "sub_population": row.get("sub_population") or None,
        "country": row.get("country") or None,
        "region": row.get("region") or None,
        "longitude": _float_or_none(row.get("longitude")),
        "latitude": _float_or_none(row.get("latitude")),
        "description": row.get("description") or None,
    }


def _sample_conflicts(existing, row, *, species_code, accession_code):
    _, conflicts = plan_fill_blank_metadata(existing, {
        "sample_name": row.get("sample_name") or row.get("sample_code") or None,
        "tissue": row.get("tissue") or None,
        "treatment": row.get("treatment") or None,
        "replicate": row.get("replicate") or None,
        "data_type": row.get("data_type") or None,
        "description": row.get("description") or None,
        "biosample_accession": row.get("biosample_accession") or None,
        "experiment_accession": row.get("experiment_accession") or None,
    })
    existing_species = existing.species.species_code if existing.species_id else ""
    existing_accession = existing.accession.accession if existing.accession_id else ""
    for item in (
        _relation_conflict("species", existing_species, species_code),
        _relation_conflict("accession", existing_accession, accession_code),
    ):
        if item:
            conflicts.append(item)
    return conflicts


def _dataset_conflicts(existing, row, *, species_code, project_code):
    _, conflicts = plan_fill_blank_metadata(existing, {
        "dataset_name": row.get("dataset_name") or row.get("dataset_code") or None,
        "dataset_type": row.get("dataset_type") or None,
        "bioproject_accession": row.get("ncbi_bioproject") or None,
        "description": row.get("description") or None,
    })
    existing_species = existing.species.species_code if existing.species_id else ""
    existing_project = existing.project.project_code if existing.project_id else ""
    for item in (
        _relation_conflict("species", existing_species, species_code),
        _relation_conflict("project", existing_project, project_code),
    ):
        if item:
            conflicts.append(item)
    return conflicts


def _split_values(value):
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _validate_external_mapping_conflicts(line, row, accession, conflicts):
    if not accession:
        return
    study = row.get("ena_study") or row.get("bioproject")
    shared = {
        "external_database": row.get("external_database") or "ENA",
        "biosample_accession": row.get("biosample") or None,
        "experiment_accession": row.get("experiment") or None,
        "run_accession": row.get("run") or None,
        "scientific_name": row.get("scientific_name") or None,
        "library_strategy": row.get("library_strategy") or None,
        "instrument_platform": row.get("instrument_platform") or None,
        "instrument_model": row.get("instrument_model") or None,
    }
    urls = _split_values(row.get("fastq_ftp") or row.get("submitted_ftp"))
    checksums = _split_values(row.get("fastq_md5") or row.get("submitted_md5"))
    for index in range(max(len(urls), len(checksums), 1)):
        values = {
            **shared,
            "fastq_url": urls[index] if index < len(urls) else (urls[0] if len(urls) == 1 else None),
            "fastq_md5": checksums[index] if index < len(checksums) else (checksums[0] if len(checksums) == 1 else None),
        }
        mapping = AccessionExternalMapping.objects.filter(
            accession=accession,
            external_study_accession=study,
            biosample_accession=values["biosample_accession"],
            experiment_accession=values["experiment_accession"],
            run_accession=values["run_accession"],
            fastq_url=values["fastq_url"],
            fastq_md5=values["fastq_md5"],
        ).first()
        if mapping:
            _, field_conflicts = plan_fill_blank_metadata(mapping, values)
            _append_metadata_conflict(
                conflicts,
                "external_mappings",
                line,
                f"{accession.accession}:{study}:{index + 1}",
                field_conflicts,
            )


def _raw_data_conflicts(existing_description, row):
    if not existing_description:
        existing_raw = {}
    else:
        try:
            payload = json.loads(existing_description)
        except (TypeError, ValueError):
            return [{
                "field": "description",
                "existing": existing_description,
                "incoming": "raw_data metadata",
            }]
        if not isinstance(payload, dict):
            return [{"field": "description", "existing": payload, "incoming": "raw_data metadata"}]
        existing_raw = payload.get("raw_data") or {}
        if not isinstance(existing_raw, dict):
            return [{"field": "raw_data", "existing": existing_raw, "incoming": "raw_data metadata"}]
    _, conflicts = plan_fill_blank_mapping(existing_raw, {
        "sample_code": row.get("sample_code") or "",
        "species_code": row.get("species_code") or "",
        "raw_data_type": row.get("raw_data_type") or "",
        "sequencing_platform": row.get("sequencing_platform") or "",
        "cluster_name": row.get("cluster_name") or "",
        "check_status": row.get("check_status") or "unchecked",
        "remark": row.get("remark") or "",
    })
    return conflicts


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
