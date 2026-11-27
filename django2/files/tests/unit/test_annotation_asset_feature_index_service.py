import os
import tempfile
from pathlib import Path

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
from files.services.annotation_asset_feature_index_service import (
    AnnotationIndexUnavailable,
    build_annotation_asset_feature_index,
    get_ready_annotation_asset_index,
    select_annotation_asset_source_file,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class AnnotationAssetFeatureIndexServiceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name, "protected")
        self.root.mkdir()
        self.roots = {
            "test": {
                "path": str(self.root),
                "internal_uri": "/_protected_gate_c/",
            }
        }
        self.user = get_user_model().objects.create_user(username="gate-c-owner")
        self.project = Project.objects.create(project_code="PROJECT_GATE_C_INDEX_SERVICE")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.user,
        )
        registry = load_data_asset_registry()
        self.annotation_profile = registry.resolve_current_asset_profile(
            "feature", "genome_annotation"
        )
        self.reference_profile = registry.resolve_current_asset_profile(
            "sequence", "reference_genome"
        )
        self.annotation_asset = self.create_asset(
            "ASSET_GATE_C_ANNOTATION_SERVICE",
            self.annotation_profile,
        )

    def create_asset(self, code, profile):
        return DataAsset.objects.create(
            asset_code=code,
            project=self.project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
            published_at=timezone.now(),
            created_by=self.user,
        )

    def create_gff(self, code, *, availability=DataFile.AVAILABILITY_AVAILABLE):
        path = self.root / f"{code}.gff3"
        path.write_text(
            "##gff-version 3\n"
            "chr1\tsource\tgene\t1\t10\t.\t+\t.\tID=gene1\n",
            encoding="utf-8",
        )
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            sha256="a" * 64,
            is_current=True,
            availability_status=availability,
        )

    def add_gff(self, asset, data_file, *, position=0):
        return AssetFileMembership.objects.create(
            asset=asset,
            data_file=data_file,
            file_role="annotation_gff",
            position=position,
            created_by=self.user,
        )

    def test_builds_new_index_without_legacy_annotation(self):
        source_file = self.create_gff("FILE_GATE_C_ANNOTATION")
        self.add_gff(self.annotation_asset, source_file)

        feature_index, changed = build_annotation_asset_feature_index(
            self.annotation_asset,
            user=self.user,
            roots=self.roots,
        )

        self.assertTrue(changed)
        self.assertEqual(feature_index.annotation_asset, self.annotation_asset)
        self.assertIsNone(feature_index.annotation_id)
        self.assertEqual(feature_index.source_file, source_file)
        self.assertEqual(feature_index.feature_count, 1)
        self.assertEqual(feature_index.chromosomes, ["chr1"])

    def test_ready_index_detects_source_file_change(self):
        source_file = self.create_gff("FILE_GATE_C_STALE")
        self.add_gff(self.annotation_asset, source_file)
        feature_index, _ = build_annotation_asset_feature_index(
            self.annotation_asset,
            user=self.user,
            roots=self.roots,
        )
        service_file = {
            "file_id": source_file.id,
            "file_path": source_file.file_path,
        }
        self.assertEqual(
            get_ready_annotation_asset_index(self.annotation_asset, service_file),
            feature_index,
        )

        with open(source_file.file_path, "a", encoding="utf-8") as handle:
            handle.write("chr2\tsource\tgene\t2\t4\t.\t+\t.\tID=gene2\n")
        os.utime(source_file.file_path, None)

        with self.assertRaises(AnnotationIndexUnavailable) as caught:
            get_ready_annotation_asset_index(self.annotation_asset, service_file)
        self.assertEqual(caught.exception.index_status, "stale")

    def test_wrong_profile_fails_closed(self):
        reference_asset = self.create_asset(
            "ASSET_GATE_C_WRONG_PROFILE",
            self.reference_profile,
        )

        with self.assertRaises(AnnotationIndexUnavailable) as caught:
            select_annotation_asset_source_file(reference_asset, roots=self.roots)

        self.assertEqual(caught.exception.index_status, "profile_invalid")

    def test_missing_or_multiple_annotation_members_fail_closed(self):
        with self.assertRaises(AnnotationIndexUnavailable) as missing:
            select_annotation_asset_source_file(
                self.annotation_asset,
                roots=self.roots,
            )
        self.assertEqual(missing.exception.index_status, "source_missing")

        first = self.create_gff("FILE_GATE_C_MULTIPLE_1")
        second = self.create_gff("FILE_GATE_C_MULTIPLE_2")
        self.add_gff(self.annotation_asset, first, position=0)
        self.add_gff(self.annotation_asset, second, position=1)
        with self.assertRaises(AnnotationIndexUnavailable) as multiple:
            select_annotation_asset_source_file(
                self.annotation_asset,
                roots=self.roots,
            )
        self.assertEqual(multiple.exception.index_status, "source_ambiguous")

    def test_blocked_source_file_fails_closed(self):
        source_file = self.create_gff(
            "FILE_GATE_C_BLOCKED",
            availability=DataFile.AVAILABILITY_BLOCKED,
        )
        self.add_gff(self.annotation_asset, source_file)

        with self.assertRaises(AnnotationIndexUnavailable) as caught:
            select_annotation_asset_source_file(
                self.annotation_asset,
                roots=self.roots,
            )

        self.assertEqual(caught.exception.index_status, "file_not_available")
