import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, Dataset, Project
from files.services.import_log_service import build_import_stats, import_timestamp, write_key_value_report


REQUIRED_COLUMNS = {"accession", "project_code", "dataset_code", "dataset_type"}
VALID_DATASET_TYPES = {choice[0] for choice in Dataset.DATASET_TYPE_CHOICES}


def _clean(value):
    return (value or "").strip()


class Command(BaseCommand):
    help = "Import Dataset and Project metadata from a TSV manifest."

    def add_arguments(self, parser):
        parser.add_argument("--input", dest="input_path", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")

        counts = {"scanned": 0, "created": 0, "reused": 0, "updated": 0, "skipped": 0}
        unmapped = []
        started_at = datetime.now().isoformat(timespec="seconds")
        with open(input_path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing_columns:
                raise CommandError(f"Missing required columns: {', '.join(sorted(missing_columns))}")
            for line_number, row in enumerate(reader, start=2):
                if limit is not None and counts["scanned"] >= limit:
                    break
                counts["scanned"] += 1
                result = self.import_row(row, dry_run=dry_run, line_number=line_number)
                for key in ("created", "reused", "updated", "skipped"):
                    counts[key] += int(result[key])
                unmapped.extend(result["unmapped"])

        timestamp = import_timestamp()
        stats = build_import_stats(
            command="import_dataset_manifest",
            input_path=input_path,
            dry_run=dry_run,
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            scanned_count=counts["scanned"],
            created_count=counts["created"],
            reused_count=counts["reused"],
            updated_count=counts["updated"],
            skipped_count=counts["skipped"],
            unmapped_count=len(unmapped),
        )
        log_path = f"import_dataset_manifest_log_{timestamp}.txt"
        unmapped_path = f"import_dataset_manifest_unmapped_{timestamp}.tsv"
        write_key_value_report(log_path, stats)
        self.write_unmapped(unmapped_path, unmapped)
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

    def import_row(self, row, dry_run, line_number):
        accession_code = _clean(row.get("accession"))
        dataset_code = _clean(row.get("dataset_code"))
        dataset_type = _clean(row.get("dataset_type"))
        project_code = _clean(row.get("project_code"))
        if not accession_code or not dataset_code or not project_code:
            return self.skipped(line_number, accession_code, dataset_code, "missing accession, project_code, or dataset_code")
        if dataset_type not in VALID_DATASET_TYPES:
            return self.skipped(line_number, accession_code, dataset_code, f"invalid dataset_type: {dataset_type}")
        accession = Accession.objects.select_related("species").filter(accession=accession_code).first()
        if not accession:
            return self.skipped(line_number, accession_code, dataset_code, f"accession not found: {accession_code}")

        project_defaults = {
            "project_name": _clean(row.get("project_name")) or None,
            "description": _clean(row.get("description")) or None,
        }
        project = Project.objects.filter(project_code=project_code).first()
        if not project:
            if not dry_run:
                project = Project.objects.create(project_code=project_code, **project_defaults)
        else:
            update_fields = [field for field, value in project_defaults.items() if getattr(project, field) in (None, "") and value]
            if update_fields and not dry_run:
                for field in update_fields:
                    setattr(project, field, project_defaults[field])
                project.save(update_fields=update_fields + ["updated_at"])

        defaults = {
            "dataset_name": _clean(row.get("dataset_name")) or dataset_code,
            "dataset_type": dataset_type,
            "bioproject_accession": _clean(row.get("ncbi_bioproject")) or None,
            "species": accession.species,
            "project": project,
            "description": _clean(row.get("description")) or None,
        }
        dataset = Dataset.objects.filter(dataset_code=dataset_code).first()
        if not dataset:
            if not dry_run:
                Dataset.objects.create(dataset_code=dataset_code, **defaults)
            return self.result(created=True)

        update_fields = []
        for field, value in defaults.items():
            current = getattr(dataset, field)
            if field in {"species", "project"}:
                if current is None and value is not None:
                    setattr(dataset, field, value)
                    update_fields.append(field)
            elif current in (None, "") and value not in (None, ""):
                setattr(dataset, field, value)
                update_fields.append(field)
        if update_fields:
            if not dry_run:
                dataset.save(update_fields=update_fields + ["updated_at"])
            return self.result(updated=True)
        return self.result(reused=True)

    @staticmethod
    def result(created=False, reused=False, updated=False):
        return {"created": created, "reused": reused, "updated": updated, "skipped": False, "unmapped": []}

    @staticmethod
    def skipped(line_number, accession, dataset_code, reason):
        return {
            "created": False, "reused": False, "updated": False, "skipped": True,
            "unmapped": [{"line_number": line_number, "accession": accession, "dataset_code": dataset_code, "reason": reason}],
        }

    @staticmethod
    def write_unmapped(path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_number", "accession", "dataset_code", "reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
