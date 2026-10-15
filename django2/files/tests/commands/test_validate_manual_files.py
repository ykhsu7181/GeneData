import csv
import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, DataFile


class ValidateManualFilesCommandTestCase(TestCase):
    def setUp(self):
        self.manual_dir = tempfile.TemporaryDirectory()
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.manual_dir.cleanup)
        self.addCleanup(self.output_dir.cleanup)
        self.accession = Accession.objects.create(accession="IR64")

    def write(self, name, content, *, binary=False):
        path = Path(self.manual_dir.name) / name
        if binary:
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def run_command(self, **kwargs):
        stdout = StringIO()
        call_command(
            "validate_manual_files",
            path=self.manual_dir.name,
            output_dir=self.output_dir.name,
            stdout=stdout,
            **kwargs,
        )
        report = next(Path(self.output_dir.name).glob("validate_manual_files_*.tsv"))
        with report.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return stdout.getvalue(), rows

    def test_validates_without_writing_database(self):
        fasta = self.write("genome.IR64.fasta", ">chr1\nACGTNN\n")
        before = {
            "accessions": Accession.objects.count(),
            "datafiles": DataFile.objects.count(),
        }

        output, rows = self.run_command(checksum="md5")

        self.assertEqual(rows[0]["status"], "warning")
        self.assertIn("missing_assembly_context", rows[0]["issues"])
        self.assertEqual(
            rows[0]["checksum"],
            hashlib.md5(fasta.read_bytes()).hexdigest(),
        )
        self.assertEqual(Accession.objects.count(), before["accessions"])
        self.assertEqual(DataFile.objects.count(), before["datafiles"])
        self.assertTrue(fasta.exists())
        summary = next(Path(self.output_dir.name).glob("validate_manual_files_*.txt"))
        self.assertIn("read_only", summary.read_text())
        self.assertIn("result\tPASS_WITH_WARNINGS", output)

    def test_reports_empty_invalid_and_unrecognized_files(self):
        self.write("annotation.IR64.gff", "")
        self.write("genome.IR64.fasta", ">chr1\n测试\n")
        self.write("notes.png", b"not-an-image", binary=True)

        output, rows = self.run_command()
        by_name = {row["file_name"]: row for row in rows}

        self.assertEqual(by_name["annotation.IR64.gff"]["status"], "error")
        self.assertIn("empty_file", by_name["annotation.IR64.gff"]["issues"])
        self.assertEqual(by_name["genome.IR64.fasta"]["status"], "error")
        self.assertIn("invalid_fasta_sequence_characters", by_name["genome.IR64.fasta"]["issues"])
        self.assertEqual(by_name["notes.png"]["status"], "warning")
        self.assertIn("unrecognized_filename", by_name["notes.png"]["issues"])
        self.assertIn("result\tFAIL", output)

    def test_understands_telomere_fai_and_fastaq_names(self):
        self.write("telomere.IR64.txt", "chr1\t100\t200\n")
        self.write("genome.IR64.fasta.fai", "chr1\t1000\t6\t80\t81\n")

        import gzip

        fastq_path = Path(self.manual_dir.name) / "transcriptome.root.IR64.fastaq.gz"
        with gzip.open(fastq_path, "wt", encoding="utf-8") as handle:
            handle.write("@read1\nACGT\n+\n!!!!\n")

        _, rows = self.run_command()
        by_name = {row["file_name"]: row for row in rows}
        self.assertEqual(by_name["telomere.IR64.txt"]["file_role"], "telomere")
        self.assertEqual(by_name["genome.IR64.fasta.fai"]["file_role"], "genome_index")
        self.assertEqual(
            by_name["transcriptome.root.IR64.fastaq.gz"]["file_role"],
            "transcriptome.root",
        )

    def test_filesystem_only_does_not_require_database_context(self):
        self.write("genome.UNKNOWN.fasta", ">chr1\nACGT\n")

        _, rows = self.run_command(filesystem_only=True)

        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["accession_state"], "not_checked")
        self.assertEqual(rows[0]["datafile_state"], "not_checked")
