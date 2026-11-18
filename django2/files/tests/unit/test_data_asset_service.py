from django.contrib.auth import get_user_model
from django.test import TestCase

from files.models import Accession, DataAsset, DataFile, Project, Species
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
        self.data_file = DataFile.objects.create(
            file_code="FILE_ASSET_SERVICE",
            file_name="service.fasta",
            file_path="/not-used/service.fasta",
        )

    def create_asset(self, **overrides):
        values = {
            "asset_code": "ASSET_SERVICE",
            "project": self.project,
            "data_type_key": "genome",
            "profile_key": "reference_genome",
            "created_by": self.user,
        }
        values.update(overrides)
        return create_data_asset(**values)

    def test_create_asset_populates_registry_identity_and_relations(self):
        asset = self.create_asset(
            metadata={"coverage": 30},
            file_memberships=[
                AssetFileInput(
                    data_file=self.data_file,
                    file_role="primary_data",
                    is_primary=True,
                )
            ],
            accession_links=[AssetAccessionInput(accession=self.accession_a)],
        )

        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
        self.assertRegex(asset.schema_digest, r"^[0-9a-f]{64}$")
        self.assertEqual(asset.file_memberships.get().primary_slot, 1)
        self.assertEqual(asset.accession_links.get().primary_slot, 1)

    def test_asset_can_be_created_without_accession(self):
        asset = self.create_asset(asset_code="ASSET_NO_ACCESSION")

        self.assertFalse(asset.accession_links.exists())

    def test_unknown_metadata_and_file_role_are_rejected_before_write(self):
        with self.assertRaisesRegex(DataAssetServiceError, "Additional properties"):
            self.create_asset(
                asset_code="ASSET_BAD_METADATA",
                metadata={"not_registered": True},
            )
        with self.assertRaisesRegex(DataAssetServiceError, "Unknown file role"):
            self.create_asset(
                asset_code="ASSET_BAD_ROLE",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="not_registered")
                ],
            )

        self.assertFalse(DataAsset.objects.exists())

    def test_duplicate_file_and_primary_context_inputs_are_rejected(self):
        with self.assertRaisesRegex(DataAssetServiceError, "only once"):
            self.create_asset(
                asset_code="ASSET_DUP_FILE",
                file_memberships=[
                    AssetFileInput(data_file=self.data_file, file_role="primary_data"),
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
