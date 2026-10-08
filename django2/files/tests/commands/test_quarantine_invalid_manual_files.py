import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import DataFile


class QuarantineInvalidManualFilesCommandTestCase(TestCase):
    def setUp(self):
        self.manual_dir = tempfile.TemporaryDirectory()
        self.quarantine_dir = tempfile.TemporaryDirectory()
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.manual_dir.cleanup)
        self.addCleanup(self.quarantine_dir.cleanup)
        self.addCleanup(self.output_dir.cleanup)

    def write(self, name, content):
        path = Path(self.manual_dir.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_command(self, *args):
        stdout = StringIO()
        call_command(
            "quarantine_invalid_manual_files",
            *args,
            path=self.manual_dir.name,
            quarantine_root=self.quarantine_dir.name,
            output_dir=self.output_dir.name,
            stdout=stdout,
        )
        report = sorted(
            Path(self.output_dir.name).glob("quarantine_invalid_manual_files_*.tsv")
        )[-1]
        with report.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return stdout.getvalue(), rows

    def test_dry_run_only_reports_recognized_invalid_files(self):
        invalid = self.write("genome.BAD.fasta", "测试")
        valid = self.write("genome.GOOD.fasta", ">chr1\nACGT\n")
        auxiliary = self.write("notes.txt", "keep me")

        output, rows = self.run_command()

        self.assertIn("mode\tDRY_RUN", output)
        self.assertEqual([row["file_name"] for row in rows], [invalid.name])
        self.assertEqual(rows[0]["status"], "candidate")
        self.assertTrue(invalid.exists())
        self.assertTrue(valid.exists())
        self.assertTrue(auxiliary.exists())

    def test_apply_moves_file_and_updates_datafile_without_deleting_it(self):
        invalid = self.write("nested/genome.BAD.fasta", "")
        data_file = DataFile.objects.create(
            file_code="FILE_BAD",
            file_name=invalid.name,
            file_path=str(invalid.resolve()),
            is_current=True,
        )

        output, rows = self.run_command("--apply")

        self.assertIn("moved\t1", output)
        self.assertFalse(invalid.exists())
        target = Path(rows[0]["target_path"])
        self.assertTrue(target.exists())
        self.assertEqual(target.relative_to(Path(self.quarantine_dir.name)).parts[1:], ("nested", invalid.name))
        data_file.refresh_from_db()
        self.assertFalse(data_file.is_current)
        self.assertEqual(Path(data_file.file_path), target)
        self.assertIn("Quarantined", data_file.description)

    def test_existing_target_blocks_move(self):
        invalid = self.write("genome.BAD.fasta", "")
        batch = Path(self.quarantine_dir.name) / __import__("datetime").date.today().strftime("%Y%m%d")
        batch.mkdir(parents=True)
        (batch / invalid.name).write_text("existing", encoding="utf-8")

        _, rows = self.run_command("--apply")

        self.assertEqual(rows[0]["status"], "blocked")
        self.assertIn("target_already_exists", rows[0]["blocked_reason"])
        self.assertTrue(invalid.exists())
