import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation


class BindManualFilesCommandTestCase(TestCase):
    def setUp(self):
        self.manual_dir = tempfile.TemporaryDirectory()
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.manual_dir.cleanup)
        self.addCleanup(self.output_dir.cleanup)
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 genome assembly",
            assembly_code="ASM_IR64_TEST",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            accession=self.accession,
            assembly=self.assembly,
            name="IR64 annotation",
            annotation_code="ANN_IR64_TEST",
            is_default=True,
        )

    def write(self, name, content):
        path = Path(self.manual_dir.name) / name
        path.write_text(content, encoding="utf-8")
        return path

    def run_command(self, *args):
        stdout = StringIO()
        call_command(
            "bind_manual_files",
            *args,
            path=self.manual_dir.name,
            output_dir=self.output_dir.name,
            stdout=stdout,
        )
        report = sorted(Path(self.output_dir.name).glob("bind_manual_files_*.tsv"))[-1]
        with report.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return stdout.getvalue(), rows

    def test_default_is_dry_run(self):
        self.write("genome.IR64.fasta", ">chr1\nACGT\n")

        output, rows = self.run_command()

        self.assertIn("mode\tDRY_RUN", output)
        self.assertEqual(rows[0]["status"], "ready")
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_apply_is_idempotent_and_sets_primary_relations(self):
        self.write("genome.IR64.fasta", ">chr1\nACGT\n")
        self.write(
            "annotation.IR64.gff",
            "##gff-version 3\nchr1\tdemo\tgene\t1\t4\t.\t+\t.\tID=g1\n",
        )

        self.run_command("--apply")
        self.run_command("--apply")

        self.assertEqual(DataFile.objects.count(), 2)
        self.assertEqual(FileRelation.objects.count(), 5)
        self.assertTrue(
            FileRelation.objects.filter(
                related_type="assembly",
                related_id=str(self.assembly.id),
                file_role="genome",
                is_primary=True,
            ).exists()
        )
        self.assertTrue(
            FileRelation.objects.filter(
                related_type="annotation",
                related_id=str(self.annotation.id),
                file_role="annotation",
                is_primary=True,
            ).exists()
        )

    def test_skips_invalid_and_ambiguous_inputs(self):
        self.write("genome.IR64.fasta", "")
        Assembly.objects.create(accession=self.accession, name="second")

        _, rows = self.run_command()

        self.assertEqual(rows[0]["status"], "skipped")
        self.assertEqual(rows[0]["reason"], "empty_file")
        self.assertEqual(DataFile.objects.count(), 0)
