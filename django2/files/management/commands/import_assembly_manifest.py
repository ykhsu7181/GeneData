import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.models import Accession, Assembly


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

    def handle(self, *args, **options):
        manifest_path = Path(options["file"])
        if not manifest_path.is_file():
            raise CommandError(f"Manifest file not found: {manifest_path}")

        rows = self._load_rows(manifest_path)
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        errors = []
        stats = {
            "total_rows": len(rows), "matched_accession": 0, "missing_accession": 0,
            "created_assembly": 0, "updated_assembly": 0, "duplicate_assembly": 0,
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

                if Assembly.objects.filter(assembly_code=assembly_code).exists():
                    stats["duplicate_assembly"] += 1
                if options["dry_run"]:
                    continue

                defaults = self._defaults(row, accession)
                _, created = Assembly.objects.update_or_create(
                    assembly_code=assembly_code,
                    defaults=defaults,
                )
                stats["created_assembly" if created else "updated_assembly"] += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        log_path, error_path = self._write_reports(output_dir, timestamp, options["dry_run"], stats, errors)
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
    def _defaults(row, accession):
        assembly_name = row["assembly_name"]
        assembly_accession = row.get("assembly_accession", "")
        return {
            "accession": accession,
            "name": assembly_name or row["assembly_code"],
            "assembly_name": assembly_name or None,
            "display_name": assembly_name or None,
            "assembly_accession": assembly_accession or None,
            "standard_id": assembly_accession or None,
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

    @staticmethod
    def _error(line_number, assembly_code, accession, reason):
        return {"line_number": line_number, "assembly_code": assembly_code, "accession": accession, "reason": reason}

    @staticmethod
    def _write_reports(output_dir, timestamp, dry_run, stats, errors):
        log_path = output_dir / f"import_assembly_manifest_log_{timestamp}.txt"
        error_path = output_dir / f"import_assembly_manifest_errors_{timestamp}.tsv"
        log_path.write_text(
            "\n".join([f"dry_run: {dry_run}"] + [f"{key}: {value}" for key, value in stats.items()]) + "\n",
            encoding="utf-8",
        )
        with error_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_number", "assembly_code", "accession", "reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(errors)
        return log_path, error_path
