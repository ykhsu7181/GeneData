from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    AnnotationFeatureIndex,
    Assembly,
    DataAsset,
    DataFile,
    Project,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class AnnotationFeatureIndexTargetConstraintTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="gate-c-index-owner")
        project = Project.objects.create(project_code="PROJECT_GATE_C_INDEX")
        profile = load_data_asset_registry().resolve_current_asset_profile(
            "feature", "genome_annotation"
        )
        self.annotation_asset = DataAsset.objects.create(
            asset_code="ASSET_GATE_C_ANNOTATION",
            project=project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            created_by=user,
        )
        accession = Accession.objects.create(accession="GATE_C_ACCESSION")
        assembly = Assembly.objects.create(
            accession=accession,
            name="gate-c-assembly",
        )
        self.legacy_annotation = Annotation.objects.create(
            assembly=assembly,
            accession=accession,
            name="gate-c-annotation",
        )
        self.source_file = DataFile.objects.create(
            file_code="FILE_GATE_C_GFF",
            file_name="gate-c.gff3",
            file_path="/not-used/gate-c.gff3",
        )

    def index_values(self):
        return {
            "source_file": self.source_file,
            "source_file_size": 0,
            "source_file_mtime_ns": 0,
        }

    def test_legacy_annotation_target_remains_valid(self):
        index = AnnotationFeatureIndex.objects.create(
            annotation=self.legacy_annotation,
            **self.index_values(),
        )

        self.assertEqual(index.annotation, self.legacy_annotation)
        self.assertIsNone(index.annotation_asset_id)

    def test_new_annotation_asset_target_is_valid(self):
        index = AnnotationFeatureIndex.objects.create(
            annotation_asset=self.annotation_asset,
            **self.index_values(),
        )

        self.assertEqual(index.annotation_asset, self.annotation_asset)
        self.assertIsNone(index.annotation_id)

    def test_target_is_required(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnnotationFeatureIndex.objects.create(**self.index_values())

    def test_legacy_and_new_targets_are_mutually_exclusive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnnotationFeatureIndex.objects.create(
                annotation=self.legacy_annotation,
                annotation_asset=self.annotation_asset,
                **self.index_values(),
            )
