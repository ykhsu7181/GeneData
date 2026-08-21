import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, GenomeFile
from files.services.file_relation_service import (
    get_files_for_accession,
    get_files_for_annotation,
    get_files_for_assembly,
)


class ScanFilesNewOnlyTestCase(TransactionTestCase):
    def setUp(self):
        self.scan_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.scan_dir.cleanup)
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

    def test_default_scan_creates_only_datafile_and_filerelation(self):
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

    def test_dry_run_does_not_write_any_file_tables(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        stdout = StringIO()
        self.run_scan(dry_run=True, stdout=stdout)

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)
        output = stdout.getvalue()
        self.assertIn("created_datafile_count=1", output)
        self.assertIn("created_filerelation_count=2", output)

    def test_repeated_scan_does_not_duplicate_datafile_or_filerelation(self):
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

    def test_write_mode_legacy_is_unsupported(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        with self.assertRaises(CommandError):
            self.run_scan(write_mode="legacy")

    def test_write_mode_dual_is_unsupported(self):
        self.write_scan_file(f"genome.{self.accession_code}.fasta")

        with self.assertRaises(CommandError):
            self.run_scan(write_mode="dual")

    def test_scan_creates_accession_assembly_annotation_relations(self):
        annotation_path = self.write_scan_file(f"annotation.{self.accession_code}.gff")

        self.run_scan()

        relation_keys = set(
            FileRelation.objects.values_list("related_type", "related_id", "file_role")
        )
        self.assertIn(("accession", str(self.accession.id), "annotation"), relation_keys)
        self.assertIn(("assembly", str(self.assembly.id), "annotation"), relation_keys)
        self.assertIn(("annotation", str(self.annotation.id), "annotation"), relation_keys)

        accession_files = get_files_for_accession(self.accession.id, file_role="annotation")
        assembly_files = get_files_for_assembly(self.assembly.id, file_role="annotation")
        annotation_files = get_files_for_annotation(self.annotation.id, file_role="annotation")

        for files in [accession_files, assembly_files, annotation_files]:
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["file_path"], annotation_path)
            self.assertEqual(files[0]["source"], "new_relation")

    def test_unmapped_file_writes_report_without_legacy_rows(self):
        self.write_scan_file("genome.UNKNOWN_ACCESSION.fasta")

        self.run_scan()

        self.assertEqual(DataFile.objects.count(), 1)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertEqual(GenomeFile.objects.count(), 0)
        report_files = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("scan_files_unmapped_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(report_files), 1)
        with open(os.path.join(self.output_dir.name, report_files[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("UNKNOWN_ACCESSION", report)
        self.assertIn("no_related_object", report)

    def test_scanned_datafile_can_be_downloaded(self):
        genome_path = self.write_scan_file(f"genome.{self.accession_code}.fasta")

        self.run_scan()
        data_file = DataFile.objects.get(file_path=genome_path)

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"genome.{self.accession_code}.fasta", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b">chr1\nATGC\n")
        response.close()
