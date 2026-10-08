import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Assembly
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata
from files.services.import_log_service import (
    add_provenance_arguments,
    build_import_stats,
    provenance_options,
    write_key_value_report,
)


class Command(BaseCommand):
    help = "Import Assembly records from an assembly manifest TSV."

    required_columns = {
        "assembly_code", "accession", "assembly_name", "species_code",
        "assembly_level", "reference", "source_database", "external_project",
        "file_name", "file_type", "description",
    }

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Assembly manifest TSV path.")
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
            "created_assembly": 0, "updated_assembly": 0, "reused_assembly": 0,
            "duplicate_assembly": 0, "conflict_count": 0, "invalid_metadata": 0,
        }

        with transaction.atomic():
            for line_number, row in enumerate(rows, start=2):
                assembly_code = row["assembly_code"].strip()
                accession_code = row["accession"].strip()
                if not assembly_code or not accession_code:
                    errors.append(self._error(line_number, assembly_code, accession_code, "assembly_code or accession is empty"))
                    continue

                accession = Accession.objects.filter(accession=accession_code).first()
                if not accession:
                    stats["missing_accession"] += 1
                    errors.append(self._error(line_number, assembly_code, accession_code, "accession not found"))
                    continue
                stats["matched_accession"] += 1

                try:
                    metadata_values = self._metadata_values(row)
                except ValueError as exc:
                    stats["invalid_metadata"] += 1
                    errors.append(self._error(line_number, assembly_code, accession_code, str(exc)))
                    continue

                assembly = Assembly.objects.filter(assembly_code=assembly_code).first()
                if assembly:
                    stats["duplicate_assembly"] += 1
                    if assembly.accession_id != accession.id:
                        stats["conflict_count"] += 1
                        errors.append(self._error(
                            line_number,
                            assembly_code,
                            accession_code,
                            "identity conflict: assembly_code belongs to another accession",
                        ))
                        continue

                    updates, conflicts = plan_fill_blank_metadata(
                        assembly,
                        metadata_values,
                    )
                    if conflicts:
                        stats["conflict_count"] += len(conflicts)
                        errors.append(self._error(
                            line_number,
                            assembly_code,
                            accession_code,
                            self._conflict_reason(conflicts),
                        ))
                    if updates:
                        stats["updated_assembly"] += 1
                        if not options["dry_run"]:
                            for field, value in updates.items():
                                setattr(assembly, field, value)
                            assembly.save(update_fields=[*updates, "updated_at"])
                    else:
                        stats["reused_assembly"] += 1
                    continue

                if not options["dry_run"]:
                    Assembly.objects.create(
                        assembly_code=assembly_code,
                        **self._defaults(row, accession, metadata_values),
                    )
                    stats["created_assembly"] += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        report_stats = build_import_stats(
            command="import_assembly_manifest",
            input_path=str(manifest_path),
            dry_run=options["dry_run"],
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            scanned_count=stats["total_rows"],
            created_count=stats["created_assembly"],
            reused_count=stats["reused_assembly"],
            updated_count=stats["updated_assembly"],
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

    @classmethod
    def _defaults(cls, row, accession, metadata_values=None):
        metadata_values = metadata_values or cls._metadata_values(row)
        return {
            "accession": accession,
            **{
                **metadata_values,
                "name": metadata_values["name"] or row["assembly_code"],
            },
        }

    @classmethod
    def _metadata_values(cls, row):
        assembly_name = row["assembly_name"]
        assembly_accession = row.get("assembly_accession", "")
        return {
            "name": assembly_name or None,
            "assembly_name": assembly_name or None,
            "display_name": assembly_name or None,
            "assembly_accession": assembly_accession or None,
            "standard_id": assembly_accession or None,
            "species_code": row.get("species_code") or None,
            "assembly_level": row.get("assembly_level") or None,
            "biosample_accession": row.get("biosample_accession") or None,
            "assembly_type": row.get("assembly_type") or None,
            "assembly_method": row.get("assembly_method") or None,
            "sequencing_technology": row.get("sequencing_technology") or None,
            "genome_size": cls._optional_nonnegative_integer(row, "genome_size"),
            "chromosome_count": cls._optional_nonnegative_integer(row, "chromosome_count"),
            "contig_count": cls._optional_nonnegative_integer(row, "contig_count"),
            "n50": cls._optional_nonnegative_integer(row, "n50"),
            "gc_content": cls._optional_percentage(row, "gc_content"),
            "reference": row.get("reference") or None,
            "source_database": row.get("source_database") or None,
            "external_project": row.get("external_project") or None,
            "bio_project": row.get("external_project") or None,
            "file_name": row.get("file_name") or None,
            "file_type": row.get("file_type") or None,
            "description": row.get("description") or None,
        }

    @staticmethod
    def _optional_nonnegative_integer(row, field):
        raw_value = row.get(field, "")
        if raw_value == "":
            return None
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"invalid {field}: expected a non-negative integer")
        if value < 0:
            raise ValueError(f"invalid {field}: expected a non-negative integer")
        return value

    @staticmethod
    def _optional_percentage(row, field):
        raw_value = row.get(field, "")
        if raw_value == "":
            return None
        try:
            value = Decimal(raw_value)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"invalid {field}: expected a percentage from 0 to 100")
        if not value.is_finite() or value < 0 or value > 100:
            raise ValueError(f"invalid {field}: expected a percentage from 0 to 100")
        if value.as_tuple().exponent < -3:
            raise ValueError(f"invalid {field}: expected at most 3 decimal places")
        return value

    @staticmethod
    def _conflict_reason(conflicts):
        fields = ", ".join(item["field"] for item in conflicts)
        return f"metadata conflict (preserved existing values): {fields}"

    @staticmethod
    def _error(line_number, assembly_code, accession, reason):
        return {"line_number": line_number, "assembly_code": assembly_code, "accession": accession, "reason": reason}

    @staticmethod
    def _write_reports(output_dir, timestamp, stats, errors):
        log_path = output_dir / f"import_assembly_manifest_log_{timestamp}.txt"
        error_path = output_dir / f"import_assembly_manifest_errors_{timestamp}.tsv"
        write_key_value_report(log_path, stats)
        with error_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_number", "assembly_code", "accession", "reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(errors)
        return log_path, error_path
