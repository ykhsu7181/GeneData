import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, AccessionExternalMapping
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata
from files.services.import_log_service import (
    add_provenance_arguments,
    build_import_stats,
    import_timestamp,
    provenance_options,
    write_key_value_report,
)


REQUIRED_COLUMNS = {"accession", "ena_study"}


def _clean(value):
    return (value or "").strip()


def _split_values(value):
    return [item.strip() for item in _clean(value).split(";") if item.strip()]


class Command(BaseCommand):
    help = "Import accession external-study mappings from a TSV manifest."

    def add_arguments(self, parser):
        parser.add_argument("--input", dest="input_path", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)
        add_provenance_arguments(parser)

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")
        counts = {"scanned": 0, "created": 0, "reused": 0, "updated": 0, "skipped": 0}
        unmapped = []
        conflicts = []
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
                conflicts.extend(result.get("conflicts", []))
        timestamp = import_timestamp()
        stats = build_import_stats(
            command="import_accession_external_mapping_manifest", input_path=input_path, dry_run=dry_run,
            started_at=started_at, finished_at=datetime.now().isoformat(timespec="seconds"),
            scanned_count=counts["scanned"], created_count=counts["created"], reused_count=counts["reused"],
            updated_count=counts["updated"], skipped_count=counts["skipped"], unmapped_count=len(unmapped),
            **provenance_options(options),
            extra={"conflict_count": len(conflicts)},
        )
        log_path = f"import_accession_external_mapping_log_{timestamp}.txt"
        unmapped_path = f"import_accession_external_mapping_unmapped_{timestamp}.tsv"
        conflict_path = f"import_accession_external_mapping_conflicts_{timestamp}.tsv"
        write_key_value_report(log_path, stats)
        self.write_unmapped(unmapped_path, unmapped)
        self.write_conflicts(conflict_path, conflicts)
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")
        self.stdout.write(f"conflicts={conflict_path}")

    def import_row(self, row, dry_run, line_number):
        accession_code = _clean(row.get("accession"))
        study = _clean(row.get("ena_study") or row.get("bioproject"))
        if not accession_code or not study:
            return self.skipped(line_number, accession_code, study, "missing accession or external study")
        accession = Accession.objects.filter(accession=accession_code).first()
        if not accession:
            return self.skipped(line_number, accession_code, study, f"accession not found: {accession_code}")
        shared_defaults = {
            "external_database": _clean(row.get("external_database")) or "ENA",
            "biosample_accession": _clean(row.get("biosample")) or None,
            "experiment_accession": _clean(row.get("experiment")) or None,
            "run_accession": _clean(row.get("run")) or None,
            "scientific_name": _clean(row.get("scientific_name")) or None,
            "library_strategy": _clean(row.get("library_strategy")) or None,
            "instrument_platform": _clean(row.get("instrument_platform")) or None,
            "instrument_model": _clean(row.get("instrument_model")) or None,
        }
        urls = _split_values(row.get("fastq_ftp") or row.get("submitted_ftp"))
        checksums = _split_values(row.get("fastq_md5") or row.get("submitted_md5"))
        entry_count = max(len(urls), len(checksums), 1)
        totals = {"created": 0, "reused": 0, "updated": 0}
        conflicts = []

        for index in range(entry_count):
            defaults = {
                **shared_defaults,
                "fastq_url": urls[index] if index < len(urls) else (urls[0] if len(urls) == 1 else None),
                "fastq_md5": checksums[index] if index < len(checksums) else (checksums[0] if len(checksums) == 1 else None),
            }
            result, metadata_conflicts = self.import_mapping(accession, study, defaults, dry_run)
            totals[result] += 1
            conflicts.extend(self.conflict_rows(
                line_number,
                f"{accession_code}:{study}:{index + 1}",
                metadata_conflicts,
            ))
        return {**totals, "skipped": False, "unmapped": [], "conflicts": conflicts}

    @staticmethod
    def import_mapping(accession, study, defaults, dry_run):
        mapping = AccessionExternalMapping.objects.filter(
            accession=accession,
            external_study_accession=study,
            biosample_accession=defaults["biosample_accession"],
            experiment_accession=defaults["experiment_accession"],
            run_accession=defaults["run_accession"],
            fastq_url=defaults["fastq_url"],
            fastq_md5=defaults["fastq_md5"],
        ).first()
        if not mapping:
            if not dry_run:
                AccessionExternalMapping.objects.create(accession=accession, external_study_accession=study, **defaults)
            return "created", []
        updates, conflicts = plan_fill_blank_metadata(mapping, defaults)
        if updates:
            if not dry_run:
                for field, value in updates.items():
                    setattr(mapping, field, value)
                mapping.save(update_fields=[*updates, "updated_at"])
            return "updated", conflicts
        return "reused", conflicts

    @staticmethod
    def conflict_rows(line_number, identity, conflicts):
        return [
            {
                "line_number": line_number,
                "identity": identity,
                "field": item["field"],
                "existing": item["existing"],
                "incoming": item["incoming"],
                "reason": "metadata conflict; preserved existing value",
            }
            for item in conflicts
        ]

    @staticmethod
    def result(created=False, reused=False, updated=False):
        return {"created": created, "reused": reused, "updated": updated, "skipped": False, "unmapped": []}

    @staticmethod
    def skipped(line_number, accession, study, reason):
        return {
            "created": False, "reused": False, "updated": False, "skipped": True,
            "unmapped": [{"line_number": line_number, "accession": accession, "external_study_accession": study, "reason": reason}],
        }

    @staticmethod
    def write_unmapped(path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_number", "accession", "external_study_accession", "reason"], delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def write_conflicts(path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["line_number", "identity", "field", "existing", "incoming", "reason"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)
