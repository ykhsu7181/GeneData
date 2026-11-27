import hashlib
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from files.management.data_asset_command_support import profile_assets
from files.models import (
    AssetFileMembership,
    CoreAuditEvent,
    DataAsset,
    DataFile,
    Project,
    ProjectMembership,
)
from files.services.data_asset_auxiliary_service import (
    DataAssetAuxiliaryError,
    DataAssetAuxiliaryPermissionDenied,
    register_generated_auxiliary_file,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class DataAssetAuxiliaryServiceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = get_user_model().objects.create_user(username="aux-owner")
        self.viewer = get_user_model().objects.create_user(username="aux-viewer")
        self.project = Project.objects.create(project_code="AUX_PROJECT")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMembership.ROLE_VIEWER,
            created_by=self.owner,
        )
        self.registry = load_data_asset_registry()
        profile = self.registry.resolve_current_asset_profile("sequence", "reference_genome")
        self.asset = DataAsset.objects.create(
            asset_code="AUX_REF",
            project=self.project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
            created_by=self.owner,
            published_at=timezone.now(),
        )
        self.target = self.root / "reference.fasta.fai"
        self.target.write_bytes(b"chr1\t4\t6\t4\t5\n")

    def register(self, **kwargs):
        options = {
            "asset": self.asset,
            "actor": self.owner,
            "file_role": "fasta_index",
            "path": self.target,
            "registry": self.registry,
        }
        options.update(kwargs)
        return register_generated_auxiliary_file(**options)

    def test_owner_registers_released_auxiliary_with_audit(self):
        data_file = self.register()
        membership = AssetFileMembership.objects.get(asset=self.asset, file_role="fasta_index")
        self.assertEqual(membership.data_file, data_file)
        event = CoreAuditEvent.objects.get(asset=self.asset, event_type="asset_updated")
        self.assertTrue(event.before_digest)
        self.assertTrue(event.after_digest)
        self.assertNotEqual(event.before_digest, event.after_digest)

    def test_viewer_cannot_register_auxiliary(self):
        with self.assertRaises(DataAssetAuxiliaryPermissionDenied):
            self.register(actor=self.viewer)
        self.assertFalse(DataFile.objects.filter(file_path=str(self.target)).exists())

    def test_profile_assets_excludes_viewer_from_maintenance_selection(self):
        assets, _ = profile_assets(
            user=self.viewer, family="reference_genome", asset_codes=[self.asset.asset_code]
        )
        self.assertEqual(assets, [])

    def test_existing_path_with_another_identity_fails_without_mutation(self):
        existing = DataFile.objects.create(
            file_code="UNRELATED_FILE",
            file_name=self.target.name,
            file_path=str(self.target),
            file_size=1,
            sha256=hashlib.sha256(b"x").hexdigest(),
        )
        with self.assertRaisesRegex(DataAssetAuxiliaryError, "already owned"):
            self.register()
        existing.refresh_from_db()
        self.assertEqual(existing.file_code, "UNRELATED_FILE")
        self.assertEqual(existing.file_size, 1)

    def test_existing_code_with_another_path_fails_without_mutation(self):
        other_path = self.root / "other.fai"
        other_path.write_bytes(b"old")
        existing = DataFile.objects.create(
            file_code=f"JB_{self.asset.pk}_fasta_index",
            file_name=other_path.name,
            file_path=str(other_path),
        )
        with self.assertRaisesRegex(DataAssetAuxiliaryError, "conflicts"):
            self.register()
        existing.refresh_from_db()
        self.assertEqual(existing.file_path, str(other_path))

    def test_core_role_and_frozen_review_status_are_rejected(self):
        with self.assertRaisesRegex(DataAssetAuxiliaryError, "auxiliary role"):
            self.register(file_role="genome_fasta")
        self.asset.status = DataAsset.STATUS_APPROVED
        self.asset.save(update_fields=["status", "updated_at"])
        with self.assertRaisesRegex(DataAssetAuxiliaryError, "draft or released"):
            self.register()
