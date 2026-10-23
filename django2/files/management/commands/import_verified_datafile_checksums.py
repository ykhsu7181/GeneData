import csv
import hashlib
import os
import re
from datetime import datetime, timezone as datetime_timezone
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


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FIELDS = (
    "file_path",
    "file_code",
    "status",
    "reason",
    "file_size",
    "sha256",
)


class Command(BaseCommand):
    help = (
        "Import DataFile SHA-256 values from an independently checksummed, "
        "read-only validation report. Default mode is dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--audit-report", required=True)
        parser.add_argument("--audit-report-sha256", required=True)
        parser.add_argument("--selection-manifest", required=True)
        parser.add_argument("--selection-manifest-sha256", required=True)
        parser.add_argument("--exception-report", default=None)
        parser.add_argument("--exception-report-sha256", default=None)
        parser.add_argument(
            "--audit-started-at",
            required=True,
            help="ISO-8601 start time of the source validation run.",
        )
        parser.add_argument("--output-dir", default=None)
        add_safe_mode_arguments(parser)

    def handle(self, *args, **options):
        apply_mode = is_apply_mode(options)
        cutoff = self.parse_cutoff(options["audit_started_at"])
        audit_path = self.verify_file(
            options["audit_report"], options["audit_report_sha256"], "audit report"
        )
        selection_path = self.verify_file(
            options["selection_manifest"],
            options["selection_manifest_sha256"],
            "selection manifest",
        )
        exception_paths = set()
        exception_report = options.get("exception_report")
        exception_sha256 = options.get("exception_report_sha256")
        if bool(exception_report) != bool(exception_sha256):
            raise CommandError(
                "--exception-report and --exception-report-sha256 must be supplied together"
            )
        if exception_report:
            exception_path = self.verify_file(
                exception_report, exception_sha256, "exception report"
            )
            exception_paths = self.load_exception_paths(exception_path)

        audit_rows = self.load_unique_rows(
            audit_path,
            required={
                "file_path",
                "file_size",
                "checksum_algorithm",
                "checksum",
                "status",
                "issues",
            },
        )
        selection_rows = self.load_unique_rows(
            selection_path,
            required={"file_path"},
        )

        report_rows = []
        prepared = []
        for normalized_path, selection_row in selection_rows.items():
            audit_row = audit_rows.get(normalized_path)
            issues = []
            data_file = DataFile.objects.filter(
                file_path=normalized_path,
                is_current=True,
            ).first()
            if audit_row is None:
                issues.append("audit_row_missing")
                expected_size = ""
                digest = ""
            else:
                expected_size, digest = self.inspect_audit_row(
                    audit_row,
                    normalized_path=normalized_path,
                    exception_paths=exception_paths,
                    issues=issues,
                )

            path = Path(normalized_path)
            actual_size = ""
            try:
                stat = path.stat()
                actual_size = stat.st_size
                if expected_size != "" and actual_size != expected_size:
                    issues.append("file_size_changed_after_audit")
                modified_at = datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=datetime_timezone.utc,
                )
                if modified_at > cutoff:
                    issues.append("file_modified_after_audit_start")
            except OSError:
                issues.append("file_not_readable")

            if data_file is None:
                issues.append("current_datafile_not_found")
            elif data_file.file_size not in (None, actual_size):
                issues.append("datafile_size_mismatch")
            elif data_file.sha256:
                current_digest = data_file.sha256.strip().lower()
                if current_digest != digest:
                    issues.append("existing_sha256_mismatch")

            issues = list(dict.fromkeys(issues))
            if issues:
                status = "blocked"
                reason = ",".join(issues)
            elif data_file.sha256:
                status = "already_applied"
                reason = "sha256_already_matches"
            else:
                status = "ready" if not apply_mode else "pending"
                reason = "verified_audit_evidence"
                prepared.append((data_file, digest))

            report_rows.append(
                {
                    "file_path": selection_row["file_path"],
                    "file_code": data_file.file_code if data_file else "",
                    "status": status,
                    "reason": reason,
                    "file_size": actual_size,
                    "sha256": digest,
                }
            )

        blocked = sum(row["status"] == "blocked" for row in report_rows)
        if apply_mode and not blocked:
            report_by_file_code = {
                row["file_code"]: row for row in report_rows if row["file_code"]
            }
            runtime_blocked = False
            with transaction.atomic():
                locked = {
                    item.id: item
                    for item in DataFile.objects.select_for_update().filter(
                        id__in=[item.id for item, _digest in prepared]
                    )
                }
                for data_file, digest in prepared:
                    current = locked.get(data_file.id)
                    report_row = report_by_file_code[data_file.file_code]
                    if current is None or current.sha256:
                        report_row["status"] = "blocked"
                        report_row["reason"] = "datafile_changed_before_apply"
                        blocked += 1
                        runtime_blocked = True
                        transaction.set_rollback(True)
                        break
                    current.sha256 = digest
                    current.save(update_fields=["sha256", "updated_at"])
                    report_row["status"] = "applied"
            if runtime_blocked:
                for row in report_rows:
                    if row["status"] in {"applied", "pending"}:
                        row["status"] = "ready_not_applied"
        elif apply_mode:
            for row in report_rows:
                if row["status"] == "pending":
                    row["status"] = "ready_not_applied"

        report_path = make_report_path(options["output_dir"], "verified_checksum_import")
        write_tsv(report_path, FIELDS, report_rows)
        self.stdout.write(f"mode\t{'APPLY' if apply_mode else 'DRY_RUN'}")
        self.stdout.write(f"total\t{len(report_rows)}")
        self.stdout.write(f"ready\t{sum(row['status'] == 'ready' for row in report_rows)}")
        applied = sum(row["status"] == "applied" for row in report_rows)
        already_applied = sum(
            row["status"] == "already_applied" for row in report_rows
        )
        self.stdout.write(f"applied\t{applied}")
        self.stdout.write(f"already_applied\t{already_applied}")
        self.stdout.write(f"blocked\t{blocked}")
        self.stdout.write(f"report\t{report_path}")
        if blocked:
            raise CommandError(
                "Checksum import blocked; inspect the TSV report. "
                "No checksums were imported."
            )

    @staticmethod
    def parse_cutoff(value):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("--audit-started-at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise CommandError("--audit-started-at must include a timezone offset")
        return parsed.astimezone(datetime_timezone.utc)

    @staticmethod
    def verify_file(path_value, expected_digest, label):
        path = Path(path_value).expanduser().resolve()
        expected = (expected_digest or "").strip().lower()
        if not path.is_file():
            raise CommandError(f"{label} not found: {path}")
        if not SHA256_PATTERN.fullmatch(expected):
            raise CommandError(f"{label} SHA-256 must contain 64 lowercase hex characters")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise CommandError(f"{label} SHA-256 mismatch")
        return path

    @staticmethod
    def load_unique_rows(path, *, required):
        rows = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f"{path.name} is missing columns: {', '.join(sorted(missing))}"
                )
            for row in reader:
                raw_path = (row.get("file_path") or "").strip()
                if not raw_path or raw_path == "SUMMARY":
                    continue
                normalized = os.path.abspath(os.path.normpath(raw_path))
                if normalized in rows:
                    raise CommandError(f"Duplicate file_path in {path.name}: {raw_path}")
                rows[normalized] = {
                    key: (value or "").strip() for key, value in row.items()
                }
        if not rows:
            raise CommandError(f"{path.name} contains no data rows")
        return rows

    def load_exception_paths(self, path):
        rows = self.load_unique_rows(
            path,
            required={"file_path", "status", "detail"},
        )
        accepted = set()
        for normalized_path, row in rows.items():
            if row["status"] != "PASS" or row["detail"] != "first_member_readable":
                raise CommandError(
                    f"Exception evidence is not PASS/first_member_readable: {row['file_path']}"
                )
            accepted.add(normalized_path)
        return accepted

    @staticmethod
    def inspect_audit_row(audit_row, *, normalized_path, exception_paths, issues):
        if audit_row["checksum_algorithm"].lower() != "sha256":
            issues.append("audit_checksum_not_sha256")
        digest = audit_row["checksum"].lower()
        if not SHA256_PATTERN.fullmatch(digest):
            issues.append("audit_sha256_invalid")
        try:
            expected_size = int(audit_row["file_size"])
            if expected_size <= 0:
                issues.append("audit_file_empty")
        except ValueError:
            expected_size = ""
            issues.append("audit_file_size_invalid")

        audit_issues = audit_row["issues"]
        if "empty_file" in audit_issues:
            issues.append("audit_empty_file")
        if "invalid_content" in audit_issues and normalized_path not in exception_paths:
            issues.append("invalid_content_without_exception_evidence")
        return expected_size, digest
