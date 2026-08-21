import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, TransactionTestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services.file_relation_service import get_files_for_accession


class Stage7ReduceLegacyDependencyTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.file_type = FileType.objects.create(
            name=f"FASTA_STAGE7_{self.suffix}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(accession=f"IR64_{self.suffix}")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="default-annotation",
            is_default=True,
        )

    def create_data_file(self, code_suffix, file_path, file_name=None):
        return DataFile.objects.create(
            file_code=f"STAGE7{self.suffix}{code_suffix}",
            file_name=file_name or os.path.basename(file_path),
            file_path=file_path,
            file_size=123,
        )

    def test_legacy_genomefile_no_longer_falls_back_or_logs_warning(self):
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path=f"/tmp/stage7/{self.suffix}/legacy.fasta",
            file_type=self.file_type,
            size=123,
        )

        with self.assertNoLogs("files.services.file_relation_service", level="WARNING"):
            files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    def test_new_relation_does_not_log_warning(self):
        data_file = self.create_data_file("A", f"/tmp/stage7/{self.suffix}/new.fasta")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )

        with self.assertNoLogs("files.services.file_relation_service", level="WARNING"):
            files = get_files_for_accession(self.accession.id)

        self.assertEqual(files[0]["source"], "new_relation")

    def test_new_relation_files_include_datafile_download_url(self):
        data_file = self.create_data_file("B", f"/tmp/stage7/{self.suffix}/detail.fasta")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )

        response = self.client.get(f"/gd/api/files/accessions/{self.accession.accession}/")

        self.assertEqual(response.status_code, 200)
        files = response.json()["data"]["files"]
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertEqual(
            files[0]["datafile_download_url"],
            f"/gd/api/files/data-files/{data_file.id}/download/",
        )

    def test_legacy_files_are_not_returned_by_accession_detail(self):
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path=f"/tmp/stage7/{self.suffix}/legacy.fasta",
            file_type=self.file_type,
            size=123,
        )

        response = self.client.get(f"/gd/api/files/accessions/{self.accession.accession}/")

        self.assertEqual(response.status_code, 200)
        files = response.json()["data"]["files"]
        self.assertEqual(files, [])

    def test_generate_legacy_fix_todo_writes_report_without_changing_database(self):
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path=f"/tmp/stage7/{self.suffix}/legacy.fasta",
            file_type=self.file_type,
            size=123,
        )
        before_counts = self.table_counts()
        stdout = StringIO()

        call_command("generate_legacy_fix_todo", output_dir=self.output_dir.name, stdout=stdout)

        self.assertEqual(self.table_counts(), before_counts)
        self.assertIn("todo_count\t1", stdout.getvalue())
        reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("legacy_fix_todo_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("GenomeFile", report)
        self.assertIn("legacy_genomefile", report)
        self.assertIn("create_datafile_and_filerelation", report)

    def table_counts(self):
        return {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }


class Stage7ScanDefaultModeTestCase(TransactionTestCase):
    def setUp(self):
        self.scan_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.scan_dir.cleanup)
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession = Accession.objects.create(accession=f"IR64_{self.suffix}")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )

    def write_scan_file(self, filename, content=b">chr1\nATGC\n"):
        path = os.path.join(self.scan_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return os.path.abspath(os.path.normpath(path))

    def run_scan(self, **options):
        defaults = {
            "path": self.scan_dir.name,
            "output_dir": self.output_dir.name,
        }
        defaults.update(options)
        call_command("scan_files", **defaults)

    def test_scan_files_default_write_mode_is_new_only(self):
        file_path = self.write_scan_file(f"genome.{self.accession.accession}.fasta")

        self.run_scan()

        self.assertTrue(DataFile.objects.filter(file_path=file_path).exists())
        self.assertTrue(FileRelation.objects.filter(related_type="accession").exists())
        self.assertFalse(GenomeFile.objects.filter(file_path=file_path).exists())

    def test_scan_files_legacy_mode_is_unsupported(self):
        file_path = self.write_scan_file(f"genome.{self.accession.accession}.fasta")

        with self.assertRaises(CommandError):
            self.run_scan(write_mode="legacy")

        self.assertFalse(DataFile.objects.filter(file_path=file_path).exists())
        self.assertFalse(FileRelation.objects.exists())
        self.assertFalse(GenomeFile.objects.filter(file_path=file_path).exists())

    def test_scan_files_new_mode_still_works(self):
        file_path = self.write_scan_file(f"genome.{self.accession.accession}.fasta")

        self.run_scan(write_mode="new")

        self.assertTrue(DataFile.objects.filter(file_path=file_path).exists())
        self.assertTrue(FileRelation.objects.filter(related_type="accession").exists())
        self.assertFalse(GenomeFile.objects.filter(file_path=file_path).exists())

    def test_scan_files_dry_run_does_not_write_database(self):
        self.write_scan_file(f"genome.{self.accession.accession}.fasta")

        self.run_scan(dry_run=True)

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)
