import os
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from files.models import (
    AssetFileMembership,
    DataAsset,
    DataFile,
    Project,
    ProjectMembership,
)
from files.services.data_asset_access_service import (
    build_data_asset_file_response,
    filter_visible_asset_file_memberships,
    resolve_data_asset_file_access,
    resolve_data_asset_file_content_access,
    resolve_file_code_content_access,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class DataAssetFileAccessServiceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name, "protected")
        self.outside = Path(self.temp_dir.name, "outside")
        self.root.mkdir()
        self.outside.mkdir()
        self.roots = {
            "test": {
                "path": str(self.root),
                "internal_uri": "/_protected_gate_b/",
            }
        }

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="gate-b-owner")
        self.nonmember = user_model.objects.create_user(username="gate-b-nonmember")
        self.project = Project.objects.create(project_code="PROJECT_GATE_B")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.owner,
        )
        self.profile = load_data_asset_registry().resolve_current_asset_profile(
            "sequence", "raw_read_collection"
        )
        self.public_asset = self.create_asset(
            "ASSET_GATE_B_PUBLIC",
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )

    def create_asset(
        self,
        code,
        *,
        status=DataAsset.STATUS_DRAFT,
        visibility=DataAsset.VISIBILITY_PRIVATE,
        created_by=None,
    ):
        return DataAsset.objects.create(
            asset_code=code,
            project=self.project,
            data_type_key=self.profile.data_type_key,
            profile_key=self.profile.profile_key,
            schema_version=self.profile.schema_version,
            schema_digest=self.profile.schema_digest,
            status=status,
            visibility=visibility,
            created_by=created_by or self.owner,
            published_at=(
                timezone.now() if status == DataAsset.STATUS_RELEASED else None
            ),
        )

    def create_file(self, code, *, path=None, **overrides):
        if path is None:
            path = self.root / f"{code}.fastq.gz"
            path.write_bytes(b"reads")
        values = {
            "file_code": code,
            "file_name": path.name,
            "file_path": str(path),
            "sha256": "a" * 64,
            "is_current": True,
            "availability_status": DataFile.AVAILABILITY_AVAILABLE,
        }
        values.update(overrides)
        return DataFile.objects.create(**values)

    def add_membership(self, asset, data_file, *, role="read_fastq"):
        position = AssetFileMembership.objects.filter(
            asset=asset,
            file_role=role,
        ).count()
        return AssetFileMembership.objects.create(
            asset=asset,
            data_file=data_file,
            file_role=role,
            position=position,
            created_by=self.owner,
        )

    def test_membership_and_profile_role_are_both_required(self):
        data_file = self.create_file("FILE_GATE_B_MEMBERSHIP")

        missing = resolve_data_asset_file_access(self.public_asset, data_file)
        self.assertEqual(missing.reason, "file_not_asset_member")

        membership = self.add_membership(
            self.public_asset,
            data_file,
            role="unregistered_role",
        )
        invalid_role = resolve_data_asset_file_access(self.public_asset, data_file)
        self.assertEqual(invalid_role.reason, "file_role_not_allowed")

        membership.file_role = "read_fastq"
        membership.save(update_fields=["file_role"])
        self.assertTrue(
            resolve_data_asset_file_access(self.public_asset, data_file).allowed
        )

    def test_exact_profile_version_and_digest_are_required(self):
        data_file = self.create_file("FILE_GATE_B_PROFILE")
        self.add_membership(self.public_asset, data_file)
        self.public_asset.schema_digest = "0" * 64

        decision = resolve_data_asset_file_access(self.public_asset, data_file)

        self.assertEqual(decision.reason, "asset_profile_unknown")

    def test_physical_gate_requires_current_available_and_checksum(self):
        data_file = self.create_file("FILE_GATE_B_PHYSICAL")
        self.add_membership(self.public_asset, data_file)

        for availability in (
            DataFile.AVAILABILITY_QUARANTINED,
            DataFile.AVAILABILITY_BLOCKED,
            DataFile.AVAILABILITY_MISSING,
        ):
            with self.subTest(availability=availability):
                data_file.availability_status = availability
                self.assertEqual(
                    resolve_data_asset_file_content_access(
                        self.public_asset, data_file, roots=self.roots
                    ).reason,
                    "file_not_available",
                )

        data_file.availability_status = DataFile.AVAILABILITY_AVAILABLE
        data_file.is_current = False
        self.assertEqual(
            resolve_data_asset_file_content_access(
                self.public_asset, data_file, roots=self.roots
            ).reason,
            "file_not_current",
        )
        data_file.is_current = True
        data_file.sha256 = None
        self.assertEqual(
            resolve_data_asset_file_content_access(
                self.public_asset, data_file, roots=self.roots
            ).reason,
            "file_checksum_unverified",
        )

    def test_available_file_must_exist_under_an_allowed_root(self):
        missing_path = self.root / "missing.fastq.gz"
        missing = self.create_file("FILE_GATE_B_MISSING", path=missing_path)
        outside_path = self.outside / "outside.fastq.gz"
        outside_path.write_bytes(b"outside")
        outside = self.create_file("FILE_GATE_B_OUTSIDE", path=outside_path)
        self.add_membership(self.public_asset, missing)
        self.add_membership(self.public_asset, outside)

        self.assertEqual(
            resolve_data_asset_file_content_access(
                self.public_asset, missing, roots=self.roots
            ).reason,
            "file_missing",
        )
        self.assertEqual(
            resolve_data_asset_file_content_access(
                self.public_asset, outside, roots=self.roots
            ).reason,
            "outside_protected_roots",
        )

    @skipUnless(hasattr(os, "symlink"), "symbolic links are not supported")
    def test_symlink_escape_is_denied(self):
        target = self.outside / "secret.fastq.gz"
        target.write_bytes(b"secret")
        link = self.root / "linked.fastq.gz"
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symbolic link creation is unavailable: {exc}")
        data_file = self.create_file("FILE_GATE_B_SYMLINK", path=link)
        self.add_membership(self.public_asset, data_file)

        decision = resolve_data_asset_file_content_access(
            self.public_asset, data_file, roots=self.roots
        )

        self.assertEqual(decision.reason, "outside_protected_roots")

    def test_direct_file_code_requires_one_visible_membership(self):
        data_file = self.create_file("FILE_GATE_B_DIRECT")
        self.add_membership(self.public_asset, data_file)

        allowed, resolved_file = resolve_file_code_content_access(
            data_file.file_code,
            roots=self.roots,
        )
        missing, hidden_file = resolve_file_code_content_access(
            "FILE_GATE_B_UNKNOWN",
            roots=self.roots,
        )

        self.assertTrue(allowed.allowed)
        self.assertEqual(resolved_file, data_file)
        self.assertEqual(missing.reason, "file_not_available")
        self.assertIsNone(hidden_file)

    def test_denied_direct_access_returns_no_file_or_membership(self):
        data_file = self.create_file(
            "FILE_GATE_B_DENIED_DIRECT",
            availability_status=DataFile.AVAILABILITY_BLOCKED,
        )
        self.add_membership(self.public_asset, data_file)

        decision, resolved_file = resolve_file_code_content_access(
            data_file.file_code,
            roots=self.roots,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "file_not_available")
        self.assertIsNone(decision.membership)
        self.assertIsNone(resolved_file)

    def test_multiple_visible_memberships_require_explicit_asset(self):
        data_file = self.create_file("FILE_GATE_B_AMBIGUOUS")
        second_public = self.create_asset(
            "ASSET_GATE_B_PUBLIC_2",
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        self.add_membership(self.public_asset, data_file)
        self.add_membership(second_public, data_file)

        ambiguous, _ = resolve_file_code_content_access(
            data_file.file_code,
            roots=self.roots,
        )
        selected, selected_file = resolve_file_code_content_access(
            data_file.file_code,
            asset_code=second_public.asset_code,
            roots=self.roots,
        )

        self.assertEqual(ambiguous.reason, "asset_selection_required")
        self.assertTrue(selected.allowed)
        self.assertEqual(selected_file, data_file)

    def test_same_file_public_and_private_uses_visible_memberships_only(self):
        data_file = self.create_file("FILE_GATE_B_SHARED")
        private_asset = self.create_asset("ASSET_GATE_B_PRIVATE")
        self.add_membership(self.public_asset, data_file)
        self.add_membership(private_asset, data_file)

        anonymous, _ = resolve_file_code_content_access(
            data_file.file_code,
            roots=self.roots,
        )
        owner, _ = resolve_file_code_content_access(
            data_file.file_code,
            user=self.owner,
            roots=self.roots,
        )
        nonmember_private, _ = resolve_file_code_content_access(
            data_file.file_code,
            user=self.nonmember,
            asset_code=private_asset.asset_code,
            roots=self.roots,
        )

        self.assertTrue(anonymous.allowed)
        self.assertEqual(owner.reason, "asset_selection_required")
        self.assertEqual(nonmember_private.reason, "file_not_available")

    def test_legacy_access_and_publication_fields_do_not_grant_or_deny(self):
        data_file = self.create_file(
            "FILE_GATE_B_LEGACY_FIELDS",
            access_level=DataFile.ACCESS_LEVEL_PRIVATE,
            publication_status=DataFile.PUBLICATION_DRAFT,
            published_at=None,
        )
        self.add_membership(self.public_asset, data_file)

        allowed = resolve_data_asset_file_content_access(
            self.public_asset, data_file, roots=self.roots
        )
        data_file.access_level = DataFile.ACCESS_LEVEL_PUBLIC
        data_file.publication_status = DataFile.PUBLICATION_RELEASED
        data_file.published_at = timezone.now()
        data_file.availability_status = DataFile.AVAILABILITY_BLOCKED
        denied = resolve_data_asset_file_content_access(
            self.public_asset, data_file, roots=self.roots
        )

        self.assertTrue(allowed.allowed)
        self.assertEqual(denied.reason, "file_not_available")

    def test_controlled_response_omits_checksum_and_absolute_path(self):
        data_file = self.create_file("FILE_GATE_B_RESPONSE")
        self.add_membership(self.public_asset, data_file)

        decision, response = build_data_asset_file_response(
            self.public_asset,
            data_file,
            roots=self.roots,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_gate_b/FILE_GATE_B_RESPONSE.fastq.gz",
        )
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Length"], "5")
        self.assertNotIn("ETag", response)
        self.assertNotIn(str(self.root), str(response.items()))
        self.assertNotIn(data_file.sha256, str(response.items()))

    def test_visible_membership_filter_is_one_query_for_batch(self):
        for index in range(3):
            data_file = self.create_file(f"FILE_GATE_B_BATCH_{index}")
            self.add_membership(self.public_asset, data_file)

        with self.assertNumQueries(1):
            memberships = list(
                filter_visible_asset_file_memberships(
                    AssetFileMembership.objects.select_related("asset", "data_file")
                )
            )

        self.assertEqual(len(memberships), 3)

    def test_blocking_content_preserves_membership_fact(self):
        data_file = self.create_file("FILE_GATE_B_PRESERVE")
        membership = self.add_membership(self.public_asset, data_file)
        data_file.availability_status = DataFile.AVAILABILITY_BLOCKED

        decision = resolve_data_asset_file_content_access(
            self.public_asset, data_file, roots=self.roots
        )

        self.assertFalse(decision.allowed)
        self.assertTrue(AssetFileMembership.objects.filter(pk=membership.pk).exists())
