import csv
import hashlib
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from files.models import (
    Accession,
    Annotation,
    Assembly,
    AssetFileMembership,
    DataAsset,
    DataAssetAccession,
    DataAssetAnnotation,
    DataAssetAssembly,
    DataAssetSample,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Project,
    Species,
)
from files.management.commands.audit_dataset_dataasset_mapping_dry_run import Command


class DatasetDataAssetMappingDryRunTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.output = self.root / "reports"
        self.species = Species.objects.create(species_code="T4_SPECIES")
        self.project = Project.objects.create(project_code="T4_PROJECT")
        self.accession = Accession.objects.create(
            accession="T4_ACCESSION", species=self.species
        )
        self.dataset = Dataset.objects.create(
            dataset_code="T4_LEGACY_GENOME",
            dataset_type="genome",
            project=self.project,
            species=self.species,
        )
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
            relation_role="primary",
            source="t4-test",
        )
        self.transcriptome = Dataset.objects.create(
            dataset_code="T4_TRANSCRIPTOME_METADATA",
            dataset_type="transcriptome",
            project=self.project,
        )
        self.hic = Dataset.objects.create(
            dataset_code="T4_HIC_METADATA",
            dataset_type="hic",
            project=self.project,
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="T4 assembly",
            assembly_code="T4_ASSEMBLY",
            assembly_accession="GCA_T4",
            assembly_method="T4 assembler",
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="T4 annotation",
        )
        self.fasta = self.make_file("T4_FASTA", b">chr1\nACGT\n")
        self.index = self.make_file("T4_FAI", b"chr1\t4\t6\t4\t5\n")
        self.gff = self.make_file("T4_GFF", b"##gff-version 3\n")
        self.relate(self.fasta, "assembly", self.assembly.id, "genome_fasta", True)
        self.relate(self.index, "assembly", self.assembly.id, "fai")
        self.relate(self.gff, "annotation", self.annotation.id, "gff")

    def make_file(self, code, content, *, dataset=None):
        path = self.root / f"{code}.dat"
        path.write_bytes(content)
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            dataset=dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
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

    def run_audit(self):
        stdout = StringIO()
        call_command(
            "audit_dataset_dataasset_mapping_dry_run",
            "--output-dir",
            str(self.output),
            stdout=stdout,
        )
        return stdout.getvalue()

    def read_rows(self, name):
        path = self.output / f"dataasset_t4_{name}.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_professional_entity_candidate_reports_are_read_only_and_explainable(self):
        before = self.snapshot()

        stdout = self.run_audit()

        self.assertEqual(before, self.snapshot())
        self.assertIn("mode\tREAD_ONLY_DRY_RUN", stdout)
        self.assertEqual(
            {path.name for path in self.output.glob("*.tsv")},
            {
                "dataasset_t4_summary.tsv",
                "dataasset_t4_assets.tsv",
                "dataasset_t4_memberships.tsv",
                "dataasset_t4_contexts.tsv",
                "dataasset_t4_exclusions.tsv",
                "dataasset_t4_conflicts.tsv",
                "dataasset_t4_permissions.tsv",
                "dataasset_t4_checksums.tsv",
            },
        )

        assets = self.read_rows("assets")
        self.assertEqual(len(assets), 1)
        asset = assets[0]
        self.assertEqual(asset["candidate_key"], f"assembly:{self.assembly.id}")
        self.assertEqual(asset["proposed_asset_code"], "T4_ASSEMBLY")
        self.assertEqual(asset["supporting_dataset_codes"], "T4_LEGACY_GENOME")
        self.assertEqual(asset["data_type_key"], "sequence")
        self.assertEqual(asset["profile_key"], "reference_genome")
        self.assertEqual(asset["mapping_status"], "ready")
        self.assertEqual(asset["core_file_count"], "1")
        self.assertEqual(asset["auxiliary_file_count"], "1")
        self.assertIn('"assembly_accession":"GCA_T4"', asset["proposed_metadata"])

        memberships = {row["file_code"]: row for row in self.read_rows("memberships")}
        self.assertEqual(set(memberships), {"T4_FASTA", "T4_FAI"})
        self.assertEqual(memberships["T4_FASTA"]["proposed_file_role"], "genome_fasta")
        self.assertEqual(memberships["T4_FASTA"]["file_role_class"], "core")
        self.assertEqual(memberships["T4_FASTA"]["proposed_is_primary"], "1")
        self.assertEqual(memberships["T4_FAI"]["proposed_file_role"], "fasta_index")

        contexts = self.read_rows("contexts")
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["context_type"], "assembly")
        self.assertEqual(contexts[0]["context_code"], "T4_ASSEMBLY")

        exclusions = {row["dataset_code"]: row for row in self.read_rows("exclusions")}
        for code in ("T4_TRANSCRIPTOME_METADATA", "T4_HIC_METADATA"):
            self.assertEqual(exclusions[code]["mapping_status"], "excluded_not_asset")
            self.assertEqual(exclusions[code]["reason"], "metadata_only_external_reference")

        conflicts = self.read_rows("conflicts")
        gff_conflict = next(row for row in conflicts if row["entity_code"] == "T4_GFF")
        self.assertEqual(gff_conflict["issue"], "profile_not_registered")
        self.assertIn("feature/genome_annotation", gff_conflict["evidence"])
        self.assertNotIn("T4_GFF", memberships)

        checksums = {row["file_code"]: row for row in self.read_rows("checksums")}
        self.assertEqual(checksums["T4_FASTA"]["physical_status"], "present")
        self.assertEqual(checksums["T4_FASTA"]["size_status"], "verified")
        self.assertEqual(checksums["T4_FASTA"]["checksum_status"], "verified")

        permissions = {row["file_code"]: row for row in self.read_rows("permissions")}
        self.assertEqual(permissions["T4_FASTA"]["permission_comparison"], "same")
        self.assertEqual(permissions["T4_GFF"]["permission_comparison"], "not_evaluated")

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["assets_total"], 1)
        self.assertEqual(summary["exclusion:metadata_only_external_reference"], 2)
        self.assertEqual(summary["target_table_available"], 1)

        for path in self.output.glob("*.tsv"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn(str(self.root), content)
            self.assertNotIn("file_path", content)
            self.assertNotIn("file_name", content)

    def test_physical_or_checksum_failure_blocks_candidate(self):
        self.fasta.sha256 = "0" * 64
        self.fasta.save(update_fields=["sha256"])

        self.run_audit()

        asset = self.read_rows("assets")[0]
        self.assertEqual(asset["mapping_status"], "blocked")
        self.assertIn("blocked_file_membership", asset["issues"])
        checksum = next(
            row for row in self.read_rows("checksums") if row["file_code"] == "T4_FASTA"
        )
        self.assertEqual(checksum["checksum_status"], "mismatch")
        self.assertEqual(checksum["mapping_status"], "blocked")

    def test_multiple_assembly_contexts_are_blocked_without_guessing(self):
        second = Assembly.objects.create(
            accession=self.accession,
            name="T4 assembly second",
            assembly_code="T4_ASSEMBLY_SECOND",
        )
        self.relate(self.fasta, "assembly", second.id, "genome_fasta")

        self.run_audit()

        assets = self.read_rows("assets")
        self.assertEqual(len(assets), 2)
        self.assertTrue(all(row["mapping_status"] == "blocked" for row in assets))
        fasta_memberships = [
            row for row in self.read_rows("memberships") if row["file_code"] == "T4_FASTA"
        ]
        self.assertEqual(len(fasta_memberships), 2)
        self.assertTrue(
            all("file_has_multiple_assembly_contexts" in row["issues"] for row in fasta_memberships)
        )

    def test_multiple_supporting_datasets_block_project_and_identity_inference(self):
        second_dataset = Dataset.objects.create(
            dataset_code="T4_SECOND_GENOME",
            dataset_type="genome",
            project=self.project,
        )
        DatasetAccession.objects.create(
            dataset=second_dataset,
            accession=self.accession,
            relation_role="reference",
        )

        self.run_audit()

        asset = self.read_rows("assets")[0]
        self.assertEqual(asset["mapping_status"], "blocked")
        self.assertIn("multiple_supporting_genome_datasets", asset["issues"])

    def test_permission_widening_is_blocked(self):
        self.dataset.status = DataAsset.STATUS_RELEASED
        self.dataset.visibility = DataAsset.VISIBILITY_PUBLIC
        self.dataset.save(update_fields=["status", "visibility"])

        self.run_audit()

        asset = self.read_rows("assets")[0]
        self.assertEqual(asset["mapping_status"], "blocked")
        self.assertIn("released_candidate_requires_release_workflow", asset["issues"])
        permission = next(
            row
            for row in self.read_rows("permissions")
            if row["file_code"] == "T4_FASTA"
        )
        self.assertEqual(permission["permission_comparison"], "widening")
        self.assertEqual(permission["mapping_status"], "blocked")
        self.assertIn("permission_widening", permission["issues"])

    def test_archive_payload_is_left_for_inspection_without_profile_guessing(self):
        self.assertIsNone(Command.unregistered_target_profile("codon_archive"))
        self.assertIsNone(Command.unregistered_target_profile("transcriptome_archive"))
        self.assertIsNone(Command.unregistered_target_profile("transcriptome_result"))
        self.assertEqual(
            Command.unregistered_target_profile("expression_matrix"),
            "matrix/expression_matrix",
        )
        archive = self.make_file("T4_CODON_ARCHIVE", b"not-a-real-archive")
        self.relate(archive, "accession", self.accession.id, "codon_archive")

        self.run_audit()

        conflicts = [
            row
            for row in self.read_rows("conflicts")
            if row["entity_code"] == "T4_CODON_ARCHIVE"
        ]
        self.assertEqual(
            {row["issue"] for row in conflicts},
            {"archive_inspection_required"},
        )
        self.assertNotIn(
            "T4_CODON_ARCHIVE",
            {row["file_code"] for row in self.read_rows("memberships")},
        )

    def test_duplicate_recorded_content_is_reported_without_automatic_merge(self):
        duplicate = self.make_file("T4_FASTA_COPY", b">chr1\nACGT\n")
        self.relate(duplicate, "accession", self.accession.id, "genome_fasta")

        self.run_audit()

        duplicate_conflicts = [
            row
            for row in self.read_rows("conflicts")
            if row["issue"] == "duplicate_content_checksum"
        ]
        self.assertEqual(
            {row["entity_code"] for row in duplicate_conflicts},
            {"T4_FASTA", "T4_FASTA_COPY"},
        )
        self.assertNotIn(
            "T4_FASTA_COPY",
            {row["file_code"] for row in self.read_rows("memberships")},
        )

    def test_unverified_matching_recorded_checksums_are_not_content_duplicates(self):
        mismatched = self.make_file("T4_STALE_CHECKSUM", b"different-content")
        mismatched.sha256 = self.fasta.sha256
        mismatched.save(update_fields=["sha256"])

        self.run_audit()

        conflicts = self.read_rows("conflicts")
        recorded = {
            row["entity_code"]
            for row in conflicts
            if row["issue"] == "duplicate_recorded_checksum"
        }
        content = {
            row["entity_code"]
            for row in conflicts
            if row["issue"] == "duplicate_content_checksum"
        }
        self.assertEqual(recorded, {"T4_FASTA", "T4_STALE_CHECKSUM"})
        self.assertNotIn("T4_STALE_CHECKSUM", content)

    def test_dataset_with_accession_file_evidence_is_not_metadata_only(self):
        transcriptome_accession = Accession.objects.create(
            accession="T4_TRANSCRIPTOME_ACCESSION", species=self.species
        )
        DatasetAccession.objects.create(
            dataset=self.transcriptome,
            accession=transcriptome_accession,
            relation_role="primary",
        )
        reads = self.make_file("T4_TRANSCRIPTOME_READS", b"@r1\nACGT\n+\n!!!!\n")
        self.relate(reads, "accession", transcriptome_accession.id, "raw_reads")

        self.run_audit()

        exclusion = next(
            row
            for row in self.read_rows("exclusions")
            if row["dataset_code"] == self.transcriptome.dataset_code
        )
        self.assertEqual(exclusion["mapping_status"], "review_required")
        self.assertEqual(exclusion["reason"], "no_professional_payload_candidate")
        self.assertEqual(exclusion["has_file_relation_evidence"], "1")

    def test_asset_code_longer_than_model_limit_is_blocked(self):
        self.assembly.assembly_code = "A" * 101
        self.assembly.save(update_fields=["assembly_code"])

        self.run_audit()

        asset = self.read_rows("assets")[0]
        self.assertEqual(asset["mapping_status"], "blocked")
        self.assertIn("asset_code_too_long", asset["issues"])
        conflict = next(
            row
            for row in self.read_rows("conflicts")
            if row["issue"] == "asset_code_too_long"
        )
        self.assertEqual(conflict["severity"], "blocked")

    def test_refuses_to_overwrite_existing_reports(self):
        self.run_audit()

        with self.assertRaises(CommandError):
            self.run_audit()

    def test_runs_before_dataasset_tables_are_deployed(self):
        table_names = [
            name
            for name in connection.introspection.table_names()
            if name not in {"data_asset", "data_asset_accession", "asset_file_membership"}
        ]
        with patch.object(connection.introspection, "table_names", return_value=table_names):
            self.run_audit()

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["target_table_available"], 0)

    @staticmethod
    def snapshot():
        return (
            Dataset.objects.count(),
            DataAsset.objects.count(),
            AssetFileMembership.objects.count(),
            DataAssetAccession.objects.count(),
            DataAssetSample.objects.count(),
            DataAssetAssembly.objects.count(),
            DataAssetAnnotation.objects.count(),
            DataFile.objects.count(),
            FileRelation.objects.count(),
        )


class DatasetDataAssetMappingTransactionBoundaryTests(TransactionTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        content = b"physical-checksum-content"
        path = self.root / "checksum.dat"
        path.write_bytes(content)
        DataFile.objects.create(
            file_code="T4_TRANSACTION_CHECKSUM",
            file_name=path.name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
        )

    def test_physical_hashing_runs_outside_database_transaction(self):
        transaction_states = []
        original_sha256 = Command.sha256

        def observe_transaction(path):
            transaction_states.append(connection.in_atomic_block)
            return original_sha256(path)

        with patch.object(Command, "sha256", side_effect=observe_transaction):
            call_command(
                "audit_dataset_dataasset_mapping_dry_run",
                "--output-dir",
                str(self.root / "reports"),
                stdout=StringIO(),
            )

        self.assertEqual(transaction_states, [False])
