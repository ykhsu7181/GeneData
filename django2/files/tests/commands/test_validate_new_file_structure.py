import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from files.management.commands.validate_new_file_structure import Command
from files.models import Accession, DataFile, FileRelation


class ValidateNewFileStructureCommandTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession = Accession.objects.create(accession=f"IR64_{self.suffix}")

    def make_data_file(self, code_suffix, *, is_current=True):
        return DataFile.objects.create(
            file_code=f"VALID{self.suffix}{code_suffix}",
            file_name=f"{code_suffix}.fasta",
            file_path=f"/tmp/validate/{self.suffix}/{code_suffix}.fasta",
            file_size=123,
            is_current=is_current,
        )

    def run_validate(self):
        stdout = StringIO()
        call_command(
            "validate_new_file_structure",
            output_dir=self.output_dir.name,
            stdout=stdout,
        )
        return stdout.getvalue()

    def read_detail_report(self):
        reports = [
            name
            for name in os.listdir(self.output_dir.name)
            if name.startswith("validate_new_file_structure_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), encoding="utf-8") as handle:
            return handle.read()

    def test_detects_current_datafile_without_relation(self):
        self.make_data_file("ORPHAN")

        output = self.run_validate()

        self.assertIn("datafile_without_relation_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("datafile_without_relation", self.read_detail_report())

    def test_ignores_inactive_datafile_without_relation(self):
        self.make_data_file("QUARANTINED", is_current=False)

        output = self.run_validate()

        self.assertIn("datafile_without_relation_count\t0", output)
        self.assertIn("result\tPASS", output)

    def test_valid_datafile_relation_passes(self):
        data_file = self.make_data_file("GENOME")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )

        output = self.run_validate()

        self.assertIn("datafile_total_count\t1", output)
        self.assertIn("datafile_without_relation_count\t0", output)
        self.assertIn("broken_filerelation_count\t0", output)
        self.assertIn("duplicate_filerelation_count\t0", output)
        self.assertIn("result\tPASS", output)

    def test_command_is_read_only(self):
        data_file = self.make_data_file("READONLY")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="genome",
        )
        before = (DataFile.objects.count(), FileRelation.objects.count())

        self.run_validate()

        self.assertEqual(before, (DataFile.objects.count(), FileRelation.objects.count()))

    def test_duplicate_relation_helper_remains_deterministic(self):
        duplicates = Command.find_duplicate_relation_keys([
            {"file_id": 1, "related_type": "accession", "related_id": 2, "file_role": "genome"},
            {"file_id": 1, "related_type": "accession", "related_id": "2", "file_role": "genome"},
        ])

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["row_count"], 2)
