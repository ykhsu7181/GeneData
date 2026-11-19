import csv
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from files.models import (
    Accession,
    AssetFileMembership,
    DataAsset,
    DataAssetAccession,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Project,
    Species,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class DatasetDataAssetMappingDryRunTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.output = Path(self.temporary_directory.name) / "reports"
        self.user = get_user_model().objects.create_user(username="t4-user")
        self.species = Species.objects.create(species_code="T4_SPECIES")
        self.project = Project.objects.create(project_code="T4_PROJECT")
        self.accession = Accession.objects.create(
            accession="T4_ACCESSION", species=self.species
        )

        self.ready = self.make_dataset(
            "T4_READY",
            project=self.project,
            dataset_name="T4 ready dataset",
            description="T4 mapping description",
            bioproject_accession="PRJ-T4",
        )
        self.released = self.make_dataset(
            "T4_RELEASED",
            project=self.project,
            status="released",
            visibility="public",
        )
        self.missing_project = self.make_dataset("T4_NO_PROJECT")
        self.unsupported = self.make_dataset(
            "T4_TRANSCRIPTOME",
            project=self.project,
            dataset_type="transcriptome",
        )
        self.conflict = self.make_dataset("T4_CONFLICT", project=self.project)
        for dataset in (self.ready, self.released, self.conflict):
            DatasetAccession.objects.create(
                dataset=dataset,
                accession=self.accession,
                relation_role="primary",
                source="t4-manifest",
            )

        primary_file = self.make_file("T4_PRIMARY", dataset=self.ready)
        self.relate(primary_file, "dataset", self.ready.id, "genome_fasta", True)
        index_file = self.make_file("T4_INDEX")
        self.relate(index_file, "accession", self.accession.id, "genome_index")
        annotation_file = self.make_file("T4_ANNOTATION")
        self.relate(annotation_file, "accession", self.accession.id, "annotation")

        profile = load_data_asset_registry().get_profile("sequence", "reference_genome")
        DataAsset.objects.create(
            asset_code=self.conflict.dataset_code,
            name="different existing name",
            project=self.project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            created_by=self.user,
        )

    def make_dataset(
        self,
        code,
        *,
        project=None,
        dataset_type="genome",
        status="draft",
        visibility="private",
        dataset_name=None,
        description=None,
        bioproject_accession=None,
    ):
        return Dataset.objects.create(
            dataset_code=code,
            dataset_type=dataset_type,
            project=project,
            species=self.species,
            dataset_name=dataset_name,
            description=description,
            bioproject_accession=bioproject_accession,
            status=status,
            visibility=visibility,
        )

    @staticmethod
    def make_file(code, dataset=None):
        return DataFile.objects.create(
            file_code=code,
            file_name=f"{code}.dat",
            file_path=f"/private/secret/{code}.dat",
            dataset=dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
            sha256="a" * 64,
        )

    @staticmethod
    def relate(data_file, related_type, related_id, role, is_primary=False):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=is_primary,
        )

    def read_rows(self, name):
        path = self.output / f"dataasset_t4_{name}.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_writes_explainable_read_only_mapping_without_physical_paths(self):
        before = self.snapshot()
        stdout = StringIO()

        call_command(
            "audit_dataset_dataasset_mapping_dry_run",
            "--output-dir",
            str(self.output),
            stdout=stdout,
        )

        self.assertEqual(before, self.snapshot())
        self.assertIn("mode\tREAD_ONLY_DRY_RUN", stdout.getvalue())
        self.assertEqual(
            {path.name for path in self.output.glob("*.tsv")},
            {
                "dataasset_t4_summary.tsv",
                "dataasset_t4_assets.tsv",
                "dataasset_t4_accessions.tsv",
                "dataasset_t4_memberships.tsv",
                "dataasset_t4_issues.tsv",
            },
        )

        assets = {row["dataset_code"]: row for row in self.read_rows("assets")}
        self.assertEqual(assets["T4_READY"]["data_type_key"], "sequence")
        self.assertEqual(assets["T4_READY"]["profile_key"], "reference_genome")
        self.assertEqual(assets["T4_READY"]["schema_version"], "2.0.0")
        self.assertEqual(assets["T4_READY"]["mapping_status"], "ready")
        self.assertEqual(assets["T4_READY"]["proposed_name"], "T4 ready dataset")
        self.assertEqual(
            assets["T4_READY"]["proposed_description"], "T4 mapping description"
        )
        self.assertEqual(
            assets["T4_READY"]["proposed_metadata"],
            '{"external_identifiers":{"bioproject":"PRJ-T4"}}',
        )
        self.assertEqual(
            assets["T4_READY"]["species_context_resolution"],
            "accession_context",
        )
        self.assertEqual(assets["T4_RELEASED"]["mapping_status"], "review")
        self.assertIn(
            "released_asset_requires_published_at", assets["T4_RELEASED"]["issues"]
        )
        self.assertEqual(assets["T4_NO_PROJECT"]["mapping_status"], "blocked")
        self.assertIn("missing_project", assets["T4_NO_PROJECT"]["issues"])
        self.assertIn(
            "unregistered_dataset_type", assets["T4_TRANSCRIPTOME"]["issues"]
        )
        self.assertEqual(assets["T4_CONFLICT"]["mapping_action"], "existing_conflict")

        memberships = {
            row["file_code"]: row for row in self.read_rows("memberships")
        }
        self.assertEqual(memberships["T4_PRIMARY"]["dataset_code"], "T4_READY")
        self.assertEqual(
            memberships["T4_PRIMARY"]["proposed_file_role"], "genome_fasta"
        )
        self.assertEqual(memberships["T4_PRIMARY"]["proposed_is_primary"], "1")
        self.assertEqual(memberships["T4_INDEX"]["proposed_file_role"], "fasta_index")
        self.assertEqual(memberships["T4_ANNOTATION"]["dataset_code"], "")
        self.assertIn(
            "no_automatic_dataset_mapping", memberships["T4_ANNOTATION"]["issues"]
        )

        accessions = self.read_rows("accessions")
        ready_accession = next(
            row for row in accessions if row["dataset_code"] == "T4_READY"
        )
        self.assertEqual(ready_accession["proposed_primary_slot"], "1")
        self.assertEqual(ready_accession["source"], "t4-manifest")

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["dataset_total"], 5)
        self.assertEqual(summary["target_table_available"], 1)
        self.assertGreaterEqual(summary["asset_status:blocked"], 3)

        for path in self.output.glob("*.tsv"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("/private/secret", content)
            self.assertNotIn("file_path", content)
            self.assertNotIn("file_name", content)

    def test_refuses_to_overwrite_existing_reports(self):
        call_command(
            "audit_dataset_dataasset_mapping_dry_run",
            "--output-dir",
            str(self.output),
            stdout=StringIO(),
        )

        with self.assertRaises(CommandError):
            call_command(
                "audit_dataset_dataasset_mapping_dry_run",
                "--output-dir",
                str(self.output),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_runs_before_dataasset_tables_are_deployed(self):
        table_names = [
            name
            for name in connection.introspection.table_names()
            if name not in {"data_asset", "data_asset_accession", "asset_file_membership"}
        ]
        with patch.object(
            connection.introspection,
            "table_names",
            return_value=table_names,
        ):
            call_command(
                "audit_dataset_dataasset_mapping_dry_run",
                "--output-dir",
                str(self.output),
                stdout=StringIO(),
            )

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["target_table_available"], 0)

    def test_multiple_primary_candidates_do_not_downgrade_blocked_members(self):
        for suffix in ("A", "B"):
            data_file = self.make_file(f"T4_BLOCKED_PRIMARY_{suffix}")
            self.relate(
                data_file,
                "dataset",
                self.missing_project.id,
                "genome_fasta",
                True,
            )

        call_command(
            "audit_dataset_dataasset_mapping_dry_run",
            "--output-dir",
            str(self.output),
            stdout=StringIO(),
        )

        memberships = {
            row["file_code"]: row for row in self.read_rows("memberships")
        }
        for suffix in ("A", "B"):
            row = memberships[f"T4_BLOCKED_PRIMARY_{suffix}"]
            self.assertEqual(row["mapping_status"], "blocked")
            self.assertIn("asset_mapping_blocked", row["issues"])
            self.assertIn("multiple_primary_file_candidates", row["issues"])

    @staticmethod
    def snapshot():
        return (
            Dataset.objects.count(),
            DatasetAccession.objects.count(),
            DataAsset.objects.count(),
            DataAssetAccession.objects.count(),
            AssetFileMembership.objects.count(),
            DataFile.objects.count(),
            FileRelation.objects.count(),
        )
