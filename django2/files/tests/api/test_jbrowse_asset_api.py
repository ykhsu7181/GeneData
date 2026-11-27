import hashlib
import os
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import AssetFileMembership, DataAsset, DataFile, Project, ProjectMembership
from files.services.data_asset_registry_service import load_data_asset_registry


class JBrowseAssetApiTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.manual_root = os.path.join(self.temporary_directory.name, "manual_files")
        self.derived_root = os.path.join(self.temporary_directory.name, "derived_data")
        os.makedirs(self.manual_root)
        os.makedirs(self.derived_root)
        self.settings_override = override_settings(
            MANUAL_FILES_DIR=self.manual_root,
            GENEDATA_DERIVED_DATA_DIR=self.derived_root,
            GENEDATA_JBROWSE_MANUAL_INTERNAL_PREFIX="/_protected_manual_files/",
            GENEDATA_JBROWSE_DERIVED_INTERNAL_PREFIX="/_protected_derived_data/",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username="browser-owner")
        self.project = Project.objects.create(project_code="BROWSER_ASSET")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.user,
        )
        profile = load_data_asset_registry().resolve_current_asset_profile(
            "sequence", "reference_genome"
        )
        self.asset = DataAsset.objects.create(
            asset_code="REF_BROWSER",
            project=self.project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
            created_by=self.user,
            published_at=timezone.now(),
        )

    def _file(self, root, relative_path, code, content=b"data", role="genome_fasta"):
        path = os.path.join(root, relative_path)
        os.makedirs(os.path.dirname(path) or root, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)
        data_file = DataFile.objects.create(
            file_code=code,
            file_name=os.path.basename(path),
            file_path=path,
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            is_current=True,
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        AssetFileMembership.objects.create(
            asset=self.asset,
            data_file=data_file,
            file_role=role,
            created_by=self.user,
        )
        return data_file

    def _url(self, data_file, asset_code=None):
        code = asset_code if asset_code is not None else self.asset.asset_code
        return f"/gd/api/files/browser-assets/{data_file.id}/?asset_code={code}"

    def test_public_member_returns_internal_redirect_without_streaming_body(self):
        data_file = self._file(
            self.manual_root, "genome.IR64.fasta", "GENOME_IR64", b">Chr01\nACGT\n"
        )
        response = self.client.get(self._url(data_file), HTTP_RANGE="bytes=0-3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_manual_files/genome.IR64.fasta",
        )
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response.content, b"")

    def test_derived_index_member_uses_encoded_internal_path(self):
        data_file = self._file(
            self.derived_root,
            os.path.join("jbrowse", "注释 1.gff3.gz"),
            "JBROWSE_GFF3",
            role="fasta_index",
        )
        response = self.client.get(self._url(data_file))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_derived_data/jbrowse/%E6%B3%A8%E9%87%8A%201.gff3.gz",
        )

    def test_non_browser_profile_role_is_not_a_general_download(self):
        data_file = self._file(
            self.manual_root, "metadata.json", "METADATA", b"{}", role="metadata"
        )
        self.assertEqual(self.client.get(self._url(data_file)).status_code, 404)

    def test_missing_or_wrong_asset_code_does_not_expose_file(self):
        data_file = self._file(self.manual_root, "reference.fa", "REFERENCE")
        for url in (
            f"/gd/api/files/browser-assets/{data_file.id}/",
            self._url(data_file, "UNKNOWN"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_blocked_outside_and_private_files_fail_closed(self):
        blocked = self._file(self.manual_root, "blocked.fa", "BLOCKED")
        blocked.availability_status = DataFile.AVAILABILITY_BLOCKED
        blocked.save(update_fields=["availability_status", "updated_at"])
        outside_root = os.path.join(self.temporary_directory.name, "outside")
        os.makedirs(outside_root)
        outside = self._file(outside_root, "outside.fa", "OUTSIDE", role="fasta_index")
        self.asset.status = DataAsset.STATUS_DRAFT
        self.asset.visibility = DataAsset.VISIBILITY_PRIVATE
        self.asset.published_at = None
        self.asset.save(update_fields=["status", "visibility", "published_at", "updated_at"])
        for data_file in (blocked, outside):
            self.assertEqual(self.client.get(self._url(data_file)).status_code, 404)

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self._url(blocked)).status_code, 404)
        self.assertEqual(self.client.get(self._url(outside)).status_code, 404)
