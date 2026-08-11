import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, Species


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

    def handle(self, *args, **options):
        input_path = options["input_path"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        if not os.path.exists(input_path):
            raise CommandError(f"Input file does not exist: {input_path}")

        scanned = 0
        created_count = 0
        reused_count = 0
        updated_count = 0
        skipped_count = 0
        unmapped = []

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"import_accession_manifest_log_{timestamp}.txt"
        unmapped_path = f"import_accession_manifest_unmapped_{timestamp}.tsv"
        stats = {
            "dry_run": dry_run,
            "scanned_count": scanned,
            "created_accession_count": created_count,
            "reused_accession_count": reused_count,
            "updated_accession_count": updated_count,
            "skipped_count": skipped_count,
            "unmapped_count": len(unmapped),
        }
        self.write_reports(log_path, unmapped_path, stats, unmapped)

        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(f"log={log_path}")
        self.stdout.write(f"unmapped={unmapped_path}")

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

        update_fields = []
        for field, value in defaults.items():
            current = getattr(accession, field)
            # Preserve existing curated values; fill only blank metadata.
            if field == "species":
                if accession.species_id is None and value is not None:
                    accession.species = value
                    update_fields.append("species")
            elif current in (None, "") and value not in (None, ""):
                setattr(accession, field, value)
                update_fields.append(field)

        if update_fields:
            if not dry_run:
                update_fields.append("updated_at")
                accession.save(update_fields=update_fields)
            return {
                "created": False,
                "reused": False,
                "updated": True,
                "skipped": False,
                "unmapped": [],
            }

        return {
            "created": False,
            "reused": True,
            "updated": False,
            "skipped": False,
            "unmapped": [],
        }

    def write_reports(self, log_path, unmapped_path, stats, unmapped):
        with open(log_path, "w", encoding="utf-8") as handle:
            for key, value in stats.items():
                handle.write(f"{key}: {value}\n")

        with open(unmapped_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["line_number", "accession", "species_code", "reason"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(unmapped)
