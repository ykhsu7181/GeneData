import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import DataFile


class AuditExternalFileCatalogCommandTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def make_data_file(self, code, file_name, publication_status="released"):
        return DataFile.objects.create(
            file_code=code,
            file_name=file_name,
            file_path=str(self.root / code / file_name),
            publication_status=publication_status,
        )

    def test_reports_unique_multiple_unregistered_and_invalid_names(self):
        self.make_data_file("FILE001", "genome.IR64.fasta")
        self.make_data_file("FILE002", "genome.fasta")
        self.make_data_file("FILE003", "GENOME.FASTA")
        source = self.root / "all-files.txt"
        source.write_text(
            "genome.IR64.fasta\n"
            "genome.fasta\n"
            "not-registered.gff\n"
            "../unsafe.fasta\n",
            encoding="utf-8",
        )
        output = self.root / "reports"

        call_command(
            "audit_external_file_catalog",
            file_list=str(source),
            output=str(output),
        )

        with (output / "external_file_catalog_coverage.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle, dialect="excel-tab"))
        self.assertEqual(
            [row["status"] for row in rows],
            [
                "UNIQUE_REGISTERED",
                "MULTIPLE_REGISTERED",
                "UNREGISTERED",
                "INVALID_NAME",
            ],
        )
        self.assertEqual(rows[1]["file_codes"], "FILE002,FILE003")
        self.assertNotIn("file_path", rows[0])
        self.assertNotIn(str(self.root / "FILE001"), str(rows))

    def test_normalized_duplicate_input_names_are_not_silently_collapsed(self):
        source = self.root / "duplicates.txt"
        source.write_text("Genome.Fasta\ngenome.fasta\n", encoding="utf-8")
        output = self.root / "reports"

        call_command(
            "audit_external_file_catalog",
            file_list=str(source),
            output=str(output),
        )

        with (output / "external_file_catalog_coverage.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle, dialect="excel-tab"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(
            all(row["status"] == "DUPLICATE_INPUT_NAME" for row in rows)
        )
