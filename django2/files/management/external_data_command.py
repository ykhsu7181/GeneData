"""Shared helpers for external-data operational management commands."""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone


def add_safe_mode_arguments(parser):
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")


def is_apply_mode(options):
    return bool(options.get("apply"))


def make_report_path(output_dir, prefix):
    directory = Path(output_dir or settings.BASE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S_%f")
    return directory / f"{prefix}_{timestamp}.tsv"


def write_tsv(path, fieldnames, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv(path, required_fields):
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise CommandError(f"Manifest does not exist: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = set(required_fields) - set(reader.fieldnames or [])
        if missing:
            raise CommandError(f"Manifest is missing columns: {', '.join(sorted(missing))}")
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
