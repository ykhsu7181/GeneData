import csv
import hashlib
import tempfile
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import DataFile


class ImportVerifiedDatafileChecksumsCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "reports"
        self.output_dir.mkdir()

    def write_tsv(self, name, fieldnames, rows):
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        return path

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def make_inputs(self, *, invalid_content=False, include_exception=False):
        data_path = self.root / "transcriptome.all.IR64.tar.gz"
        data_path.write_bytes(b"verified archive bytes")
        digest = self.digest(data_path)
        data_file = DataFile.objects.create(
            file_code="FILE000001",
            file_name=data_path.name,
            file_path=str(data_path.resolve()),
            file_size=data_path.stat().st_size,
        )
        selection = self.write_tsv(
            "selection.tsv",
            ["file_path", "file_role"],
            [{"file_path": str(data_path.resolve()), "file_role": "transcriptome.all"}],
        )
        audit = self.write_tsv(
            "audit.tsv",
            [
                "status",
                "file_path",
                "file_size",
                "checksum_algorithm",
                "checksum",
                "issues",
            ],
            [
                {
                    "status": "error" if invalid_content else "ok",
                    "file_path": str(data_path.resolve()),
                    "file_size": data_path.stat().st_size,
                    "checksum_algorithm": "sha256",
                    "checksum": digest,
                    "issues": "invalid_content:UnicodeDecodeError" if invalid_content else "",
                }
            ],
        )
        exception = None
        if include_exception:
            exception = self.write_tsv(
                "exception.tsv",
                ["file_path", "status", "detail"],
                [
                    {
                        "file_path": str(data_path.resolve()),
                        "status": "PASS",
                        "detail": "first_member_readable",
                    }
                ],
            )
        return data_file, selection, audit, exception

    def run_command(self, selection, audit, exception=None, **kwargs):
        options = {
            "selection_manifest": str(selection),
            "selection_manifest_sha256": self.digest(selection),
            "audit_report": str(audit),
            "audit_report_sha256": self.digest(audit),
            "audit_started_at": (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat(),
            "output_dir": str(self.output_dir),
            "stdout": StringIO(),
        }
        if exception:
            options.update(
                {
                    "exception_report": str(exception),
                    "exception_report_sha256": self.digest(exception),
                }
            )
        options.update(kwargs)
        call_command("import_verified_datafile_checksums", **options)
        return options["stdout"].getvalue()

    def test_dry_run_accepts_independently_verified_invalid_content_without_writing(self):
        data_file, selection, audit, exception = self.make_inputs(
            invalid_content=True,
            include_exception=True,
        )

        output = self.run_command(selection, audit, exception)

        data_file.refresh_from_db()
        self.assertIsNone(data_file.sha256)
        self.assertIn("mode\tDRY_RUN", output)
        self.assertIn("ready\t1", output)
        self.assertIn("blocked\t0", output)

    def test_apply_saves_verified_checksum(self):
        data_file, selection, audit, exception = self.make_inputs(
            invalid_content=True,
            include_exception=True,
        )
        with audit.open(encoding="utf-8", newline="") as handle:
            expected = next(csv.DictReader(handle, delimiter="\t"))["checksum"]

        output = self.run_command(selection, audit, exception, apply=True)

        data_file.refresh_from_db()
        self.assertEqual(data_file.sha256, expected)
        self.assertIn("applied\t1", output)
        self.assertIn("blocked\t0", output)

    def test_invalid_content_without_exception_evidence_blocks_all_writes(self):
        data_file, selection, audit, _exception = self.make_inputs(
            invalid_content=True,
            include_exception=False,
        )

        with self.assertRaises(CommandError):
            self.run_command(selection, audit, apply=True)

        data_file.refresh_from_db()
        self.assertIsNone(data_file.sha256)

    def test_rejects_tampered_audit_report(self):
        _data_file, selection, audit, _exception = self.make_inputs()

        with self.assertRaisesMessage(CommandError, "audit report SHA-256 mismatch"):
            call_command(
                "import_verified_datafile_checksums",
                selection_manifest=str(selection),
                selection_manifest_sha256=self.digest(selection),
                audit_report=str(audit),
                audit_report_sha256="0" * 64,
                audit_started_at=(
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
                output_dir=str(self.output_dir),
            )
