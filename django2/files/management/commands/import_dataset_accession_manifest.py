import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, Dataset, DatasetAccession
from files.services.import_log_service import build_import_stats, import_timestamp, write_key_value_report


REQUIRED_COLUMNS = {"accession", "dataset_code"}
VALID_RELATION_ROLES = {choice[0] for choice in DatasetAccession.RELATION_ROLE_CHOICES}


def _clean(value):
    return (value or "").strip()


class Command(BaseCommand):
    help = "Import Dataset-to-Accession ownership links from a TSV manifest."

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

        counts = {"scanned": 0, "created": 0, "reused": 0, "skipped": 0}
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
                for key in ("created", "reused", "skipped"):
                    counts[key] += int(result[key])
                unmapped.extend(result["unmapped"])

        timestamp = import_timestamp()
        stats = build_import_stats(
            command="import_dataset_accession_manifest",
            input_path=input_path,
            dry_run=dry_run,
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            scanned_count=counts["scanned"],
            created_count=counts["created"],
            reused_count=counts["reused"],
            skipped_count=counts["skipped"],
            unmapped_count=len(unmapped),
            extra={
                "created_dataset_accession_count": counts["created"],
                "reused_dataset_accession_count": counts["reused"],
            },
        )
        log_path = f"import_dataset_accession_manifest_log_{timestamp}.txt"
        unmapped_path = f"import_dataset_accession_manifest_unmapped_{timestamp}.tsv"
        write_key_value_report(log_path, stats)
        self.write_unmapped(unmapped_path, unmapped)
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

    def import_row(self, row, dry_run, line_number):
        accession_code = _clean(row.get("accession"))
        dataset_code = _clean(row.get("dataset_code"))
        relation_role = _clean(row.get("relation_role")) or "primary"
        source = _clean(row.get("source")) or _clean(row.get("project_code")) or None

        if not accession_code or not dataset_code:
            return self.skipped(line_number, accession_code, dataset_code, "missing accession or dataset_code")
        if relation_role not in VALID_RELATION_ROLES:
            return self.skipped(line_number, accession_code, dataset_code, f"invalid relation_role: {relation_role}")

        accession = Accession.objects.filter(accession=accession_code).first()
        if accession is None:
            return self.skipped(line_number, accession_code, dataset_code, f"accession not found: {accession_code}")
        dataset = Dataset.objects.filter(dataset_code=dataset_code).first()
        if dataset is None:
            return self.skipped(line_number, accession_code, dataset_code, f"dataset not found: {dataset_code}")

        if DatasetAccession.objects.filter(dataset=dataset, accession=accession).exists():
            return self.result(reused=True)
        if not dry_run:
            DatasetAccession.objects.create(
                dataset=dataset,
                accession=accession,
                relation_role=relation_role,
                source=source,
            )
        return self.result(created=True)

    @staticmethod
    def result(created=False, reused=False):
        return {"created": created, "reused": reused, "skipped": False, "unmapped": []}

    @staticmethod
    def skipped(line_number, accession, dataset_code, reason):
        return {
            "created": False,
            "reused": False,
            "skipped": True,
            "unmapped": [{
                "line_number": line_number,
                "accession": accession,
                "dataset_code": dataset_code,
                "reason": reason,
            }],
        }

    @staticmethod
    def write_unmapped(path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["line_number", "accession", "dataset_code", "reason"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)
