import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, Species
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata
from files.services.import_log_service import (
    build_import_stats,
    add_provenance_arguments,
    import_timestamp,
    provenance_options,
    write_key_value_report,
)


REQUIRED_COLUMNS = {"accession", "species_code"}


def _clean(value):
    return (value or "").strip()


def _float_or_none(value):
    value = _clean(value)
    if not value or value == "-":
        return None
    try:
        return float(value)
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Import accession metadata from a TSV manifest."

    def add_arguments(self, parser):
        parser.add_argument("--input", dest="input_path", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)
        add_provenance_arguments(parser)

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        started_at = datetime.now().isoformat(timespec="seconds")

        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")

        scanned = 0
        created_count = 0
        reused_count = 0
        updated_count = 0
        skipped_count = 0
        unmapped = []
        conflicts = []

        with open(input_path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing_columns:
                raise CommandError(
                    f"Missing required columns: {', '.join(sorted(missing_columns))}"
                )

            for line_number, row in enumerate(reader, start=2):
                if limit is not None and scanned >= limit:
                    break
                scanned += 1
                result = self.import_row(row, dry_run=dry_run, line_number=line_number)
                created_count += int(result["created"])
                reused_count += int(result["reused"])
                updated_count += int(result["updated"])
                skipped_count += int(result["skipped"])
                unmapped.extend(result["unmapped"])
                conflicts.extend(result.get("conflicts", []))

        finished_at = datetime.now().isoformat(timespec="seconds")
        timestamp = import_timestamp()
        log_path = f"import_accession_manifest_log_{timestamp}.txt"
        unmapped_path = f"import_accession_manifest_unmapped_{timestamp}.tsv"
        conflict_path = f"import_accession_manifest_conflicts_{timestamp}.tsv"
        stats = build_import_stats(
            command="import_accession_manifest",
            input_path=input_path,
            dry_run=dry_run,
            started_at=started_at,
            finished_at=finished_at,
            scanned_count=scanned,
            created_count=created_count,
            reused_count=reused_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            unmapped_count=len(unmapped),
            **provenance_options(options),
            extra={
                "created_accession_count": created_count,
                "reused_accession_count": reused_count,
                "updated_accession_count": updated_count,
                "conflict_count": len(conflicts),
            },
        )
        self.write_reports(log_path, unmapped_path, stats, unmapped)
        self.write_conflicts(conflict_path, conflicts)

        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")
        self.stdout.write(f"conflicts={conflict_path}")

    def import_row(self, row, dry_run=False, line_number=None):
        accession_code = _clean(row.get("accession"))
        species_code = _clean(row.get("species_code"))
        unmapped = []

        if not accession_code:
            return {
                "created": False,
                "reused": False,
                "updated": False,
                "skipped": True,
                "unmapped": [
                    {
                        "line_number": line_number,
                        "accession": accession_code,
                        "species_code": species_code,
                        "reason": "missing accession",
                    }
                ],
            }

        species = None
        if species_code:
            species = Species.objects.filter(species_code=species_code).first()
            if not species:
                unmapped.append(
                    {
                        "line_number": line_number,
                        "accession": accession_code,
                        "species_code": species_code,
                        "reason": f"species not found: {species_code}",
                    }
                )
        else:
            unmapped.append(
                {
                    "line_number": line_number,
                    "accession": accession_code,
                    "species_code": species_code,
                    "reason": "missing species_code",
                }
            )

        if unmapped:
            return {
                "created": False,
                "reused": False,
                "updated": False,
                "skipped": True,
                "unmapped": unmapped,
            }

        accession = Accession.objects.filter(accession=accession_code).first()
        defaults = {
            "species": species,
            "sub_population": _clean(row.get("sub_population")) or None,
            "country": _clean(row.get("country")) or None,
            "region": _clean(row.get("region")) or None,
            "longitude": _float_or_none(row.get("longitude")),
            "latitude": _float_or_none(row.get("latitude")),
            "description": _clean(row.get("description")) or None,
        }

        if not accession:
            if not dry_run:
                Accession.objects.create(accession=accession_code, **defaults)
            return {
                "created": True,
                "reused": False,
                "updated": False,
                "skipped": False,
                "unmapped": [],
            }

        updates, metadata_conflicts = plan_fill_blank_metadata(accession, defaults)
        conflicts = self._conflict_rows(
            line_number, accession_code, metadata_conflicts,
        )

        if updates:
            if not dry_run:
                for field, value in updates.items():
                    setattr(accession, field, value)
                accession.save(update_fields=[*updates, "updated_at"])
            return {
                "created": False,
                "reused": False,
                "updated": True,
                "skipped": False,
                "unmapped": [],
                "conflicts": conflicts,
            }

        return {
            "created": False,
            "reused": True,
            "updated": False,
            "skipped": False,
            "unmapped": [],
            "conflicts": conflicts,
        }

    @staticmethod
    def _conflict_rows(line_number, accession_code, conflicts):
        return [
            {
                "line_number": line_number,
                "identity": accession_code,
                "field": item["field"],
                "existing": item["existing"],
                "incoming": item["incoming"],
                "reason": "metadata conflict; preserved existing value",
            }
            for item in conflicts
        ]

    @staticmethod
    def write_conflicts(path, conflicts):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["line_number", "identity", "field", "existing", "incoming", "reason"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(conflicts)

    def write_reports(self, log_path, unmapped_path, stats, unmapped):
        write_key_value_report(log_path, stats)

        with open(unmapped_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["line_number", "accession", "species_code", "reason"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(unmapped)
