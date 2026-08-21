import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    GenomeFile,
)


class AuditFileMigrationCommandTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.file_type = FileType.objects.create(
            name=f"FASTA_AUDIT_{self.suffix}",
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

    def make_data_file(self, code_suffix, file_path, file_name=None):
        return DataFile.objects.create(
            file_code=f"FILEAUD{self.suffix}{code_suffix}",
            file_name=file_name or os.path.basename(file_path),
            file_path=file_path,
            file_size=123,
        )

    def test_audit_file_migration_reports_coverage_and_dirty_data(self):
        mapped_path = f"/tmp/audit/{self.suffix}/mapped.fasta"
        unmapped_path = f"/tmp/audit/{self.suffix}/legacy_only.fasta"
        duplicate_path = f"/tmp/audit/{self.suffix}/duplicate.fasta"
        data_file = self.make_data_file("A", mapped_path)
        orphan_data_file = self.make_data_file("B", f"/tmp/audit/{self.suffix}/orphan.fasta")
        GenomeFile.objects.create(
            name="mapped.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path=mapped_path,
            file_type=self.file_type,
            size=123,
        )
        GenomeFile.objects.create(
            name="legacy_only.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path=unmapped_path,
            file_type=self.file_type,
            size=123,
        )
        GenomeFile.objects.create(
            name="duplicate.1.fasta",
            organism=self.accession.accession,
            category="genome",
            file_path=duplicate_path,
            file_type=self.file_type,
            size=123,
        )
        GenomeFile.objects.create(
            name="duplicate.2.fasta",
            organism=self.accession.accession,
            category="genome",
            file_path=duplicate_path,
            file_type=self.file_type,
            size=123,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )
        FileRelation.objects.create(
            file=orphan_data_file,
            related_type="accession",
            related_id="999999999",
            related_code="missing",
            file_role="genome",
        )
        before_counts = self.table_counts()
        stdout = StringIO()

        call_command("audit_file_migration", output_dir=self.output_dir.name, stdout=stdout)

        self.assertEqual(self.table_counts(), before_counts)
        output = stdout.getvalue()
        self.assertIn("genomefile_total\t4", output)
        self.assertIn("genomefile_matched_datafile_count\t1", output)
        self.assertIn("genomefile_missing_datafile_count\t3", output)
        self.assertIn("datafile_without_relation_count\t0", output)
        self.assertIn("broken_filerelation_count\t1", output)
        self.assertIn("duplicate_file_path_count\t1", output)
        self.assertIn("duplicate_filerelation_count\t0", output)
        reports = os.listdir(self.output_dir.name)
        self.assertTrue(any(name.startswith("file_migration_audit_") and name.endswith(".txt") for name in reports))
        tsv_files = [name for name in reports if name.startswith("file_migration_audit_") and name.endswith(".tsv")]
        self.assertEqual(len(tsv_files), 1)
        with open(os.path.join(self.output_dir.name, tsv_files[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("missing_datafile", report)
        self.assertIn("broken_filerelation", report)
        self.assertIn("duplicate_file_path", report)

    def test_audit_file_migration_reports_datafile_without_relation(self):
        self.make_data_file("C", f"/tmp/audit/{self.suffix}/no_relation.fasta")
        stdout = StringIO()

        call_command("audit_file_migration", output_dir=self.output_dir.name, stdout=stdout)

        self.assertIn("datafile_without_relation_count\t1", stdout.getvalue())

    def test_audit_file_relations_reports_broken_and_duplicate_summary(self):
        data_file = self.make_data_file("D", f"/tmp/audit/{self.suffix}/relation.fasta")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id="999999999",
            related_code="missing",
            file_role="genome",
        )
        stdout = StringIO()

        call_command("audit_file_relations", output_dir=self.output_dir.name, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("broken_relation_count\t1", output)
        self.assertIn("duplicate_relation_count\t0", output)
        reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("broken_file_relations_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("missing_related_object", report)

    def test_audit_legacy_fallback_reports_legacy_and_organism_dependencies(self):
        relation_file = self.make_data_file("E", f"/tmp/audit/{self.suffix}/new.fasta")
        FileRelation.objects.create(
            file=relation_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )
        legacy_accession = Accession.objects.create(accession=f"LEGACY_{self.suffix}")
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=legacy_accession.accession,
            accession=legacy_accession,
            category="genome",
            file_path=f"/tmp/audit/{self.suffix}/legacy.fasta",
            file_type=self.file_type,
            size=123,
        )
        organism_accession = Accession.objects.create(accession=f"ORG_{self.suffix}")
        GenomeFile.objects.create(
            name="organism.fasta",
            organism=organism_accession.accession,
            category="genome",
            file_path=f"/tmp/audit/{self.suffix}/organism.fasta",
            file_type=self.file_type,
            size=123,
        )
        stdout = StringIO()

        call_command("audit_legacy_fallback", limit=10, output_dir=self.output_dir.name, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("accession_source_new_relation\t1", output)
        self.assertIn("accession_source_no_files\t2", output)
        self.assertIn("overview_source_legacy_genomefile\t1", output)
        self.assertIn("overview_source_organism_fallback\t1", output)
        reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("legacy_fallback_report_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn(legacy_accession.accession, report)
        self.assertIn(organism_accession.accession, report)
        self.assertIn("organism_fallback", report)

    def test_audit_file_relations_supports_dataset_related_type(self):
        data_file = self.make_data_file("F", f"/tmp/audit/{self.suffix}/dataset.fasta")
        dataset = Dataset.objects.create(
            dataset_code=f"DS_{self.suffix}",
            dataset_name="Audit Dataset",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="dataset",
            related_id=str(dataset.id),
            related_code=dataset.dataset_code,
            file_role="raw",
        )
        stdout = StringIO()

        call_command("audit_file_relations", output_dir=self.output_dir.name, stdout=stdout)

        self.assertIn("broken_relation_count\t0", stdout.getvalue())

    def table_counts(self):
        return {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }
