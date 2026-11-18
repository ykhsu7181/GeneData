from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from files.models import (
    Accession,
    AssetFileMembership,
    DataAsset,
    DataAssetAccession,
    DataFile,
    Project,
    Species,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class DataAssetModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="asset-owner")
        self.project = Project.objects.create(project_code="PROJECT_ASSET_TEST")
        self.species = Species.objects.create(
            species_code="SPECIES_ASSET_TEST",
            scientific_name="Oryza sativa",
        )
        self.accession_a = Accession.objects.create(
            accession="ACC_ASSET_A",
            species=self.species,
        )
        self.accession_b = Accession.objects.create(
            accession="ACC_ASSET_B",
            species=self.species,
        )
        self.data_file = DataFile.objects.create(
            file_code="FILE_ASSET_TEST",
            file_name="asset.fasta",
            file_path="/not-used/asset.fasta",
        )
        self.profile = load_data_asset_registry().get_profile(
            "genome", "reference_genome"
        )

    def create_asset(self, code):
        return DataAsset.objects.create(
            asset_code=code,
            project=self.project,
            data_type_key=self.profile.data_type_key,
            profile_key=self.profile.profile_key,
            schema_version=self.profile.schema_version,
            schema_digest=self.profile.schema_digest,
            metadata={},
            created_by=self.user,
        )

    def test_asset_can_exist_without_accession_or_files(self):
        asset = self.create_asset("ASSET_EMPTY_CONTEXT")

        self.assertFalse(asset.accession_links.exists())
        self.assertFalse(asset.file_memberships.exists())
        self.assertEqual(asset.status, DataAsset.STATUS_DRAFT)
        self.assertEqual(asset.visibility, DataAsset.VISIBILITY_PRIVATE)

    def test_one_file_can_belong_to_multiple_assets_without_duplication(self):
        first = self.create_asset("ASSET_SHARED_FIRST")
        second = self.create_asset("ASSET_SHARED_SECOND")

        AssetFileMembership.objects.create(
            asset=first,
            data_file=self.data_file,
            file_role="primary_data",
            is_primary=True,
            primary_slot=1,
        )
        AssetFileMembership.objects.create(
            asset=second,
            data_file=self.data_file,
            file_role="primary_data",
            is_primary=True,
            primary_slot=1,
        )

        self.assertEqual(self.data_file.asset_memberships.count(), 2)
        self.assertEqual(DataFile.objects.filter(pk=self.data_file.pk).count(), 1)

    def test_membership_constraints_reject_duplicates_and_multiple_primaries(self):
        asset = self.create_asset("ASSET_FILE_CONSTRAINTS")
        AssetFileMembership.objects.create(
            asset=asset,
            data_file=self.data_file,
            file_role="primary_data",
            is_primary=True,
            primary_slot=1,
        )
        other_file = DataFile.objects.create(
            file_code="FILE_ASSET_OTHER",
            file_name="other.fasta",
            file_path="/not-used/other.fasta",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetFileMembership.objects.create(
                asset=asset,
                data_file=other_file,
                file_role="primary_data",
                position=1,
                is_primary=True,
                primary_slot=1,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetFileMembership.objects.create(
                asset=asset,
                data_file=self.data_file,
                file_role="metadata",
            )

    def test_primary_guard_rejects_inconsistent_membership_values(self):
        asset = self.create_asset("ASSET_FILE_GUARD")

        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetFileMembership.objects.create(
                asset=asset,
                data_file=self.data_file,
                file_role="primary_data",
                is_primary=True,
                primary_slot=None,
            )

    def test_accession_constraints_allow_many_contexts_but_one_primary(self):
        asset = self.create_asset("ASSET_ACCESSION_CONSTRAINTS")
        DataAssetAccession.objects.create(
            asset=asset,
            accession=self.accession_a,
            relation_role=DataAssetAccession.ROLE_PRIMARY,
            primary_slot=1,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            DataAssetAccession.objects.create(
                asset=asset,
                accession=self.accession_b,
                relation_role=DataAssetAccession.ROLE_PRIMARY,
                primary_slot=1,
            )

        DataAssetAccession.objects.create(
            asset=asset,
            accession=self.accession_b,
            relation_role=DataAssetAccession.ROLE_REFERENCE,
            primary_slot=None,
        )
        self.assertEqual(asset.accession_links.count(), 2)

    def test_primary_guard_rejects_inconsistent_accession_values(self):
        asset = self.create_asset("ASSET_ACCESSION_GUARD")

        with self.assertRaises(IntegrityError), transaction.atomic():
            DataAssetAccession.objects.create(
                asset=asset,
                accession=self.accession_a,
                relation_role=DataAssetAccession.ROLE_PRIMARY,
                primary_slot=None,
            )

    def test_context_and_file_facts_are_protected_while_linked(self):
        asset = self.create_asset("ASSET_PROTECTED_LINKS")
        AssetFileMembership.objects.create(
            asset=asset,
            data_file=self.data_file,
            file_role="primary_data",
            is_primary=True,
            primary_slot=1,
        )
        DataAssetAccession.objects.create(
            asset=asset,
            accession=self.accession_a,
            relation_role=DataAssetAccession.ROLE_PRIMARY,
            primary_slot=1,
        )

        with self.assertRaises(ProtectedError):
            self.data_file.delete()
        with self.assertRaises(ProtectedError):
            self.accession_a.delete()
        with self.assertRaises(ProtectedError):
            self.project.delete()
