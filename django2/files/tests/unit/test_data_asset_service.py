from django.contrib.auth import get_user_model
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataAsset,
    DataFile,
    Project,
    Sample,
    Species,
)
from files.services.data_asset_service import (
    AssetAccessionInput,
    AssetFileInput,
    DataAssetConflictError,
    DataAssetServiceError,
    create_data_asset,
)


class DataAssetServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="asset-service-user")
        self.project = Project.objects.create(project_code="PROJECT_ASSET_SERVICE")
        self.species = Species.objects.create(species_code="SPECIES_ASSET_SERVICE")
        self.accession_a = Accession.objects.create(
            accession="ACC_SERVICE_A", species=self.species
        )
        self.accession_b = Accession.objects.create(
            accession="ACC_SERVICE_B", species=self.species
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession_a,
            name="ASSEMBLY_SERVICE",
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession_a,
            name="ANNOTATION_SERVICE",
        )
        self.sample_a = Sample.objects.create(sample_code="SAMPLE_SERVICE_A")
        self.sample_b = Sample.objects.create(sample_code="SAMPLE_SERVICE_B")
        self.data_file = self.make_file("GENOME", "service.fasta")

    def make_file(self, suffix, name):
        return DataFile.objects.create(
            file_code=f"FILE_ASSET_SERVICE_{suffix}",
            file_name=name,
            file_path=f"/not-used/{name}",
        )

    def create_asset(self, **overrides):
        values = {
            "asset_code": "ASSET_SERVICE",
            "project": self.project,
            "data_type_key": "sequence",
            "profile_key": "reference_genome",
            "created_by": self.user,
            "file_memberships": [
                AssetFileInput(
                    data_file=self.data_file,
                    file_role="genome_fasta",
                    is_primary=True,
                )
            ],
            "assembly_links": [self.assembly],
        }
        values.update(overrides)
        return create_data_asset(**values)

    def test_create_asset_populates_registry_identity_and_relations(self):
        asset = self.create_asset(metadata={"coverage": 30})

        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
        self.assertEqual(asset.data_type_key, "sequence")
        self.assertEqual(asset.schema_version, "2.0.0")
        self.assertRegex(asset.schema_digest, r"^[0-9a-f]{64}$")
        self.assertEqual(asset.file_memberships.get().primary_slot, 1)
        self.assertEqual(asset.assembly_links.get().assembly, self.assembly)
        self.assertEqual(asset.assembly_links.get().created_by, self.user)
        self.assertFalse(asset.accession_links.exists())

    def test_formal_creation_rejects_missing_or_auxiliary_only_files(self):
        invalid_memberships = (
            [],
            [AssetFileInput(data_file=self.data_file, file_role="fasta_index")],
        )
        for index, memberships in enumerate(invalid_memberships):
            with self.subTest(index=index):
                with self.assertRaisesRegex(DataAssetServiceError, "requires at least 1"):
                    self.create_asset(
                        asset_code=f"ASSET_MISSING_CORE_{index}",
                        file_memberships=memberships,
                    )
        self.assertFalse(DataAsset.objects.exists())

    def test_reference_genome_requires_one_assembly_and_rejects_other_contexts(self):
        with self.assertRaisesRegex(DataAssetServiceError, "Context assembly requires"):
            self.create_asset(asset_code="ASSET_NO_ASSEMBLY", assembly_links=[])
        with self.assertRaisesRegex(DataAssetServiceError, "Context sample.*not allowed"):
            self.create_asset(
                asset_code="ASSET_WRONG_CONTEXT",
                sample_links=[self.sample_a],
            )
        with self.assertRaisesRegex(DataAssetServiceError, "Context accession.*not allowed"):
            self.create_asset(
                asset_code="ASSET_REDUNDANT_ACCESSION",
                accession_links=[AssetAccessionInput(accession=self.accession_a)],
            )

    def test_table_can_be_created_without_professional_context(self):
        table_file = self.make_file("TABLE", "research.tsv")

        asset = self.create_asset(
            asset_code="ASSET_TABLE_NO_CONTEXT",
            data_type_key="table",
            profile_key="research_table",
            file_memberships=[
                AssetFileInput(data_file=table_file, file_role="primary_table")
            ],
            assembly_links=[],
        )

        self.assertFalse(asset.accession_links.exists())
        self.assertFalse(asset.sample_links.exists())
        self.assertFalse(asset.assembly_links.exists())
        self.assertFalse(asset.annotation_links.exists())

    def test_allowed_contexts_are_created_without_role_fields(self):
        table_file = self.make_file("CONTEXT_TABLE", "contexts.tsv")

        asset = self.create_asset(
            asset_code="ASSET_TABLE_CONTEXTS",
            data_type_key="table",
            profile_key="research_table",
            file_memberships=[
                AssetFileInput(data_file=table_file, file_role="primary_table")
            ],
            assembly_links=[self.assembly],
            sample_links=[self.sample_a],
            annotation_links=[self.annotation],
        )

        self.assertEqual(asset.sample_links.get().sample, self.sample_a)
        self.assertEqual(asset.assembly_links.get().assembly, self.assembly)
        self.assertEqual(asset.annotation_links.get().annotation, self.annotation)

    def test_unbounded_core_and_context_rules_allow_multiple_items(self):
        image_a = self.make_file("IMAGE_A", "image-a.tif")
        image_b = self.make_file("IMAGE_B", "image-b.tif")

        asset = self.create_asset(
            asset_code="ASSET_IMAGE_SET",
            data_type_key="image",
            profile_key="microscopy_image_set",
            file_memberships=[
                AssetFileInput(data_file=image_a, file_role="primary_image", position=0),
                AssetFileInput(data_file=image_b, file_role="primary_image", position=1),
            ],
            assembly_links=[],
            sample_links=[self.sample_a, self.sample_b],
        )

        self.assertEqual(asset.file_memberships.count(), 2)
        self.assertEqual(asset.sample_links.count(), 2)

    def test_unknown_metadata_and_file_role_are_rejected_before_write(self):
        with self.assertRaisesRegex(DataAssetServiceError, "Additional properties"):
            self.create_asset(
                asset_code="ASSET_BAD_METADATA",
                metadata={"not_registered": True},
            )
        with self.assertRaisesRegex(DataAssetServiceError, "not allowed"):
            self.create_asset(
                asset_code="ASSET_BAD_ROLE",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="not_registered")
                ],
            )

        self.assertFalse(DataAsset.objects.exists())

    def test_duplicate_file_and_primary_accession_inputs_are_rejected(self):
        with self.assertRaisesRegex(DataAssetServiceError, "only once"):
            self.create_asset(
                asset_code="ASSET_DUP_FILE",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="genome_fasta"),
                    AssetFileInput(data_file=self.data_file, file_role="metadata", position=1),
                ],
            )
        with self.assertRaisesRegex(DataAssetServiceError, "Only one primary Accession"):
            self.create_asset(
                asset_code="ASSET_DUP_PRIMARY_ACCESSION",
                accession_links=[
                    AssetAccessionInput(accession=self.accession_a),
                    AssetAccessionInput(accession=self.accession_b),
                ],
            )

    def test_duplicate_or_unsaved_context_inputs_are_rejected(self):
        with self.assertRaisesRegex(DataAssetServiceError, "only once"):
            self.create_asset(
                asset_code="ASSET_DUP_SAMPLE",
                data_type_key="image",
                profile_key="microscopy_image_set",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="primary_image")
                ],
                assembly_links=[],
                sample_links=[self.sample_a, self.sample_a],
            )
        with self.assertRaisesRegex(DataAssetServiceError, "saved Sample"):
            self.create_asset(
                asset_code="ASSET_UNSAVED_SAMPLE",
                data_type_key="image",
                profile_key="microscopy_image_set",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="primary_image")
                ],
                assembly_links=[],
                sample_links=[Sample(sample_code="UNSAVED")],
            )

    def test_saved_project_and_operator_are_required(self):
        with self.assertRaisesRegex(DataAssetServiceError, "project"):
            self.create_asset(asset_code="ASSET_NO_PROJECT", project=None)
        with self.assertRaisesRegex(DataAssetServiceError, "created_by"):
            self.create_asset(asset_code="ASSET_NO_OPERATOR", created_by=None)

    def test_duplicate_asset_code_returns_stable_conflict(self):
        self.create_asset(asset_code="ASSET_DUP_CODE")

        with self.assertRaises(DataAssetConflictError):
            self.create_asset(asset_code="ASSET_DUP_CODE")

        self.assertEqual(DataAsset.objects.filter(asset_code="ASSET_DUP_CODE").count(), 1)

    def test_same_profile_version_and_digest_can_be_reused(self):
        first = self.create_asset(asset_code="ASSET_PROFILE_FIRST")

        second = self.create_asset(asset_code="ASSET_PROFILE_SECOND")

        self.assertEqual(second.schema_digest, first.schema_digest)

    def test_same_profile_version_with_different_digest_is_rejected(self):
        DataAsset.objects.create(
            asset_code="ASSET_CONFLICTING_PROFILE",
            project=self.project,
            data_type_key="sequence",
            profile_key="reference_genome",
            schema_version="2.0.0",
            schema_digest="0" * 64,
            created_by=self.user,
        )

        with self.assertRaisesRegex(
            DataAssetConflictError,
            "already used with a different schema digest",
        ):
            self.create_asset(asset_code="ASSET_PROFILE_DIGEST_CONFLICT")

        self.assertFalse(
            DataAsset.objects.filter(
                asset_code="ASSET_PROFILE_DIGEST_CONFLICT"
            ).exists()
        )
