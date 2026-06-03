import hashlib
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    FileRelation,
    FileType,
    GenomeFile,
)


class BackfillGenomeFileToDataFileCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = os.path.join(self.temp_dir.name, "out")
        os.makedirs(self.output_dir, exist_ok=True)

        self.file_type = FileType.objects.create(name="FASTA", extension="fasta")
        self.accession = Accession.objects.create(accession="IR64")
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

    def create_disk_file(self, filename, content=b"ATGC\n"):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def call_backfill(self, *args):
        stdout = StringIO()
        call_command(
            "backfill_genomefile_to_datafile",
            *args,
            output_dir=self.output_dir,
            stdout=stdout,
        )
        return stdout.getvalue()

    def test_backfill_creates_data_file_and_relations_idempotently(self):
        file_path = self.create_disk_file("genome.IR64.fasta")
        GenomeFile.objects.create(
            name="genome.IR64.fasta",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="genome",
            file_path=file_path,
            file_type=self.file_type,
            size=0,
        )

        self.call_backfill()
        self.call_backfill()

        data_file = DataFile.objects.get(file_path=file_path)
        self.assertEqual(data_file.file_code, "FILE000001")
        self.assertEqual(data_file.file_name, "genome.IR64.fasta")
        self.assertEqual(data_file.file_size, os.path.getsize(file_path))
        self.assertIsNone(data_file.md5)

        relations = set(
            FileRelation.objects.values_list("related_type", "related_id", "file_role")
        )
        self.assertEqual(DataFile.objects.count(), 1)
        self.assertEqual(FileRelation.objects.count(), 3)
        self.assertEqual(
            relations,
            {
                ("accession", str(self.accession.id), "genome"),
                ("assembly", str(self.assembly.id), "genome"),
                ("annotation", str(self.annotation.id), "genome"),
            },
        )

    def test_dry_run_writes_reports_without_creating_records(self):
        file_path = self.create_disk_file("annotation.IR64.gff")
        GenomeFile.objects.create(
            name="annotation.IR64.gff",
            organism="IR64",
            accession=self.accession,
            category="annotation",
            file_path=file_path,
            file_type=self.file_type,
            size=0,
        )

        self.call_backfill("--dry-run")

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "migration_log.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "unmapped_files.tsv")))

    def test_unmapped_and_missing_file_are_reported(self):
        missing_path = os.path.join(self.temp_dir.name, "missing.fasta")
        GenomeFile.objects.create(
            name="missing.fasta",
            organism="LEGACY",
            category="genome",
            file_path=missing_path,
            file_type=self.file_type,
            size=0,
        )

        self.call_backfill()

        data_file = DataFile.objects.get(file_path=missing_path)
        self.assertIsNone(data_file.file_size)
        self.assertEqual(FileRelation.objects.count(), 0)

        unmapped_path = os.path.join(self.output_dir, "unmapped_files.tsv")
        with open(unmapped_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("missing.fasta", content)
        self.assertIn("missing_file", content)
        self.assertIn("no_explicit_relation", content)

    def test_with_md5_computes_checksum(self):
        content = b"ATGCATGC\n"
        file_path = self.create_disk_file("genome.IR64.fa", content=content)
        GenomeFile.objects.create(
            name="genome.IR64.fa",
            organism="IR64",
            accession=self.accession,
            category="genome",
            file_path=file_path,
            file_type=self.file_type,
            size=0,
        )

        self.call_backfill("--with-md5")

        data_file = DataFile.objects.get(file_path=file_path)
        self.assertEqual(data_file.md5, hashlib.md5(content).hexdigest())
