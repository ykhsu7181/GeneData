from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from files.models import (
    AssetContextLink,
    ContextEntity,
    ContextRelation,
    DataAsset,
    DataAssetRelation,
    ExternalIdentifier,
    Project,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class CoreContextModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="core-context-owner")
        self.project = Project.objects.create(project_code="PROJECT_CORE_CONTEXT")
        registry = load_data_asset_registry()
        asset_profile = registry.get_profile("sequence", "reference_genome")
        context_profile = registry.resolve_current_context_profile("sample", "basic_sample")
        self.asset = DataAsset.objects.create(
            asset_code="ASSET_CORE_CONTEXT",
            project=self.project,
            data_type_key=asset_profile.data_type_key,
            profile_key=asset_profile.profile_key,
            schema_version=asset_profile.schema_version,
            schema_digest=asset_profile.schema_digest,
            created_by=self.user,
        )
        self.other_asset = DataAsset.objects.create(
            asset_code="ASSET_CORE_CONTEXT_OTHER",
            project=self.project,
            data_type_key=asset_profile.data_type_key,
            profile_key=asset_profile.profile_key,
            schema_version=asset_profile.schema_version,
            schema_digest=asset_profile.schema_digest,
            created_by=self.user,
        )
        self.context = self.create_context("CONTEXT_SAMPLE_A", context_profile)
        self.other_context = self.create_context("CONTEXT_SAMPLE_B", context_profile)

    def create_context(self, code, profile):
        return ContextEntity.objects.create(
            context_code=code,
            project=self.project,
            context_type_key=profile.context_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            created_by=self.user,
        )

    def relation_fields(self, relation_type):
        rule = load_data_asset_registry().resolve_current_relation(relation_type)
        return {
            "relation_type": rule.key,
            "relation_rule_version": rule.version,
            "relation_rule_digest": rule.digest,
            "created_by": self.user,
        }

    def test_context_defaults_and_reverse_asset_query(self):
        AssetContextLink.objects.create(
            asset=self.asset,
            context=self.context,
            position=0,
            **self.relation_fields("source_sample"),
        )
        self.assertEqual(self.context.status, ContextEntity.STATUS_DRAFT)
        self.assertEqual(self.context.metadata, {})
        self.assertEqual(self.context.asset_links.get().asset, self.asset)
        self.assertEqual(self.asset.context_links.get().context, self.context)

    def test_asset_relation_rejects_self_and_duplicate(self):
        fields = self.relation_fields("uses_reference")
        with self.assertRaises(IntegrityError), transaction.atomic():
            DataAssetRelation.objects.create(
                source_asset=self.asset,
                target_asset=self.asset,
                **fields,
            )
        DataAssetRelation.objects.create(
            source_asset=self.asset,
            target_asset=self.other_asset,
            **fields,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            DataAssetRelation.objects.create(
                source_asset=self.asset,
                target_asset=self.other_asset,
                **fields,
            )

    def test_context_relation_rejects_self_and_supports_reverse_queries(self):
        fields = self.relation_fields("collected_from")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContextRelation.objects.create(
                source_context=self.context,
                target_context=self.context,
                **fields,
            )
        relation = ContextRelation.objects.create(
            source_context=self.context,
            target_context=self.other_context,
            **fields,
        )
        self.assertEqual(self.context.outgoing_context_relations.get(), relation)
        self.assertEqual(self.other_context.incoming_context_relations.get(), relation)

    def test_asset_context_position_and_relation_are_unique(self):
        fields = self.relation_fields("source_sample")
        AssetContextLink.objects.create(
            asset=self.asset,
            context=self.context,
            position=0,
            **fields,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetContextLink.objects.create(
                asset=self.asset,
                context=self.other_context,
                position=0,
                **fields,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetContextLink.objects.create(
                asset=self.asset,
                context=self.context,
                position=1,
                **fields,
            )

    def test_external_identifier_requires_exactly_one_target(self):
        namespace = load_data_asset_registry().resolve_current_namespace("biosample")
        base = {
            "namespace_key": namespace.key,
            "namespace_version": namespace.version,
            "namespace_digest": namespace.digest,
            "normalized_value": "SAMN00000001",
            "display_value": "SAMN00000001",
            "created_by": self.user,
        }
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExternalIdentifier.objects.create(**base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExternalIdentifier.objects.create(project=self.project, context=self.context, **base)
        identifier = ExternalIdentifier.objects.create(context=self.context, **base)
        self.assertEqual(identifier.context, self.context)

    def test_external_identifier_unique_space_crosses_namespace_versions(self):
        ExternalIdentifier.objects.create(
            namespace_key="biosample",
            namespace_version="1",
            namespace_digest="a" * 64,
            normalized_value="SAMN00000002",
            display_value="SAMN00000002",
            context=self.context,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExternalIdentifier.objects.create(
                namespace_key="biosample",
                namespace_version="2",
                namespace_digest="b" * 64,
                normalized_value="SAMN00000002",
                display_value="SAMN00000002",
                context=self.other_context,
                created_by=self.user,
            )

    def test_external_identifier_protects_target_deletion(self):
        ExternalIdentifier.objects.create(
            namespace_key="biosample",
            namespace_version="1",
            namespace_digest="a" * 64,
            normalized_value="SAMN00000003",
            display_value="SAMN00000003",
            context=self.context,
            created_by=self.user,
        )
        with self.assertRaises(ProtectedError):
            self.context.delete()

    def test_project_and_creator_are_protected_while_context_exists(self):
        with self.assertRaises(ProtectedError):
            self.project.delete()
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_invalid_context_status_is_rejected(self):
        profile = load_data_asset_registry().resolve_current_context_profile(
            "sample", "basic_sample"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContextEntity.objects.create(
                context_code="CONTEXT_INVALID_STATUS",
                project=self.project,
                context_type_key=profile.context_type_key,
                profile_key=profile.profile_key,
                schema_version=profile.schema_version,
                schema_digest=profile.schema_digest,
                status="published",
                created_by=self.user,
            )

    def test_relation_rows_cascade_with_their_endpoints(self):
        DataAssetRelation.objects.create(
            source_asset=self.asset,
            target_asset=self.other_asset,
            **self.relation_fields("uses_reference"),
        )
        AssetContextLink.objects.create(
            asset=self.asset,
            context=self.context,
            position=0,
            **self.relation_fields("source_sample"),
        )
        ContextRelation.objects.create(
            source_context=self.context,
            target_context=self.other_context,
            **self.relation_fields("collected_from"),
        )

        self.other_asset.delete()
        self.assertFalse(DataAssetRelation.objects.exists())
        self.other_context.delete()
        self.assertFalse(ContextRelation.objects.exists())
        self.asset.delete()
        self.assertFalse(AssetContextLink.objects.exists())

    def test_external_identifier_protects_each_target_kind(self):
        identifiers = [
            ExternalIdentifier(
                namespace_key="bioproject",
                namespace_version="1",
                namespace_digest="a" * 64,
                normalized_value="PRJNA000001",
                display_value="PRJNA000001",
                project=self.project,
                created_by=self.user,
            ),
            ExternalIdentifier(
                namespace_key="assembly_accession",
                namespace_version="1",
                namespace_digest="b" * 64,
                normalized_value="GCA_000000001.1",
                display_value="GCA_000000001.1",
                asset=self.asset,
                created_by=self.user,
            ),
        ]
        ExternalIdentifier.objects.bulk_create(identifiers)

        with self.assertRaises(ProtectedError):
            self.project.delete()
        with self.assertRaises(ProtectedError):
            self.asset.delete()
