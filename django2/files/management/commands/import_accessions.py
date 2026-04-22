import os

from django.conf import settings
from django.core.management.base import BaseCommand

from files.models import Accession


class Command(BaseCommand):
    help = "Import accession data from supplymentary_data.txt into database"

    @staticmethod
    def normalize_header(value):
        return (
            str(value or "")
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
        )

    @staticmethod
    def parse_float(value):
        if not value or value == "-":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def handle(self, *args, **options):
        supplementary_file = os.path.join(
            settings.MANUAL_FILES_DIR,
            "supplymentary_data.txt",
        )

        if not os.path.exists(supplementary_file):
            self.stdout.write(
                self.style.ERROR(f"File not found: {supplementary_file}")
            )
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with open(supplementary_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            self.stdout.write(self.style.WARNING("The file is empty."))
            return

        header_parts = [part.strip() for part in lines[0].strip().split("\t")]
        normalized_headers = [self.normalize_header(part) for part in header_parts]
        header_map = {header: index for index, header in enumerate(normalized_headers)}
        has_header = "accession" in header_map

        data_lines = lines[1:] if has_header else lines
        start_line_number = 2 if has_header else 1

        def get_value(parts, header_key, fallback_index=None):
            if has_header and header_key in header_map:
                index = header_map[header_key]
                return parts[index].strip() if index < len(parts) else ""
            if fallback_index is not None and fallback_index < len(parts):
                return parts[fallback_index].strip()
            return ""

        for line_number, raw_line in enumerate(data_lines, start=start_line_number):
            line = raw_line.strip()

            if not line:
                skipped_count += 1
                continue

            parts = line.split("\t")

            if len(parts) < 1:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Line {line_number} skipped: invalid format"
                    )
                )
                continue

            accession_code = get_value(parts, "accession", 0)
            genetic_stock_id = get_value(parts, "geneticstockid")
            sub_population = get_value(parts, "subpopulation", 1)
            seq_data = get_value(parts, "seqdata", 2)

            # New format:
            # Accession | SubPopulation | SeqData | Country | Region | Longitude | Latitude
            # Old format:
            # Accession | SubPopulation | SeqData | Longitude | Latitude
            country = get_value(parts, "country", 3 if len(parts) >= 7 else None)
            region = get_value(parts, "region", 4 if len(parts) >= 7 else None)
            longitude_raw = get_value(parts, "longitude", 5 if len(parts) >= 7 else 3)
            latitude_raw = get_value(parts, "latitude", 6 if len(parts) >= 7 else 4)

            if not accession_code:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Line {line_number} skipped: accession is empty"
                    )
                )
                continue

            longitude = self.parse_float(longitude_raw)
            latitude = self.parse_float(latitude_raw)

            defaults = {
                "genetic_stock_id": genetic_stock_id or None,
                "sub_population": sub_population or None,
                "seq_data": seq_data or None,
                "country": country or None,
                "region": region or None,
                "longitude": longitude,
                "latitude": latitude,
            }

            obj, created = Accession.objects.update_or_create(
                accession=accession_code,
                defaults=defaults,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completed. Created: {created_count}, "
                f"Updated: {updated_count}, Skipped: {skipped_count}"
            )
        )
