import csv
import io
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Annotation, Assembly, Dataset, FileType, Sample
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
AUDIT_SEQUENCE = (
    ("audit_file_relations", "audit_file_relations"),
    ("validate_new_file_structure", "validate_new_file_structure"),
    ("audit_genome_transcriptome_readiness", "readiness"),
)
COMPRESSION_EXTENSIONS = {"bz2", "gz", "xz", "zip"}


class Command(BaseCommand):
    help = "Validate or apply a GeneData ingestion batch directory."

    def add_arguments(self, parser):
        parser.add_argument("--batch-dir", required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--output-dir", default=None)

    def handle(self, *args, **options):
        started_at = datetime.now().isoformat(timespec="seconds")
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
        self._write_reports(
            output_dir, batch_dir, config, result, ready, applied=False,
            dry_run=options["dry_run"], started_at=started_at,
        )

        if options["apply"]:
            if not ready:
                self.stdout.write("READY_TO_IMPORT=NO")
                raise CommandError("Batch validation failed; no import was applied.")
            # Validation is deliberately rerun immediately before writes.
            result = validate_batch(batch_dir)
            ready = not any(result[key] for key in ("errors", "conflicts", "unmapped"))
            if not ready:
                self._write_reports(
                    output_dir, batch_dir, config, result, ready, applied=False,
                    dry_run=False, started_at=started_at,
                )
                self.stdout.write("READY_TO_IMPORT=NO")
                raise CommandError("Batch validation changed before apply; no import was applied.")
            import_results = self._apply_manifests(
                batch_dir, output_dir, config, result["manifests"],
            )
            imports_passed = all(item["status"] == "PASS" for item in import_results)
            audit_results = self._run_post_apply_audits(output_dir)
            audits_passed = all(item["accepted"] for item in audit_results)
            self._write_reports(
                output_dir, batch_dir, config, result, ready=True, applied=True,
                dry_run=False, started_at=started_at, audit_results=audit_results,
                import_results=import_results,
            )
            if not imports_passed:
                self.stdout.write("READY_TO_IMPORT=YES")
                self.stdout.write("POST_APPLY_IMPORT=FAIL")
                raise CommandError(
                    "Batch apply completed with importer errors, conflicts, skipped, or unmapped rows. "
                    "Review batch reports before continuing."
                )
            if not audits_passed:
                self.stdout.write("READY_TO_IMPORT=YES")
                self.stdout.write("POST_APPLY_AUDIT=FAIL")
                raise CommandError(
                    "Batch data was applied, but one or more post-apply audits failed. "
                    "Review batch reports before continuing."
                )

        self.stdout.write(f"READY_TO_IMPORT={'YES' if ready else 'NO'}")
        self.stdout.write(f"reports={output_dir}")

    def _apply_manifests(self, batch_dir, output_dir, config, manifests):
        common = {
            "batch_id": config["batch_id"],
            "source": config["source"],
            "source_version": config["source_version"],
        }
        results = []
        importer_output_dir = output_dir / "importer_outputs"
        importer_output_dir.mkdir(parents=True, exist_ok=True)
        with _working_directory(output_dir):
            for manifest_name, command, argument in IMPORT_SEQUENCE:
                item = manifests.get(manifest_name)
                if not item:
                    continue
                kwargs = {argument: str(item["path"]), **common}
                if command in {"import_assembly_manifest", "import_annotation_manifest"}:
                    kwargs["output_dir"] = str(output_dir)
                stdout = io.StringIO()
                with transaction.atomic():
                    call_command(command, stdout=stdout, **kwargs)
                results.append(self._import_result(
                    manifest_name, command, stdout.getvalue(), importer_output_dir,
                ))

            if "files" in manifests:
                counts = self._apply_files(batch_dir, manifests["files"]["rows"])
                results.append({
                    "manifest": "files",
                    "command": "file_write_service",
                    "status": "PASS",
                    **counts,
                    "output": "",
                })

            raw = manifests.get("raw_data")
            if raw and raw["rows"]:
                resolved_manifest = output_dir / "raw_data.resolved.tsv"
                self._write_resolved_raw_manifest(resolved_manifest, raw["rows"])
                stdout = io.StringIO()
                with transaction.atomic():
                    call_command(
                        "import_raw_data_manifest",
                        input_path=str(resolved_manifest),
                        stdout=stdout,
                        **common,
                    )
                results.append(self._import_result(
                    "raw_data",
                    "import_raw_data_manifest",
                    stdout.getvalue(),
                    importer_output_dir,
                ))
        return results

    def _apply_files(self, batch_dir, rows):
        counts = {
            "scanned_count": 0,
            "created_count": 0,
            "reused_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "unmapped_count": 0,
            "conflict_count": 0,
            "error_count": 0,
        }
        with transaction.atomic():
            for row in rows:
                counts["scanned_count"] += 1
                path = str(resolve_batch_file(batch_dir, row["file_path"]))
                data_file, created, reused, updated = create_or_get_datafile_from_path(
                    file_path=path,
                    file_name=Path(path).name,
                    file_type=self._resolve_file_type(path),
                    md5=row.get("md5") or None,
                )
                counts["created_count"] += int(created)
                counts["reused_count"] += int(reused)
                counts["updated_count"] += int(updated)
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
                        _, relation_created, relation_reused = create_or_get_file_relation(
                            data_file=data_file,
                            related_type=related_type,
                            related_id=obj.id,
                            related_code=code or "",
                            file_role=row["file_role"],
                        )
                        counts["created_count"] += int(relation_created)
                        counts["reused_count"] += int(relation_reused)
        return counts

    def _import_result(self, manifest, command, output, output_dir):
        values = self._parse_audit_output(output)
        output_path = output_dir / f"{manifest}.txt"
        output_path.write_text(output, encoding="utf-8")
        result = {
            "manifest": manifest,
            "command": command,
            "status": "PASS",
            "scanned_count": self._first_int_value(values, "scanned_count", "total_rows"),
            "created_count": self._first_int_value(
                values, "created_count", "created_assembly", "created_annotation",
            ),
            "reused_count": self._first_int_value(
                values, "reused_count", "reused_assembly", "reused_annotation",
            ),
            "updated_count": self._first_int_value(
                values, "updated_count", "updated_assembly", "updated_annotation",
            ),
            "skipped_count": self._int_value(values, "skipped_count"),
            "unmapped_count": self._int_value(values, "unmapped_count"),
            "conflict_count": self._int_value(values, "conflict_count"),
            "error_count": self._int_value(values, "error_count"),
            "output": str(output_path),
        }
        failure_keys = (
            "skipped_count", "unmapped_count", "conflict_count", "error_count",
        )
        if any(result[key] for key in failure_keys):
            result["status"] = "FAIL"
        if self._int_value(values, "missing_accession", "missing_assembly"):
            result["status"] = "FAIL"
        return result

    @staticmethod
    def _first_int_value(values, *keys):
        for key in keys:
            if key not in values:
                continue
            try:
                return int(values.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _int_value(values, *keys):
        return sum(Command._first_int_value(values, key) for key in keys)

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

    @staticmethod
    def _resolve_file_type(file_path):
        suffixes = [suffix.lstrip(".") for suffix in Path(file_path).suffixes]
        extension = suffixes[-1] if suffixes else ""
        if extension.lower() in COMPRESSION_EXTENSIONS and len(suffixes) > 1:
            extension = f"{suffixes[-2]}.{extension}"
        file_type = FileType.objects.filter(extension__iexact=extension).order_by("id").first()
        if file_type:
            return file_type
        return FileType.objects.create(
            name=extension.upper() if extension else "UNKNOWN",
            extension=extension,
        )

    def _run_post_apply_audits(self, output_dir):
        results = []
        for command, directory_name in AUDIT_SEQUENCE:
            audit_dir = output_dir / directory_name
            audit_dir.mkdir(parents=True, exist_ok=True)
            stdout = io.StringIO()
            try:
                call_command(command, output_dir=str(audit_dir), stdout=stdout)
                values = self._parse_audit_output(stdout.getvalue())
                status, accepted = self._audit_status(command, values)
                message = ""
            except Exception as exc:  # Audits must be reported even if a command crashes.
                status, accepted, message = "ERROR", False, str(exc)
            output = stdout.getvalue()
            (audit_dir / "command_output.txt").write_text(output, encoding="utf-8")
            results.append({
                "command": command,
                "status": status,
                "accepted": accepted,
                "report_dir": str(audit_dir),
                "message": message,
            })
        return results

    @staticmethod
    def _parse_audit_output(output):
        values = {}
        for raw_line in output.splitlines():
            separator = "\t" if "\t" in raw_line else "=" if "=" in raw_line else None
            if separator:
                key, value = raw_line.split(separator, 1)
                values[key.strip()] = value.strip()
        return values

    @staticmethod
    def _audit_status(command, values):
        if command == "audit_file_relations":
            passed = (
                values.get("broken_relation_count") == "0"
                and values.get("duplicate_relation_count") == "0"
            )
            return ("PASS" if passed else "FAIL"), passed
        if command == "validate_new_file_structure":
            passed = values.get("result") == "PASS"
            return ("PASS" if passed else "FAIL"), passed
        status = values.get("status", "ERROR")
        return status, status in {"PASS", "WARN"}

    def _write_reports(
        self, output_dir, batch_dir, config, result, ready, applied, *, dry_run,
        started_at, audit_results=None, import_results=None,
    ):
        audit_results = audit_results or []
        import_results = import_results or []
        if not applied:
            audit_status = "NOT_RUN"
        elif all(item["accepted"] for item in audit_results):
            audit_status = "PASS"
        else:
            audit_status = "FAIL"
        if not applied:
            import_status = "NOT_RUN"
        elif all(item["status"] == "PASS" for item in import_results):
            import_status = "PASS"
        else:
            import_status = "FAIL"
        summary = {
            "batch_id": config["batch_id"],
            "source": config["source"],
            "source_version": config["source_version"],
            "description": config.get("description", ""),
            "code_commit": current_code_commit(),
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "ready_to_import": "YES" if ready else "NO",
            "applied": applied,
            "post_apply_import": import_status,
            "post_apply_audit": audit_status,
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
        checksum_rows = [
            ("batch.yaml", sha256_file(batch_dir / "batch.yaml"), "source", ""),
        ]
        checksum_rows.extend(
            (str(item["path"].relative_to(batch_dir)), sha256_file(item["path"]), "source", "")
            for item in result["manifests"].values()
        )
        resolved_raw = output_dir / "raw_data.resolved.tsv"
        if applied and resolved_raw.is_file():
            checksum_rows.append((
                str(resolved_raw.relative_to(batch_dir)) if resolved_raw.is_relative_to(batch_dir) else str(resolved_raw),
                sha256_file(resolved_raw),
                "derived",
                "metadata/raw_data.tsv",
            ))
        with (output_dir / "batch_manifest_checksums.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["manifest", "sha256", "kind", "derived_from"])
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
        with (output_dir / "batch_audits.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["command", "status", "accepted", "report_dir", "message"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(audit_results)
        with (output_dir / "batch_import_results.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "manifest", "command", "status", "scanned_count", "created_count",
                    "reused_count", "updated_count", "skipped_count", "unmapped_count",
                    "conflict_count", "error_count", "output",
                ],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(import_results)


@contextmanager
def _working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
