from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    AssetFileMembership,
    DataAsset,
    DataAssetAccession,
    DataAssetAnnotation,
    DataAssetAssembly,
    DataAssetSample,
    DataFile,
    Project,
    Sample,
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
        self.sample_a = Sample.objects.create(sample_code="SAMPLE_ASSET_A")
        self.sample_b = Sample.objects.create(sample_code="SAMPLE_ASSET_B")
        self.assembly = Assembly.objects.create(
            accession=self.accession_a,
            name="ASSEMBLY_ASSET_TEST",
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession_a,
            name="ANNOTATION_ASSET_TEST",
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

    def test_asset_can_link_multiple_samples_without_roles(self):
        asset = self.create_asset("ASSET_SAMPLE_CONTEXTS")

        DataAssetSample.objects.create(
            asset=asset,
            sample=self.sample_a,
            created_by=self.user,
        )
        DataAssetSample.objects.create(
            asset=asset,
            sample=self.sample_b,
            created_by=self.user,
        )

        self.assertEqual(asset.sample_links.count(), 2)
        field_names = {field.name for field in DataAssetSample._meta.fields}
        self.assertFalse({"relation_role", "is_primary", "primary_slot"} & field_names)

    def test_context_links_reject_duplicate_targets(self):
        asset = self.create_asset("ASSET_DUPLICATE_CONTEXTS")
        relations = (
            (DataAssetSample, "sample", self.sample_a),
            (DataAssetAssembly, "assembly", self.assembly),
            (DataAssetAnnotation, "annotation", self.annotation),
        )

        for model, target_field, target in relations:
            with self.subTest(model=model.__name__):
                values = {"asset": asset, target_field: target}
                model.objects.create(**values)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.create(**values)

    def test_context_targets_are_protected_while_linked(self):
        asset = self.create_asset("ASSET_PROTECTED_CONTEXTS")
        DataAssetSample.objects.create(asset=asset, sample=self.sample_a)
        DataAssetAssembly.objects.create(asset=asset, assembly=self.assembly)
        DataAssetAnnotation.objects.create(asset=asset, annotation=self.annotation)

        for target in (self.sample_a, self.assembly, self.annotation):
            with self.subTest(target=target.__class__.__name__):
                with self.assertRaises(ProtectedError):
                    target.delete()

    def test_deleting_asset_cascades_context_links_only(self):
        asset = self.create_asset("ASSET_CONTEXT_CASCADE")
        DataAssetSample.objects.create(asset=asset, sample=self.sample_a)
        DataAssetAssembly.objects.create(asset=asset, assembly=self.assembly)
        DataAssetAnnotation.objects.create(asset=asset, annotation=self.annotation)

        asset.delete()

        self.assertFalse(DataAssetSample.objects.exists())
        self.assertFalse(DataAssetAssembly.objects.exists())
        self.assertFalse(DataAssetAnnotation.objects.exists())
        self.assertTrue(Sample.objects.filter(pk=self.sample_a.pk).exists())
        self.assertTrue(Assembly.objects.filter(pk=self.assembly.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=self.annotation.pk).exists())
