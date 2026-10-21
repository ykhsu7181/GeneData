from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.management.external_data_command import (
    add_safe_mode_arguments,
    is_apply_mode,
    make_report_path,
    read_tsv,
    write_tsv,
)
from files.models import DataFile
from files.services.external_data_operations import inspect_datafile_readiness


FIELDS = (
    "line", "file_code", "requested_access_level", "status", "issues",
    "effective_access_level", "sha256",
)
ALLOWED_LEVELS = {DataFile.ACCESS_LEVEL_PUBLIC, DataFile.ACCESS_LEVEL_INTERNAL}


class Command(BaseCommand):
    help = "Publish manifest-selected DataFiles after fail-closed readiness checks."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--published-by", default=None)
        parser.add_argument("--output-dir", default=None)
        add_safe_mode_arguments(parser)

    def handle(self, *args, **options):
        apply_mode = is_apply_mode(options)
        manifest_rows = read_tsv(options["manifest"], {"file_code", "access_level"})
        if not manifest_rows:
            raise CommandError("Manifest contains no data rows")
        publisher = self._get_publisher(options["published_by"], required=apply_mode)
        seen = set()
        prepared = []
        report_rows = []

        for line_number, manifest_row in enumerate(manifest_rows, start=2):
            file_code = manifest_row["file_code"]
            requested_level = manifest_row["access_level"]
            issues = []
            if not file_code:
                issues.append("file_code_missing")
            elif file_code in seen:
                issues.append("duplicate_file_code")
            seen.add(file_code)
            if requested_level not in ALLOWED_LEVELS:
                issues.append("invalid_access_level")

            data_file = DataFile.objects.filter(file_code=file_code).first() if file_code else None
            if data_file is None:
                issues.append("datafile_not_found")
                readiness = None
            elif requested_level in ALLOWED_LEVELS:
                readiness = inspect_datafile_readiness(data_file, access_level=requested_level)
                issues.extend(readiness.issues)
                if data_file.publication_status == DataFile.PUBLICATION_WITHDRAWN:
                    issues.append("file_withdrawn")
                if readiness.effective_access_level != requested_level:
                    issues.append("requested_access_level_conflicts_with_dataset")
                expected_sha256 = manifest_row.get("sha256", "").lower()
                if expected_sha256 and expected_sha256 != (data_file.sha256 or "").lower():
                    issues.append("sha256_manifest_mismatch")
            else:
                readiness = None

            issues = list(dict.fromkeys(issues))
            status = "blocked" if issues else ("ready" if not apply_mode else "pending")
            report_rows.append({
                "line": line_number,
                "file_code": file_code,
                "requested_access_level": requested_level,
                "status": status,
                "issues": ",".join(issues),
                "effective_access_level": readiness.effective_access_level if readiness else "",
                "sha256": data_file.sha256 if data_file else "",
            })
            if not issues:
                prepared.append((data_file, requested_level, report_rows[-1]))

        report_path = make_report_path(options["output_dir"], "datafile_publication")
        blocked = sum(row["status"] == "blocked" for row in report_rows)
        if apply_mode and not blocked:
            published_at = timezone.now()
            runtime_blocked = False
            with transaction.atomic():
                locked_files = {
                    item.file_code: item
                    for item in DataFile.objects.select_for_update().filter(
                        file_code__in=[item.file_code for item, _, _ in prepared]
                    )
                }
                for original, requested_level, report_row in prepared:
                    data_file = locked_files.get(original.file_code)
                    if data_file is None:
                        report_row["status"] = "blocked"
                        report_row["issues"] = "datafile_disappeared_before_publication"
                        runtime_blocked = True
                        transaction.set_rollback(True)
                        break
                    readiness = inspect_datafile_readiness(data_file, access_level=requested_level)
                    if not readiness.ready or readiness.effective_access_level != requested_level:
                        report_row["status"] = "blocked"
                        report_row["issues"] = "readiness_changed_before_publication"
                        runtime_blocked = True
                        transaction.set_rollback(True)
                        break
                    data_file.access_level = requested_level
                    data_file.publication_status = DataFile.PUBLICATION_RELEASED
                    if data_file.published_at is None:
                        data_file.published_at = published_at
                    if data_file.published_by_id is None:
                        data_file.published_by = publisher
                    data_file.save(update_fields=[
                        "access_level", "publication_status", "published_at", "published_by", "updated_at"
                    ])
                    report_row["status"] = "applied"
            if runtime_blocked:
                for report_row in report_rows:
                    if report_row["status"] == "applied":
                        report_row["status"] = "ready_not_applied"
                blocked = sum(row["status"] == "blocked" for row in report_rows)
        elif apply_mode:
            for report_row in report_rows:
                if report_row["status"] == "pending":
                    report_row["status"] = "ready_not_applied"

        write_tsv(report_path, FIELDS, report_rows)
        self.stdout.write(f"mode\t{'APPLY' if apply_mode else 'DRY_RUN'}")
        self.stdout.write(f"total\t{len(report_rows)}")
        self.stdout.write(f"ready\t{sum(row['status'] == 'ready' for row in report_rows)}")
        self.stdout.write(f"applied\t{sum(row['status'] == 'applied' for row in report_rows)}")
        self.stdout.write(f"blocked\t{blocked}")
        self.stdout.write(f"report\t{report_path}")
        if blocked:
            raise CommandError("Publication blocked; inspect the TSV report. No files were published.")

    @staticmethod
    def _get_publisher(identifier, *, required):
        if not identifier:
            if required:
                raise CommandError("--published-by is required with --apply")
            return None
        user_model = get_user_model()
        field = user_model.USERNAME_FIELD
        try:
            return user_model._default_manager.get(**{field: identifier})
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Publisher not found: {identifier}") from exc
