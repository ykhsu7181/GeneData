import gzip
import hashlib
import os
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from files.models import (
    AssetFileMembership,
    DataAsset,
    DataAssetRelation,
    DataFile,
    Project,
    ProjectMembership,
)
from files.services.annotation_asset_feature_index_service import (
    build_annotation_asset_feature_index,
)
from files.services.data_asset_registry_service import load_data_asset_registry
from files.services.jbrowse_asset_config_service import (
    get_jbrowse_asset_config,
    get_jbrowse_asset_status,
)
from files.services.jbrowse_asset_location_service import resolve_jbrowse_asset_location


class JBrowseAssetConfigServiceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.roots = {"test": {"path": str(self.root), "internal_uri": "/_test/"}}
        self.user = get_user_model().objects.create_user(username="config-owner")
        self.project = Project.objects.create(project_code="CONFIG_PROJECT")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.user,
        )
        registry = load_data_asset_registry()
        annotation_profile = registry.resolve_current_asset_profile(
            "feature", "genome_annotation"
        )
        reference_profile = registry.resolve_current_asset_profile(
            "sequence", "reference_genome"
        )
        self.annotation = self._asset("ANN_CONFIG", annotation_profile)
        self.reference = self._asset(
            "REF_CONFIG",
            reference_profile,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        rule = registry.resolve_current_relation("uses_reference")
        DataAssetRelation.objects.create(
            source_asset=self.annotation,
            target_asset=self.reference,
            relation_type=rule.key,
            relation_rule_version=rule.version,
            relation_rule_digest=rule.digest,
            created_by=self.user,
        )
        fasta = self._member(
            self.reference, "genome_fasta", "reference.fa", b">chr1\nACGTACGTACGT\n"
        )
        fai = self._member(
            self.reference, "fasta_index", "reference.fa.fai", b"chr1\t12\t6\t12\t13\n"
        )
        gff_path = self.root / "annotation.gff3.gz"
        with gzip.open(gff_path, "wt", encoding="utf-8", newline="\n") as handle:
            handle.write("##gff-version 3\nchr1\ttest\tgene\t2\t4\t.\t+\t.\tID=g1\n")
        gff = self._member_path(self.annotation, "annotation_gff", gff_path)
        tbi = self._member(self.annotation, "tabix_index", "annotation.gff3.gz.tbi", b"index")
        base = 1_700_000_000
        os.utime(fasta.file_path, (base, base))
        os.utime(gff.file_path, (base, base))
        os.utime(fai.file_path, (base + 10, base + 10))
        os.utime(tbi.file_path, (base + 10, base + 10))

    def _asset(self, code, profile, *, status=DataAsset.STATUS_DRAFT,
               visibility=DataAsset.VISIBILITY_PRIVATE):
        return DataAsset.objects.create(
            asset_code=code,
            project=self.project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            status=status,
            visibility=visibility,
            created_by=self.user,
            published_at=timezone.now() if status == DataAsset.STATUS_RELEASED else None,
        )

    def _member(self, asset, role, name, content):
        path = self.root / name
        path.write_bytes(content)
        return self._member_path(asset, role, path)

    def _member_path(self, asset, role, path):
        content = path.read_bytes()
        data_file = DataFile.objects.create(
            file_code=f"CFG_{asset.asset_code}_{role}",
            file_name=path.name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        AssetFileMembership.objects.create(
            asset=asset,
            data_file=data_file,
            file_role=role,
            created_by=self.user,
        )
        return data_file

    def test_config_uses_asset_codes_and_explicit_file_authorization_urls(self):
        config, status = get_jbrowse_asset_config(
            self.annotation, user=self.user, roots=self.roots
        )
        self.assertEqual(status["status"], "ready")
        serialized = str(config)
        self.assertIn("asset-REF_CONFIG", serialized)
        self.assertIn("asset_code=REF_CONFIG", serialized)
        self.assertIn("asset_code=ANN_CONFIG", serialized)

    def test_location_uses_asset_feature_index_and_reference_aliases(self):
        feature_index, _ = build_annotation_asset_feature_index(
            self.annotation, user=self.user, roots=self.roots
        )
        feature = feature_index.features.get()
        payload = resolve_jbrowse_asset_location(
            self.annotation, feature.id, user=self.user, roots=self.roots
        )
        self.assertEqual(payload["ref_name"], "chr1")
        self.assertEqual(payload["annotation_asset_code"], "ANN_CONFIG")
        self.assertEqual(payload["reference_asset_code"], "REF_CONFIG")

    def test_stale_tabix_fails_closed(self):
        tabix = self.annotation.file_memberships.get(file_role="tabix_index").data_file
        os.utime(tabix.file_path, (1, 1))
        status = get_jbrowse_asset_status(
            self.annotation, user=self.user, roots=self.roots
        )
        self.assertEqual(status["status"], "tabix_index_stale")
        self.assertFalse(status["ready"])
