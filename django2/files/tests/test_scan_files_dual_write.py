import os
import tempfile
import uuid

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, GenomeFile
from files.services.file_relation_service import get_files_for_accession


class ScanFilesNewOnlyCompatibilityTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.accession_code = f"IR64_{uuid.uuid4().hex[:8].upper()}"
        self.accession = Accession.objects.create(accession=self.accession_code)
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

    def write_scan_file(self, filename, content=b">chr1\nATGC\n"):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return os.path.abspath(os.path.normpath(path))

    def run_scan(self, **options):
        defaults = {
            "path": self.temp_dir.name,
            "output_dir": self.output_dir.name,
        }
        defaults.update(options)
        call_command("scan_files", **defaults)

    def test_dry_run_does_not_write_database(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        self.run_scan(dry_run=True)

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)

    def test_default_mode_writes_datafile_and_filerelation_only(self):
        genome_path = self.write_scan_file(f"genome.{self.accession_code}.fasta")

        self.run_scan()

        self.assertTrue(DataFile.objects.filter(file_path=genome_path).exists())
        self.assertTrue(
            FileRelation.objects.filter(
                related_type="accession",
                related_id=str(self.accession.id),
                file_role="genome",
            ).exists()
        )
        self.assertFalse(GenomeFile.objects.filter(file_path=genome_path).exists())

    def test_repeated_scan_does_not_duplicate_new_records(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        self.run_scan()
        self.run_scan()

        self.assertEqual(DataFile.objects.count(), 1)
        self.assertEqual(
            FileRelation.objects.filter(
                related_type="accession",
                related_id=str(self.accession.id),
                file_role="genome",
            ).count(),
            1,
        )
        self.assertEqual(GenomeFile.objects.count(), 0)

    def test_accession_assembly_annotation_relations_are_created(self):
        self.write_scan_file(f"annotation.{self.accession_code}.gff")

        self.run_scan()

        relation_keys = set(
            FileRelation.objects.values_list("related_type", "related_id", "file_role")
        )
        self.assertIn(("accession", str(self.accession.id), "annotation"), relation_keys)
        self.assertIn(("assembly", str(self.assembly.id), "annotation"), relation_keys)
        self.assertIn(("annotation", str(self.annotation.id), "annotation"), relation_keys)

    def test_unmapped_file_is_reported(self):
        self.write_scan_file("genome.UNKNOWN_ACCESSION.fasta")

        self.run_scan(write_mode="new")

        self.assertEqual(FileRelation.objects.count(), 0)
        report_files = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("scan_files_unmapped_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(report_files), 1)
        with open(os.path.join(self.output_dir.name, report_files[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("UNKNOWN_ACCESSION", report)
        self.assertIn("no_related_object", report)

    def test_legacy_mode_is_unsupported(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        with self.assertRaises(CommandError):
            self.run_scan(write_mode="legacy")

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)

    def test_dual_mode_is_unsupported(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        with self.assertRaises(CommandError):
            self.run_scan(write_mode="dual")

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)

    def test_new_datafile_is_queryable_for_accession(self):
        genome_path = self.write_scan_file(f"genome.{self.accession_code}.fasta")

        self.run_scan()

        files = get_files_for_accession(self.accession.id)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_path"], genome_path)
        self.assertEqual(files[0]["source"], "new_relation")

    def test_scanned_datafile_can_be_downloaded(self):
        genome_path = self.write_scan_file(f"genome.{self.accession_code}.fasta")
        self.run_scan()
        data_file = DataFile.objects.get(file_path=genome_path)

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"genome.{self.accession_code}.fasta", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b">chr1\nATGC\n")
        response.close()
