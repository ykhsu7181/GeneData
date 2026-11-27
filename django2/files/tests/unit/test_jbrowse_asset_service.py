import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

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
from files.services.data_asset_registry_service import load_data_asset_registry
from files.services.jbrowse_asset_service import (
    JBrowseAssetError,
    resolve_jbrowse_asset_context,
)
from files.services.jbrowse_asset_build_service import build_reference_fasta_index


class JBrowseAssetServiceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user = get_user_model().objects.create_user(username="jbrowse-owner")
        self.project = Project.objects.create(project_code="JBROWSE_ASSET")
        self.other_project = Project.objects.create(project_code="JBROWSE_REFERENCE")
        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.user,
        )
        ProjectMembership.objects.create(
            project=self.other_project,
            user=self.user,
            role=ProjectMembership.ROLE_OWNER,
            created_by=self.user,
        )
        self.registry = load_data_asset_registry()
        annotation_profile = self.registry.resolve_current_asset_profile(
            "feature", "genome_annotation"
        )
        reference_profile = self.registry.resolve_current_asset_profile(
            "sequence", "reference_genome"
        )
        self.annotation = self._asset("ANN", self.project, annotation_profile)
        self.reference = self._asset(
            "REF", self.other_project, reference_profile,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        rule = self.registry.resolve_current_relation("uses_reference")
        self.relation = DataAssetRelation.objects.create(
            source_asset=self.annotation,
            target_asset=self.reference,
            relation_type=rule.key,
            relation_rule_version=rule.version,
            relation_rule_digest=rule.digest,
            created_by=self.user,
        )
        self._member(self.annotation, "annotation_gff", "annotation.gff", b"##gff-version 3\n")
        self._member(self.reference, "genome_fasta", "reference.fa", b">chr1\nACGT\n")

    def _asset(self, code, project, profile, *, status=DataAsset.STATUS_DRAFT,
               visibility=DataAsset.VISIBILITY_PRIVATE):
        return DataAsset.objects.create(
            asset_code=code,
            project=project,
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
        data_file = DataFile.objects.create(
            file_code=f"FILE_{asset.asset_code}_{role}",
            file_name=name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        return AssetFileMembership.objects.create(
            asset=asset, data_file=data_file, file_role=role, created_by=self.user
        )

    def resolve(self, **kwargs):
        return resolve_jbrowse_asset_context(
            self.annotation,
            user=self.user,
            registry=self.registry,
            roots={"test": {"path": str(self.root), "internal_uri": "/_test/"}},
            **kwargs,
        )

    def test_resolves_exact_annotation_reference_and_files(self):
        context = self.resolve()
        self.assertEqual(context.reference_asset, self.reference)
        self.assertEqual(context.annotation_gff.file_name, "annotation.gff")
        self.assertEqual(context.genome_fasta.file_name, "reference.fa")

    def test_duplicate_reference_fails_closed(self):
        second = self._asset(
            "REF2", self.other_project,
            self.registry.resolve_current_asset_profile("sequence", "reference_genome"),
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        DataAssetRelation.objects.create(
            source_asset=self.annotation,
            target_asset=second,
            relation_type=self.relation.relation_type,
            relation_rule_version=self.relation.relation_rule_version,
            relation_rule_digest=self.relation.relation_rule_digest,
            created_by=self.user,
        )
        with self.assertRaisesRegex(JBrowseAssetError, "multiple"):
            self.resolve()

    def test_unreleased_reference_fails_closed(self):
        self.reference.status = DataAsset.STATUS_DRAFT
        self.reference.visibility = DataAsset.VISIBILITY_PRIVATE
        self.reference.project = self.project
        self.reference.save(update_fields=["status", "visibility", "project", "updated_at"])
        with self.assertRaisesRegex(JBrowseAssetError, "not released"):
            self.resolve()

    def test_cross_project_nonpublic_reference_fails_closed(self):
        self.reference.visibility = DataAsset.VISIBILITY_PRIVATE
        self.reference.save(update_fields=["visibility", "updated_at"])
        with self.assertRaises(JBrowseAssetError) as caught:
            self.resolve()
        self.assertEqual(caught.exception.code, "cross_project_target_not_public_released")

    def test_blocked_member_fails_closed(self):
        membership = self.annotation.file_memberships.get(file_role="annotation_gff")
        membership.data_file.availability_status = DataFile.AVAILABILITY_BLOCKED
        membership.data_file.save(update_fields=["availability_status", "updated_at"])
        with self.assertRaises(JBrowseAssetError) as caught:
            self.resolve()
        self.assertEqual(caught.exception.code, "file_not_available")

    def test_fasta_index_build_registers_available_auxiliary_membership(self):
        with self.settings(GENEDATA_DERIVED_DATA_DIR=str(self.root / "derived")):
            index_file, sequence_count = build_reference_fasta_index(
                self.reference,
                user=self.user,
                registry=self.registry,
                roots={"test": {"path": str(self.root), "internal_uri": "/_test/"}},
                output_root=str(self.root / "derived"),
            )
        self.assertEqual(sequence_count, 1)
        self.assertEqual(index_file.availability_status, DataFile.AVAILABILITY_AVAILABLE)
        self.assertIsNotNone(index_file.content_version)
        self.assertTrue(
            AssetFileMembership.objects.filter(
                asset=self.reference,
                data_file=index_file,
                file_role="fasta_index",
            ).exists()
        )

    def test_fasta_index_build_rejects_output_outside_derived_root(self):
        with self.settings(GENEDATA_DERIVED_DATA_DIR=str(self.root / "derived")):
            with self.assertRaisesRegex(RuntimeError, "derived data root"):
                build_reference_fasta_index(
                    self.reference,
                    user=self.user,
                    registry=self.registry,
                    roots={"test": {"path": str(self.root), "internal_uri": "/_test/"}},
                    output_root=str(self.root / "outside"),
                )

    def test_fasta_index_build_restores_previous_file_when_registration_fails(self):
        output_root = self.root / "derived"
        target = output_root / "assets" / self.reference.asset_code / "reference.fasta.fai"
        target.parent.mkdir(parents=True)
        target.write_text("previous-index\n", encoding="utf-8")
        with self.settings(GENEDATA_DERIVED_DATA_DIR=str(output_root)):
            with patch(
                "files.services.jbrowse_asset_build_service.register_generated_auxiliary_file",
                side_effect=RuntimeError("database rejected registration"),
            ):
                with self.assertRaisesRegex(RuntimeError, "database rejected"):
                    build_reference_fasta_index(
                        self.reference,
                        user=self.user,
                        registry=self.registry,
                        roots={
                            "test": {"path": str(self.root), "internal_uri": "/_test/"}
                        },
                        output_root=str(output_root),
                    )
        self.assertEqual(target.read_text(encoding="utf-8"), "previous-index\n")
