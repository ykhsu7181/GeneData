from django.test import TestCase
from django.utils import timezone

from files.models import AssetFileMembership, DataAccessToken, DataAsset, DataFile, Project
from files.services.data_asset_access_service import resolve_data_asset_file_access
from files.services.datafile_access_service import ACTION_CONTENT, ACTION_METADATA


class DataAssetAccessServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(project_code="PROJECT_ASSET_ACCESS")
        self.asset = DataAsset.objects.create(
            asset_code="ASSET_ACCESS",
            project=self.project,
            data_type_key="sequence",
            profile_key="reference_genome",
            schema_version="2.0.0",
            schema_digest="a" * 64,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
            published_at=timezone.now(),
        )
        self.data_file = DataFile.objects.create(
            file_code="FILE_ASSET_ACCESS",
            file_name="access.fasta",
            file_path="/not-used/access.fasta",
            is_current=True,
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
            sha256="b" * 64,
        )
        AssetFileMembership.objects.create(
            asset=self.asset,
            data_file=self.data_file,
            file_role="genome_fasta",
            is_primary=True,
            primary_slot=1,
        )

    def issue_token(self, *, scopes, access_tier=DataAccessToken.ACCESS_TIER_PUBLIC):
        token, _raw = DataAccessToken.issue(
            name=f"asset-token-{DataAccessToken.objects.count()}",
            scopes=scopes,
            access_tier=access_tier,
        )
        return token

    def test_public_released_asset_and_file_allow_metadata(self):
        decision = resolve_data_asset_file_access(
            self.asset,
            self.data_file,
            action=ACTION_METADATA,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "asset_and_file_authorized")

    def test_draft_or_incomplete_asset_fails_closed(self):
        self.asset.status = DataAsset.STATUS_DRAFT
        self.asset.save(update_fields=["status"])
        self.assertEqual(
            resolve_data_asset_file_access(self.asset, self.data_file).reason,
            "asset_not_released",
        )

        self.asset.status = DataAsset.STATUS_RELEASED
        self.asset.published_at = None
        self.asset.save(update_fields=["status", "published_at"])
        self.assertEqual(
            resolve_data_asset_file_access(self.asset, self.data_file).reason,
            "asset_release_incomplete",
        )

    def test_asset_never_loosens_private_file_policy(self):
        self.data_file.access_level = DataFile.ACCESS_LEVEL_PRIVATE
        self.data_file.save(update_fields=["access_level"])

        decision = resolve_data_asset_file_access(self.asset, self.data_file)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PRIVATE)

    def test_private_asset_denies_public_file(self):
        self.asset.visibility = DataAsset.VISIBILITY_PRIVATE
        self.asset.save(update_fields=["visibility"])

        decision = resolve_data_asset_file_access(self.asset, self.data_file)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "asset_or_file_private")

    def test_internal_asset_requires_internal_token_scope(self):
        self.asset.visibility = DataAsset.VISIBILITY_INTERNAL
        self.asset.save(update_fields=["visibility"])
        public_token = self.issue_token(scopes=[DataAccessToken.SCOPE_FILE_READ])
        internal_token = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        anonymous = resolve_data_asset_file_access(
            self.asset, self.data_file, action=ACTION_CONTENT
        )
        public = resolve_data_asset_file_access(
            self.asset,
            self.data_file,
            principal=public_token,
            action=ACTION_CONTENT,
        )
        internal = resolve_data_asset_file_access(
            self.asset,
            self.data_file,
            principal=internal_token,
            action=ACTION_CONTENT,
        )

        self.assertEqual(anonymous.reason, "authentication_required")
        self.assertEqual(public.reason, "insufficient_access_tier")
        self.assertTrue(internal.allowed)
        self.assertEqual(internal.effective_access_level, DataFile.ACCESS_LEVEL_INTERNAL)

    def test_unrelated_file_is_not_authorized_by_asset(self):
        unrelated = DataFile.objects.create(
            file_code="FILE_ASSET_UNRELATED",
            file_name="unrelated.fasta",
            file_path="/not-used/unrelated.fasta",
        )

        decision = resolve_data_asset_file_access(self.asset, unrelated)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "file_not_asset_member")
