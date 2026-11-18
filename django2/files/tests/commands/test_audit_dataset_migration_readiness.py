import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import (
    Accession,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Project,
    Species,
)


class AuditDatasetMigrationReadinessTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.output = Path(self.temporary_directory.name) / "reports"

        species = Species.objects.create(species_code="ORYZA")
        project = Project.objects.create(project_code="RICE")
        self.primary = Dataset.objects.create(
            dataset_code="DS_PRIMARY",
            dataset_type="genome",
            project=project,
            species=species,
            bioproject_accession="PRJ1",
            version="v1",
            visibility="public",
            status="released",
        )
        self.secondary = Dataset.objects.create(
            dataset_code="DS_SECONDARY",
            dataset_type="genome",
            project=project,
            species=species,
            bioproject_accession="PRJ1",
            version="v1",
        )
        self.incomplete = Dataset.objects.create(dataset_code="DS_INCOMPLETE")

        accession_a = Accession.objects.create(accession="ACC_A", species=species)
        accession_b = Accession.objects.create(accession="ACC_B", species=species)
        DatasetAccession.objects.create(
            dataset=self.primary, accession=accession_a, relation_role="primary"
        )
        DatasetAccession.objects.create(
            dataset=self.primary, accession=accession_b, relation_role="reference"
        )
        DatasetAccession.objects.create(
            dataset=self.secondary, accession=accession_a, relation_role="derived"
        )

        aligned = self.make_file("ALIGNED", self.primary)
        self.relate(aligned, self.primary)
        self.make_file("DIRECT_ONLY", self.primary)
        relation_only = self.make_file("RELATION_ONLY")
        self.relate(relation_only, self.secondary)
        mismatch = self.make_file("MISMATCH", self.primary)
        self.relate(mismatch, self.secondary)
        multiple = self.make_file("MULTIPLE", self.primary)
        self.relate(multiple, self.primary, role="primary")
        self.relate(multiple, self.secondary, role="reference")
        invalid = self.make_file("INVALID")
        FileRelation.objects.create(
            file=invalid,
            related_type="dataset",
            related_id="not-an-id",
            file_role="other",
        )
        self.make_file("DATASETLESS")

    @staticmethod
    def make_file(code, dataset=None):
        return DataFile.objects.create(
            file_code=code,
            file_name=f"{code}.dat",
            file_path=f"/private/secret/{code}.dat",
            dataset=dataset,
        )

    @staticmethod
    def relate(data_file, dataset, role="other"):
        return FileRelation.objects.create(
            file=data_file,
            related_type="dataset",
            related_id=str(dataset.id),
            related_code=dataset.dataset_code,
            file_role=role,
        )

    def read_rows(self, name):
        path = self.output / f"dataset_t0_{name}.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_writes_complete_read_only_reports_without_physical_paths(self):
        before = self.snapshot()
        stdout = StringIO()

        call_command(
            "audit_dataset_migration_readiness",
            "--output-dir",
            str(self.output),
            stdout=stdout,
        )

        self.assertEqual(before, self.snapshot())
        self.assertIn("mode\tREAD_ONLY", stdout.getvalue())
        self.assertEqual(
            set(path.name for path in self.output.glob("*.tsv")),
            {
                "dataset_t0_summary.tsv",
                "dataset_t0_datasets.tsv",
                "dataset_t0_accessions.tsv",
                "dataset_t0_file_links.tsv",
                "dataset_t0_duplicates.tsv",
            },
        )

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["dataset_total"], 3)
        self.assertEqual(summary["dataset_missing_project"], 1)
        self.assertEqual(summary["dataset_accessions_multiple"], 1)
        self.assertEqual(summary["datafile_link_datasetless"], 1)
        self.assertEqual(summary["datafile_link_direct_only"], 1)
        self.assertEqual(summary["datafile_link_relation_only"], 1)
        self.assertEqual(summary["datafile_link_aligned"], 1)
        self.assertEqual(summary["datafile_link_conflict"], 3)
        self.assertEqual(summary["dataset_relation_invalid_total"], 1)
        self.assertEqual(summary["duplicate_group_total"], 2)

        datasets = {row["dataset_code"]: row for row in self.read_rows("datasets")}
        self.assertIn("multiple_accessions", datasets["DS_PRIMARY"]["issues"])
        self.assertIn("missing_project", datasets["DS_INCOMPLETE"]["issues"])
        self.assertEqual(datasets["DS_PRIMARY"]["multi_dataset_file_count"], "2")

        files = {row["file_code"]: row for row in self.read_rows("file_links")}
        self.assertEqual(files["ALIGNED"]["classification"], "aligned")
        self.assertEqual(files["MISMATCH"]["classification"], "conflict")
        self.assertIn("multiple_effective_datasets", files["MULTIPLE"]["issues"])
        self.assertIn("invalid_dataset_relation", files["INVALID"]["issues"])

        for path in self.output.glob("*.tsv"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("/private/secret", content)
            self.assertNotIn("file_path", content)
            self.assertNotIn("dataset_name", content)

    def test_refuses_to_overwrite_existing_reports(self):
        call_command(
            "audit_dataset_migration_readiness",
            "--output-dir",
            str(self.output),
            stdout=StringIO(),
        )

        with self.assertRaises(CommandError):
            call_command(
                "audit_dataset_migration_readiness",
                "--output-dir",
                str(self.output),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    @staticmethod
    def snapshot():
        return (
            Dataset.objects.count(),
            DatasetAccession.objects.count(),
            DataFile.objects.count(),
            FileRelation.objects.count(),
        )
