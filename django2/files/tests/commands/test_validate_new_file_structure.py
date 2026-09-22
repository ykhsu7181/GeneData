import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from files.management.commands.validate_new_file_structure import Command
from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile


class ValidateNewFileStructureCommandTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.file_type = FileType.objects.create(
            name=f"FASTA_VALIDATE_{self.suffix}",
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

    def make_data_file(self, code_suffix, file_path, file_name=None, *, is_current=True):
        return DataFile.objects.create(
            file_code=f"VALID{self.suffix}{code_suffix}",
            file_name=file_name or os.path.basename(file_path),
            file_path=file_path,
            file_size=123,
            is_current=is_current,
        )

    def make_genome_file(self, file_path, *, accession=None, organism=None, category="genome"):
        return GenomeFile.objects.create(
            name=os.path.basename(file_path),
            organism=organism or self.accession.accession,
            accession=accession,
            assembly=self.assembly if accession else None,
            category=category,
            file_path=file_path,
            file_type=self.file_type,
            size=123,
        )

    def run_validate(self):
        stdout = StringIO()
        call_command("validate_new_file_structure", output_dir=self.output_dir.name, stdout=stdout)
        return stdout.getvalue()

    def read_detail_report(self):
        reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("validate_new_file_structure_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), "r", encoding="utf-8") as handle:
            return handle.read()

    def test_detects_genomefile_without_datafile(self):
        self.make_genome_file(f"/tmp/validate/{self.suffix}/missing_datafile.fasta", accession=self.accession)
        before_counts = self.table_counts()

        output = self.run_validate()

        self.assertEqual(self.table_counts(), before_counts)
        self.assertIn("genomefile_missing_datafile_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("genomefile_missing_datafile", self.read_detail_report())

    def test_detects_datafile_without_filerelation(self):
        self.make_data_file("A", f"/tmp/validate/{self.suffix}/orphan_datafile.fasta")

        output = self.run_validate()

        self.assertIn("datafile_without_relation_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("datafile_without_relation", self.read_detail_report())

    def test_ignores_inactive_quarantined_datafile_without_relation(self):
        self.make_data_file(
            "Q",
            f"/tmp/validate/{self.suffix}/quarantined.fasta",
            is_current=False,
        )

        output = self.run_validate()

        self.assertIn("datafile_without_relation_count\t0", output)
        self.assertNotIn("quarantined.fasta", self.read_detail_report())

    def test_detects_broken_filerelation(self):
        data_file = self.make_data_file("B", f"/tmp/validate/{self.suffix}/broken_relation.fasta")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id="999999999",
            related_code="missing",
            file_role="genome",
        )

        output = self.run_validate()

        self.assertIn("broken_filerelation_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("missing_related_object", self.read_detail_report())

    def test_duplicate_filerelation_detection_helper(self):
        duplicates = Command.find_duplicate_relation_keys(
            [
                {
                    "file_id": 1,
                    "related_type": "accession",
                    "related_id": "10",
                    "file_role": "genome",
                },
                {
                    "file_id": 1,
                    "related_type": "accession",
                    "related_id": "10",
                    "file_role": "genome",
                },
                {
                    "file_id": 2,
                    "related_type": "accession",
                    "related_id": "10",
                    "file_role": "genome",
                },
            ]
        )

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["row_count"], 2)
        self.assertEqual(duplicates[0]["file_id"], 1)

    def test_detects_legacy_fallback(self):
        path = f"/tmp/validate/{self.suffix}/legacy.fasta"
        self.make_genome_file(path, accession=self.accession)
        self.make_data_file("C", path)

        output = self.run_validate()

        self.assertIn("legacy_fallback_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("legacy_fallback", self.read_detail_report())

    def test_detects_organism_fallback(self):
        path = f"/tmp/validate/{self.suffix}/organism.fasta"
        self.make_genome_file(path, organism=self.accession.accession)
        self.make_data_file("D", path)

        output = self.run_validate()

        self.assertIn("organism_fallback_count\t1", output)
        self.assertIn("result\tFAIL", output)
        self.assertIn("organism_fallback", self.read_detail_report())

    def test_passes_when_new_structure_is_complete(self):
        path = f"/tmp/validate/{self.suffix}/complete.fasta"
        data_file = self.make_data_file("E", path)
        self.make_genome_file(path, accession=self.accession)
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )

        output = self.run_validate()

        self.assertIn("genomefile_missing_datafile_count\t0", output)
        self.assertIn("datafile_without_relation_count\t0", output)
        self.assertIn("broken_filerelation_count\t0", output)
        self.assertIn("duplicate_filerelation_count\t0", output)
        self.assertIn("legacy_fallback_count\t0", output)
        self.assertIn("organism_fallback_count\t0", output)
        self.assertIn("result\tPASS", output)

    def test_fails_when_any_key_issue_exists(self):
        self.make_data_file("F", f"/tmp/validate/{self.suffix}/orphan.fasta")

        output = self.run_validate()

        self.assertIn("result\tFAIL", output)
        self.assertIn("cannot_enter_new_only\ttrue", output)

    def test_command_is_read_only(self):
        path = f"/tmp/validate/{self.suffix}/readonly.fasta"
        data_file = self.make_data_file("G", path)
        self.make_genome_file(path, accession=self.accession)
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )
        before_counts = self.table_counts()

        self.run_validate()

        self.assertEqual(self.table_counts(), before_counts)

    def table_counts(self):
        return {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }
