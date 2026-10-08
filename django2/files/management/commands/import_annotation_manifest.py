import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Annotation, Assembly
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata
from files.services.import_log_service import (
    add_provenance_arguments,
    build_import_stats,
    provenance_options,
    write_key_value_report,
)


class Command(BaseCommand):
    help = "Import Annotation records from an annotation manifest TSV."

    required_columns = {
        "annotation_code", "accession", "assembly_code", "annotation_name",
        "species_code", "source_database", "external_project", "file_name",
        "file_type", "description",
    }

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Annotation manifest TSV path.")
        parser.add_argument("--dry-run", action="store_true", help="Validate without writing database records.")
        parser.add_argument("--output-dir", default=".", help="Directory for import logs.")
        add_provenance_arguments(parser)

    def handle(self, *args, **options):
        manifest_path = Path(options["file"])
        if not manifest_path.is_file():
            raise CommandError(f"Manifest file not found: {manifest_path}")

        rows = self._load_rows(manifest_path)
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        errors = []
        started_at = datetime.now().isoformat(timespec="seconds")
        stats = {
            "total_rows": len(rows), "matched_accession": 0, "missing_accession": 0,
            "matched_assembly": 0, "missing_assembly": 0, "created_annotation": 0,
            "updated_annotation": 0, "reused_annotation": 0,
            "duplicate_annotation": 0, "conflict_count": 0,
        }

        with transaction.atomic():
            for line_number, row in enumerate(rows, start=2):
                annotation_code = row["annotation_code"].strip()
                accession_code = row["accession"].strip()
                assembly_code = row["assembly_code"].strip()
                if not annotation_code or not accession_code or not assembly_code:
                    errors.append(self._error(line_number, annotation_code, accession_code, assembly_code, "annotation_code, accession, or assembly_code is empty"))
                    continue

                accession = Accession.objects.filter(accession=accession_code).first()
                if not accession:
                    stats["missing_accession"] += 1
                    errors.append(self._error(line_number, annotation_code, accession_code, assembly_code, "accession not found"))
                    continue
                stats["matched_accession"] += 1

                assembly = Assembly.objects.filter(assembly_code=assembly_code).first()
                if not assembly or assembly.accession_id != accession.id:
                    stats["missing_assembly"] += 1
                    reason = "assembly not found" if not assembly else "assembly does not belong to accession"
                    errors.append(self._error(line_number, annotation_code, accession_code, assembly_code, reason))
                    continue
                stats["matched_assembly"] += 1

                annotation = Annotation.objects.filter(annotation_code=annotation_code).first()
                if annotation:
                    stats["duplicate_annotation"] += 1
                    if annotation.assembly_id != assembly.id:
                        stats["conflict_count"] += 1
                        errors.append(self._error(
                            line_number,
                            annotation_code,
                            accession_code,
                            assembly_code,
                            "identity conflict: annotation_code belongs to another assembly",
                        ))
                        continue

                    updates, conflicts = plan_fill_blank_metadata(
                        annotation,
                        self._metadata_values(row, accession),
                    )
                    if conflicts:
                        stats["conflict_count"] += len(conflicts)
                        errors.append(self._error(
                            line_number,
                            annotation_code,
                            accession_code,
                            assembly_code,
                            self._conflict_reason(conflicts),
                        ))
                    if updates:
                        stats["updated_annotation"] += 1
                        if not options["dry_run"]:
                            for field, value in updates.items():
                                setattr(annotation, field, value)
                            annotation.save(update_fields=[*updates, "updated_at"])
                    else:
                        stats["reused_annotation"] += 1
                    continue

                if not options["dry_run"]:
                    Annotation.objects.create(
                        annotation_code=annotation_code,
                        **self._defaults(row, accession, assembly),
                    )
                    stats["created_annotation"] += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        report_stats = build_import_stats(
            command="import_annotation_manifest",
            input_path=str(manifest_path),
            dry_run=options["dry_run"],
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            scanned_count=stats["total_rows"],
            created_count=stats["created_annotation"],
            reused_count=stats["reused_annotation"],
            updated_count=stats["updated_annotation"],
            error_count=len(errors),
            **provenance_options(options),
            extra=stats,
        )
        log_path, error_path = self._write_reports(output_dir, timestamp, report_stats, errors)
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"dry_run={options['dry_run']}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"errors={error_path}")

    def _load_rows(self, path):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            columns = set(reader.fieldnames or [])
            missing = self.required_columns - columns
            if missing:
                raise CommandError(f"Manifest missing required columns: {', '.join(sorted(missing))}")
            return [{key: (value or "").strip() for key, value in row.items()} for row in reader]

    @staticmethod
    def _defaults(row, accession, assembly):
        annotation_name = row["annotation_name"]
        annotation_version = row.get("annotation_version", "")
        source_database = row.get("source_database", "")
        source_name = row.get("source_name", "") or source_database
        return {
            "accession": accession,
            "assembly": assembly,
            "name": annotation_name or row["annotation_code"],
            "annotation_name": annotation_name or None,
            "display_name": annotation_name or None,
            "standard_id": row["annotation_code"],
            "annotation_version": annotation_version or None,
            "release_version": annotation_version or None,
            "species_code": row.get("species_code") or None,
            "source_database": source_database or None,
            "source_name": source_name or None,
            "external_project": row.get("external_project") or None,
            "file_name": row.get("file_name") or None,
            "file_type": row.get("file_type") or None,
            "description": row.get("description") or None,
        }

    @staticmethod
    def _metadata_values(row, accession):
        annotation_name = row["annotation_name"]
        annotation_version = row.get("annotation_version", "")
        source_database = row.get("source_database", "")
        source_name = row.get("source_name", "") or source_database
        return {
            "accession": accession,
            "name": annotation_name or None,
            "annotation_name": annotation_name or None,
            "display_name": annotation_name or None,
            "standard_id": row["annotation_code"],
            "annotation_version": annotation_version or None,
            "release_version": annotation_version or None,
            "species_code": row.get("species_code") or None,
            "source_database": source_database or None,
            "source_name": source_name or None,
            "external_project": row.get("external_project") or None,
            "file_name": row.get("file_name") or None,
            "file_type": row.get("file_type") or None,
            "description": row.get("description") or None,
        }

    @staticmethod
    def _conflict_reason(conflicts):
        fields = ", ".join(item["field"] for item in conflicts)
        return f"metadata conflict (preserved existing values): {fields}"

    @staticmethod
    def _error(line_number, annotation_code, accession, assembly_code, reason):
        return {"line_number": line_number, "annotation_code": annotation_code, "accession": accession, "assembly_code": assembly_code, "reason": reason}

    @staticmethod
    def _write_reports(output_dir, timestamp, stats, errors):
        log_path = output_dir / f"import_annotation_manifest_log_{timestamp}.txt"
        error_path = output_dir / f"import_annotation_manifest_errors_{timestamp}.tsv"
        write_key_value_report(log_path, stats)
        with error_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_number", "annotation_code", "accession", "assembly_code", "reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(errors)
        return log_path, error_path
