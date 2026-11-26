from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from files.models import CoreAuditEvent, DataAsset, DataFile
from files.services.context_service import create_context, transition_context
from files.services.data_asset_service import (
    AssetContextInput,
    AssetFileInput,
    AssetRelationInput,
    DataAssetConflictError,
    DataAssetPermissionDenied,
    DataAssetServiceError,
    create_data_asset,
    transition_data_asset,
    update_data_asset_draft,
)
from files.services.project_service import add_project_member, create_project


class DataAssetServiceTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="asset-owner")
        self.manager = users.create_user(username="asset-manager")
        self.contributor = users.create_user(username="asset-contributor")
        self.viewer = users.create_user(username="asset-viewer")
        self.project = create_project(creator=self.owner, project_code="ASSET_PROJECT")
        add_project_member(
            project=self.project, actor=self.owner, user=self.manager, role="manager",
            reason="Manager appointed for tests",
        )
        add_project_member(project=self.project, actor=self.owner, user=self.contributor, role="contributor")
        add_project_member(project=self.project, actor=self.owner, user=self.viewer, role="viewer")
        self.file = DataFile.objects.create(
            file_code="ASSET_FILE", file_name="reads.fastq.gz",
            file_path="/not-used/reads.fastq.gz", file_size=10,
            sha256="a" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        self.sample = create_context(
            context_code="SAMPLE_CONTEXT", project=self.project,
            context_type_key="sample", profile_key="basic_sample", actor=self.owner,
        )
        transition_context(context=self.sample, actor=self.manager, action="activate")

    def create_reads(self, **overrides):
        values = {
            "asset_code": "READS_ASSET",
            "project": self.project,
            "data_type_key": "sequence",
            "profile_key": "raw_read_collection",
            "created_by": self.contributor,
            "metadata": {"library_layout": "paired", "platform": "Illumina"},
            "file_memberships": [AssetFileInput(self.file, "read_fastq", is_primary=True)],
            "context_links": [AssetContextInput(self.sample, "source_sample")],
        }
        values.update(overrides)
        return create_data_asset(**values)

    def test_draft_creation_uses_new_context_and_audit_only(self):
        asset = self.create_reads()

        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
        self.assertEqual(asset.context_links.get().context, self.sample)
        self.assertFalse(asset.accession_links.exists())
        self.assertEqual(
            CoreAuditEvent.objects.filter(asset=asset, event_type="asset_created").count(), 1
        )

    def test_incomplete_but_legal_draft_is_allowed_and_submit_is_not(self):
        asset = self.create_reads(
            asset_code="INCOMPLETE_DRAFT", file_memberships=[], context_links=[]
        )
        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
        with self.assertRaisesRegex(DataAssetServiceError, "requires at least"):
            transition_data_asset(asset=asset, actor=self.contributor, action="submit")
        asset.refresh_from_db()
        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)

    def test_draft_rejects_unknown_roles_and_cross_project_context(self):
        with self.assertRaisesRegex(DataAssetServiceError, "Unknown file role"):
            self.create_reads(
                asset_code="BAD_ROLE",
                file_memberships=[AssetFileInput(self.file, "unknown")],
            )
        other_owner = get_user_model().objects.create_user(username="other-owner")
        other_project = create_project(creator=other_owner, project_code="OTHER_PROJECT")
        other_context = create_context(
            context_code="OTHER_SAMPLE", project=other_project,
            context_type_key="sample", profile_key="basic_sample", actor=other_owner,
        )
        with self.assertRaises(DataAssetPermissionDenied):
            self.create_reads(
                asset_code="CROSS_CONTEXT",
                context_links=[AssetContextInput(other_context, "source_sample")],
            )

    def test_creator_and_manager_can_edit_but_viewer_cannot(self):
        asset = self.create_reads()
        update_data_asset_draft(asset=asset, actor=self.contributor, name="new name")
        update_data_asset_draft(asset=asset, actor=self.manager, description="reviewed")
        with self.assertRaises(DataAssetPermissionDenied):
            update_data_asset_draft(asset=asset, actor=self.viewer, name="forbidden")
        asset.refresh_from_db()
        self.assertEqual(asset.name, "new name")
        self.assertEqual(asset.description, "reviewed")
        self.assertEqual(
            CoreAuditEvent.objects.filter(asset=asset, event_type="asset_updated").count(), 2
        )

    def test_lifecycle_revalidates_and_writes_audit_atomically(self):
        asset = self.create_reads()
        transition_data_asset(asset=asset, actor=self.contributor, action="submit")
        transition_data_asset(asset=asset, actor=self.manager, action="approve")
        transition_data_asset(asset=asset, actor=self.owner, action="release")
        transition_data_asset(
            asset=asset, actor=self.owner, action="archive", reason="Superseded release"
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, DataAsset.STATUS_ARCHIVED)
        self.assertEqual(
            list(CoreAuditEvent.objects.filter(asset=asset).values_list("event_type", flat=True))[-4:],
            ["asset_submitted", "asset_approved", "asset_released", "asset_archived"],
        )

    def test_frozen_asset_requires_return_before_edit(self):
        asset = self.create_reads()
        transition_data_asset(asset=asset, actor=self.contributor, action="submit")
        with self.assertRaises(DataAssetConflictError):
            update_data_asset_draft(asset=asset, actor=self.manager, name="blocked")
        transition_data_asset(
            asset=asset, actor=self.manager, action="return", reason="Metadata correction"
        )
        update_data_asset_draft(asset=asset, actor=self.contributor, name="corrected")

    def test_uses_reference_status_is_checked_again_at_submit_and_release(self):
        reference_file = DataFile.objects.create(
            file_code="REFERENCE_FILE", file_name="genome.fasta",
            file_path="/not-used/genome.fasta", file_size=10,
            sha256="b" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        reference = create_data_asset(
            asset_code="REFERENCE_ASSET", project=self.project,
            data_type_key="sequence", profile_key="reference_genome",
            created_by=self.owner,
            file_memberships=[AssetFileInput(reference_file, "genome_fasta")],
        )
        table_file = DataFile.objects.create(
            file_code="TABLE_FILE", file_name="table.tsv",
            file_path="/not-used/table.tsv", file_size=10,
            sha256="c" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        table = create_data_asset(
            asset_code="TABLE_ASSET", project=self.project,
            data_type_key="table", profile_key="research_table", created_by=self.owner,
            file_memberships=[AssetFileInput(table_file, "primary_table")],
            asset_relations=[AssetRelationInput(reference, "uses_reference")],
        )
        with self.assertRaisesRegex(DataAssetServiceError, "approved reference"):
            transition_data_asset(asset=table, actor=self.owner, action="submit")
        reference.status = DataAsset.STATUS_APPROVED
        reference.save(update_fields=["status"])
        transition_data_asset(asset=table, actor=self.owner, action="submit")
        transition_data_asset(asset=table, actor=self.manager, action="approve")
        with self.assertRaisesRegex(DataAssetServiceError, "released reference"):
            transition_data_asset(asset=table, actor=self.owner, action="release")

    def test_duplicate_code_returns_stable_conflict(self):
        self.create_reads(asset_code="DUPLICATE_ASSET")
        with self.assertRaises(DataAssetConflictError):
            self.create_reads(asset_code="DUPLICATE_ASSET")

    def test_asset_transition_rolls_back_when_audit_append_fails(self):
        asset = self.create_reads(asset_code="ASSET_AUDIT_ROLLBACK")
        with patch(
            "files.services.data_asset_service.append_core_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ), self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            transition_data_asset(asset=asset, actor=self.contributor, action="submit")
        asset.refresh_from_db()
        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
