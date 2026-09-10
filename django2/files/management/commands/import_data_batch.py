import csv
import os
from contextlib import contextmanager
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Annotation, Assembly, Dataset, Sample
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)
from files.services.import_log_service import current_code_commit
from files.services.ingestion.batch import (
    load_batch_config,
    resolve_batch_file,
    sha256_file,
    validate_batch,
)


IMPORT_SEQUENCE = (
    ("accessions", "import_accession_manifest", "input_path"),
    ("assemblies", "import_assembly_manifest", "file"),
    ("annotations", "import_annotation_manifest", "file"),
    ("samples", "import_sample_manifest", "input_path"),
    ("datasets", "import_dataset_manifest", "input_path"),
    ("dataset_accessions", "import_dataset_accession_manifest", "input_path"),
    ("external_mappings", "import_accession_external_mapping_manifest", "input_path"),
)


class Command(BaseCommand):
    help = "Validate or apply a GeneData ingestion batch directory."

    def add_arguments(self, parser):
        parser.add_argument("--batch-dir", required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--output-dir", default=None)

    def handle(self, *args, **options):
        batch_dir = Path(options["batch_dir"]).resolve()
        config_path = batch_dir / "batch.yaml"
        if not batch_dir.is_dir() or not config_path.is_file():
            raise CommandError(f"Invalid batch directory or missing batch.yaml: {batch_dir}")
        try:
            config = load_batch_config(config_path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        output_dir = Path(options["output_dir"] or batch_dir / "reports").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        result = validate_batch(batch_dir)
        ready = not any(result[key] for key in ("errors", "conflicts", "unmapped"))
        self._write_reports(output_dir, batch_dir, config, result, ready, applied=False)

        if options["apply"]:
            if not ready:
                self.stdout.write("READY_TO_IMPORT=NO")
                raise CommandError("Batch validation failed; no import was applied.")
            # Validation is deliberately rerun immediately before writes.
            result = validate_batch(batch_dir)
            ready = not any(result[key] for key in ("errors", "conflicts", "unmapped"))
            if not ready:
                self._write_reports(output_dir, batch_dir, config, result, ready, applied=False)
                self.stdout.write("READY_TO_IMPORT=NO")
                raise CommandError("Batch validation changed before apply; no import was applied.")
            self._apply_manifests(batch_dir, output_dir, config, result["manifests"])
            self._write_reports(output_dir, batch_dir, config, result, ready=True, applied=True)

        self.stdout.write(f"READY_TO_IMPORT={'YES' if ready else 'NO'}")
        self.stdout.write(f"reports={output_dir}")

    def _apply_manifests(self, batch_dir, output_dir, config, manifests):
        common = {
            "batch_id": config["batch_id"],
            "source": config["source"],
            "source_version": config["source_version"],
        }
        with _working_directory(output_dir):
            for manifest_name, command, argument in IMPORT_SEQUENCE:
                item = manifests.get(manifest_name)
                if not item:
                    continue
                kwargs = {argument: str(item["path"]), **common}
                if command in {"import_assembly_manifest", "import_annotation_manifest"}:
                    kwargs["output_dir"] = str(output_dir)
                with transaction.atomic():
                    call_command(command, **kwargs)

            if "files" in manifests:
                self._apply_files(batch_dir, manifests["files"]["rows"])

            raw = manifests.get("raw_data")
            if raw and raw["rows"]:
                resolved_manifest = output_dir / "raw_data.resolved.tsv"
                self._write_resolved_raw_manifest(resolved_manifest, raw["rows"])
                with transaction.atomic():
                    call_command("import_raw_data_manifest", input_path=str(resolved_manifest), **common)

    def _apply_files(self, batch_dir, rows):
        with transaction.atomic():
            for row in rows:
                path = str(resolve_batch_file(batch_dir, row["file_path"]))
                data_file, _, _, _ = create_or_get_datafile_from_path(
                    file_path=path,
                    file_name=Path(path).name,
                    md5=row.get("md5") or None,
                )
                accession = Accession.objects.filter(accession=row.get("accession")).first()
                assembly = Assembly.objects.filter(assembly_code=row.get("assembly_code")).first()
                if not assembly and accession:
                    assemblies = list(accession.assemblies.all()[:2])
                    assembly = assemblies[0] if len(assemblies) == 1 else None
                annotation = Annotation.objects.filter(annotation_code=row.get("annotation_code")).first()
                if annotation and not assembly:
                    assembly = annotation.assembly
                sample = Sample.objects.filter(sample_code=row.get("sample_code")).first()
                dataset = Dataset.objects.filter(dataset_code=row.get("dataset_code")).first()
                for related_type, obj, code in (
                    ("accession", accession, row.get("accession")),
                    ("assembly", assembly, row.get("assembly_code") or (assembly.assembly_code if assembly else "")),
                    ("annotation", annotation, row.get("annotation_code")),
                    ("sample", sample, row.get("sample_code")),
                    ("dataset", dataset, row.get("dataset_code")),
                ):
                    if obj:
                        create_or_get_file_relation(
                            data_file=data_file,
                            related_type=related_type,
                            related_id=obj.id,
                            related_code=code or "",
                            file_role=row["file_role"],
                        )

    @staticmethod
    def _write_resolved_raw_manifest(path, rows):
        fieldnames = [key for key in rows[0] if key != "resolved_file_path"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            for row in rows:
                output = {key: row.get(key, "") for key in fieldnames}
                output["file_path"] = row["resolved_file_path"]
                writer.writerow(output)

    def _write_reports(self, output_dir, batch_dir, config, result, ready, applied):
        summary = {
            "batch_id": config["batch_id"],
            "source": config["source"],
            "source_version": config["source_version"],
            "description": config.get("description", ""),
            "code_commit": current_code_commit(),
            "ready_to_import": "YES" if ready else "NO",
            "applied": applied,
            "manifest_count": len(result["manifests"]),
            "error_count": len(result["errors"]),
            "conflict_count": len(result["conflicts"]),
            "unmapped_count": len(result["unmapped"]),
            "warning_count": len(result["warnings"]),
        }
        (output_dir / "batch_summary.txt").write_text(
            "\n".join(f"{key}: {value}" for key, value in summary.items()) + "\n",
            encoding="utf-8",
        )
        checksum_rows = [("batch.yaml", sha256_file(batch_dir / "batch.yaml"))]
        checksum_rows.extend(
            (str(item["path"].relative_to(batch_dir)), sha256_file(item["path"]))
            for item in result["manifests"].values()
        )
        with (output_dir / "batch_manifest_checksums.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["manifest", "sha256"])
            writer.writerows(checksum_rows)
        with (output_dir / "batch_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["order", "manifest", "row_count", "action"])
            ordered_names = [item[0] for item in IMPORT_SEQUENCE] + ["files", "raw_data"]
            for order, name in enumerate(ordered_names, 1):
                item = result["manifests"].get(name)
                if item:
                    writer.writerow([order, f"metadata/{name}.tsv", len(item["rows"]), "apply" if ready else "blocked"])
        for filename, key in (
            ("batch_errors.tsv", "errors"),
            ("batch_conflicts.tsv", "conflicts"),
            ("batch_unmapped.tsv", "unmapped"),
            ("batch_warnings.tsv", "warnings"),
        ):
            with (output_dir / filename).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["manifest", "line_number", "identity", "message"],
                    delimiter="\t",
                )
                writer.writeheader()
                writer.writerows(result[key])


@contextmanager
def _working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
