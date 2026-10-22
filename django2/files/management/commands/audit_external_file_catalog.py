import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.models import DataFile
from files.services.external_file_catalog_service import normalize_file_name


DETAIL_FIELDS = (
    "line_number",
    "file_name",
    "status",
    "match_count",
    "file_codes",
    "publication_statuses",
)


class Command(BaseCommand):
    help = "Audit an authoritative file-name list against registered DataFiles (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--file-list", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        source = Path(options["file_list"]).expanduser().resolve()
        output = Path(options["output"]).expanduser().resolve()
        if not source.is_file():
            raise CommandError(f"File list does not exist: {source}")
        if output.exists() and not output.is_dir():
            raise CommandError(f"Output is not a directory: {output}")
        output.mkdir(parents=True, exist_ok=True)

        names = _read_names(source)
        registered = defaultdict(list)
        for data_file in DataFile.objects.order_by("file_code", "id"):
            registered[normalize_file_name(data_file.file_name)].append(data_file)

        input_counts = Counter(normalize_file_name(item[1]) for item in names)
        counters = Counter()
        rows = []
        for line_number, file_name in names:
            normalized = normalize_file_name(file_name)
            if not normalized or "/" in file_name or "\\" in file_name:
                status = "INVALID_NAME"
                matches = []
            else:
                matches = registered.get(normalized, [])
                if input_counts[normalized] > 1:
                    status = "DUPLICATE_INPUT_NAME"
                elif not matches:
                    status = "UNREGISTERED"
                elif len(matches) == 1:
                    status = "UNIQUE_REGISTERED"
                else:
                    status = "MULTIPLE_REGISTERED"
            counters[status] += 1
            rows.append({
                "line_number": line_number,
                "file_name": file_name,
                "status": status,
                "match_count": len(matches),
                "file_codes": ",".join(item.file_code for item in matches),
                "publication_statuses": ",".join(
                    sorted({item.publication_status for item in matches})
                ),
            })

        detail_path = output / "external_file_catalog_coverage.tsv"
        with detail_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DETAIL_FIELDS, dialect="excel-tab")
            writer.writeheader()
            writer.writerows(rows)

        summary_path = output / "external_file_catalog_summary.tsv"
        summary_rows = [
            ("TOTAL_INPUT_NAMES", len(names)),
            ("UNIQUE_NORMALIZED_INPUT_NAMES", len(input_counts)),
            ("REGISTERED_DATAFILES", sum(len(items) for items in registered.values())),
        ]
        summary_rows.extend(sorted(counters.items()))
        with summary_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, dialect="excel-tab")
            writer.writerow(("metric", "count"))
            writer.writerows(summary_rows)

        for metric, count in summary_rows:
            self.stdout.write(f"{metric}\t{count}")
        self.stdout.write(f"details\t{detail_path}")
        self.stdout.write(f"summary\t{summary_path}")


def _read_names(source):
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CommandError("File list must be UTF-8 or UTF-8 with BOM.") from exc
    return [
        (line_number, value.strip())
        for line_number, value in enumerate(text.splitlines(), start=1)
        if value.strip()
    ]
