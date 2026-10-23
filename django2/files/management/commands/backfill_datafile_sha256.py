import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.management.external_data_command import (
    add_safe_mode_arguments,
    is_apply_mode,
    make_report_path,
    write_tsv,
)
from files.models import DataFile
from files.services.datafile_access_service import resolve_protected_datafile_path


FIELDS = (
    "data_file_id", "file_code", "file_path", "status", "reason", "sha256",
    "recorded_size", "actual_size",
)


class Command(BaseCommand):
    help = "Safely calculate missing DataFile SHA-256 values; default mode is dry-run."

    def add_arguments(self, parser):
        add_safe_mode_arguments(parser)
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--data-file-id", action="append", type=int, dest="data_file_ids")
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        if options["batch_size"] <= 0:
            raise CommandError("--batch-size must be greater than zero")
        apply_mode = is_apply_mode(options)
        queryset = DataFile.objects.filter(is_current=True).order_by("id")
        if options["data_file_ids"]:
            queryset = queryset.filter(id__in=options["data_file_ids"])

        rows = []
        hashed = applied = skipped = failed = 0
        for data_file in queryset.iterator(chunk_size=options["batch_size"]):
            base = {
                "data_file_id": data_file.id,
                "file_code": data_file.file_code,
                "file_path": data_file.file_path,
                "recorded_size": data_file.file_size if data_file.file_size is not None else "",
            }
            if data_file.content_version:
                skipped += 1
                rows.append({**base, "status": "skipped", "reason": "sha256_already_valid", "sha256": data_file.sha256, "actual_size": ""})
                continue
            location = resolve_protected_datafile_path(data_file)
            if not location.allowed:
                failed += 1
                rows.append({**base, "status": "failed", "reason": location.reason, "sha256": "", "actual_size": ""})
                continue
            path = Path(location.resolved_path)
            try:
                before = path.stat()
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                after = path.stat()
            except OSError as exc:
                failed += 1
                rows.append({
                    **base, "status": "failed", "reason": f"hash_io_error:{exc.__class__.__name__}",
                    "sha256": "", "actual_size": "",
                })
                continue
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                failed += 1
                rows.append({**base, "status": "failed", "reason": "file_changed_during_hash", "sha256": "", "actual_size": after.st_size})
                continue
            hashed += 1
            value = digest.hexdigest()
            status = "ready"
            reason = "dry_run_no_changes"
            if apply_mode:
                with transaction.atomic():
                    locked = DataFile.objects.select_for_update().get(pk=data_file.pk)
                    if locked.content_version:
                        status, reason, value = "skipped", "sha256_added_concurrently", locked.sha256
                        skipped += 1
                    else:
                        try:
                            current = path.stat()
                        except OSError as exc:
                            status, reason, value = "failed", f"save_io_error:{exc.__class__.__name__}", ""
                            failed += 1
                            current = None
                        if current is None:
                            pass
                        elif (before.st_size, before.st_mtime_ns) != (current.st_size, current.st_mtime_ns):
                            status, reason, value = "failed", "file_changed_before_save", ""
                            failed += 1
                        else:
                            locked.sha256 = value
                            locked.save(update_fields=["sha256", "updated_at"])
                            status, reason = "applied", "sha256_saved"
                            applied += 1
            rows.append({**base, "status": status, "reason": reason, "sha256": value, "actual_size": after.st_size})

        report_path = make_report_path(options["output_dir"], "datafile_sha256_backfill")
        write_tsv(report_path, FIELDS, rows)
        self.stdout.write(f"mode\t{'APPLY' if apply_mode else 'DRY_RUN'}")
        self.stdout.write(f"hashed\t{hashed}")
        self.stdout.write(f"applied\t{applied}")
        self.stdout.write(f"skipped\t{skipped}")
        self.stdout.write(f"failed\t{failed}")
        self.stdout.write(f"report\t{report_path}")
