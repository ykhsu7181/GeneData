from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from files.models import (
    AssetContextLink,
    AssetFileMembership,
    ContextEntity,
    DataAccessToken,
    DataAsset,
    DataAssetRelation,
    DataFile,
    Project,
    ProjectMembership,
)
from files.services.data_asset_access_service import (
    filter_visible_contexts,
    filter_visible_data_assets,
    project_context_for_asset,
    resolve_context_access,
    resolve_data_asset_access,
    resolve_data_asset_file_access,
    resolve_data_asset_relation_access,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class DataAssetAccessServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="asset-owner")
        self.manager = user_model.objects.create_user(username="asset-manager")
        self.contributor = user_model.objects.create_user(username="asset-contributor")
        self.viewer = user_model.objects.create_user(username="asset-viewer")
        self.creator = user_model.objects.create_user(username="asset-creator")
        self.nonmember = user_model.objects.create_user(username="asset-nonmember")
        self.inactive = user_model.objects.create_user(
            username="asset-inactive", is_active=False
        )
        self.project = Project.objects.create(project_code="PROJECT_ASSET_ACCESS")
        self.other_project = Project.objects.create(project_code="PROJECT_ASSET_OTHER")
        for user, role in (
            (self.owner, ProjectMembership.ROLE_OWNER),
            (self.manager, ProjectMembership.ROLE_MANAGER),
            (self.contributor, ProjectMembership.ROLE_CONTRIBUTOR),
            (self.viewer, ProjectMembership.ROLE_VIEWER),
            (self.creator, ProjectMembership.ROLE_CONTRIBUTOR),
            (self.inactive, ProjectMembership.ROLE_VIEWER),
        ):
            ProjectMembership.objects.create(
                project=self.project,
                user=user,
                role=role,
                created_by=self.owner,
            )

        registry = load_data_asset_registry()
        self.asset_profile = registry.resolve_current_asset_profile(
            "sequence", "raw_read_collection"
        )
        self.context_profile = registry.resolve_current_context_profile(
            "sample", "basic_sample"
        )
        self.relation_rule = registry.resolve_current_relation("uses_reference")
        self.context_link_rule = registry.resolve_current_relation("source_sample")
        self.public_asset = self.create_asset(
            "ASSET_PUBLIC",
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )

    def create_asset(
        self,
        code,
        *,
        project=None,
        status=DataAsset.STATUS_DRAFT,
        visibility=DataAsset.VISIBILITY_PRIVATE,
        created_by=None,
    ):
        return DataAsset.objects.create(
            asset_code=code,
            project=project or self.project,
            data_type_key=self.asset_profile.data_type_key,
            profile_key=self.asset_profile.profile_key,
            schema_version=self.asset_profile.schema_version,
            schema_digest=self.asset_profile.schema_digest,
            status=status,
            visibility=visibility,
            created_by=created_by or self.creator,
            published_at=(
                timezone.now() if status == DataAsset.STATUS_RELEASED else None
            ),
        )

    def create_context(self, code="CONTEXT_ACCESS"):
        return ContextEntity.objects.create(
            context_code=code,
            project=self.project,
            context_type_key=self.context_profile.context_type_key,
            profile_key=self.context_profile.profile_key,
            schema_version=self.context_profile.schema_version,
            schema_digest=self.context_profile.schema_digest,
            status=ContextEntity.STATUS_ACTIVE,
            metadata={
                "scientific_name": "Oryza sativa",
                "tissue": "leaf",
                "collection_method": "field",
                "treatment": "control",
            },
            description="private context description",
            created_by=self.creator,
        )

    def link_context(self, asset, context):
        return AssetContextLink.objects.create(
            asset=asset,
            context=context,
            relation_type=self.context_link_rule.key,
            relation_rule_version=self.context_link_rule.version,
            relation_rule_digest=self.context_link_rule.digest,
            created_by=self.creator,
        )

    def create_relation(self, source, target):
        return DataAssetRelation.objects.create(
            source_asset=source,
            target_asset=target,
            relation_type=self.relation_rule.key,
            relation_rule_version=self.relation_rule.version,
            relation_rule_digest=self.relation_rule.digest,
            created_by=self.creator,
        )

    def test_released_public_is_visible_to_anonymous_and_nonmember(self):
        self.assertTrue(resolve_data_asset_access(self.public_asset).allowed)
        self.assertTrue(
            resolve_data_asset_access(self.public_asset, user=self.nonmember).allowed
        )

    def test_unreleased_public_uses_private_read_rule(self):
        asset = self.create_asset(
            "ASSET_PUBLIC_DRAFT", visibility=DataAsset.VISIBILITY_PUBLIC
        )

        self.assertFalse(resolve_data_asset_access(asset).allowed)
        self.assertTrue(resolve_data_asset_access(asset, user=self.creator).allowed)
        self.assertTrue(resolve_data_asset_access(asset, user=self.owner).allowed)
        self.assertTrue(resolve_data_asset_access(asset, user=self.manager).allowed)
        self.assertFalse(resolve_data_asset_access(asset, user=self.contributor).allowed)
        self.assertFalse(resolve_data_asset_access(asset, user=self.viewer).allowed)
        self.assertFalse(resolve_data_asset_access(asset, user=self.nonmember).allowed)

    def test_private_and_internal_rules_are_distinct(self):
        private = self.create_asset("ASSET_PRIVATE")
        internal = self.create_asset(
            "ASSET_INTERNAL", visibility=DataAsset.VISIBILITY_INTERNAL
        )

        self.assertTrue(resolve_data_asset_access(private, user=self.creator).allowed)
        self.assertTrue(resolve_data_asset_access(private, user=self.owner).allowed)
        self.assertFalse(resolve_data_asset_access(private, user=self.viewer).allowed)
        self.assertTrue(resolve_data_asset_access(internal, user=self.viewer).allowed)
        self.assertTrue(resolve_data_asset_access(internal, user=self.contributor).allowed)
        self.assertFalse(resolve_data_asset_access(internal, user=self.nonmember).allowed)
        self.assertFalse(resolve_data_asset_access(internal, user=self.inactive).allowed)

    def test_archived_never_expands_visibility(self):
        archived_public = self.create_asset(
            "ASSET_ARCHIVED_PUBLIC",
            status=DataAsset.STATUS_ARCHIVED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        archived_internal = self.create_asset(
            "ASSET_ARCHIVED_INTERNAL",
            status=DataAsset.STATUS_ARCHIVED,
            visibility=DataAsset.VISIBILITY_INTERNAL,
        )

        self.assertFalse(resolve_data_asset_access(archived_public).allowed)
        self.assertFalse(
            resolve_data_asset_access(archived_public, user=self.viewer).allowed
        )
        self.assertTrue(
            resolve_data_asset_access(archived_public, user=self.creator).allowed
        )
        self.assertTrue(resolve_data_asset_access(archived_public, user=self.owner).allowed)
        self.assertTrue(
            resolve_data_asset_access(archived_internal, user=self.viewer).allowed
        )

    def test_membership_changes_take_effect_immediately(self):
        private = self.create_asset("ASSET_ROLE_CHANGE", created_by=self.creator)
        membership = ProjectMembership.objects.get(
            project=self.project, user=self.viewer
        )
        self.assertFalse(resolve_data_asset_access(private, user=self.viewer).allowed)

        membership.role = ProjectMembership.ROLE_MANAGER
        membership.save(update_fields=["role", "updated_at"])
        self.assertTrue(resolve_data_asset_access(private, user=self.viewer).allowed)

        membership.delete()
        self.assertFalse(resolve_data_asset_access(private, user=self.viewer).allowed)

    def test_queryset_filter_matches_single_object_decisions(self):
        self.create_asset("ASSET_FILTER_PRIVATE")
        self.create_asset(
            "ASSET_FILTER_INTERNAL", visibility=DataAsset.VISIBILITY_INTERNAL
        )
        self.create_asset(
            "ASSET_FILTER_PUBLIC_DRAFT", visibility=DataAsset.VISIBILITY_PUBLIC
        )
        assets = list(DataAsset.objects.filter(asset_code__startswith="ASSET_"))

        for user in (None, self.owner, self.viewer, self.creator, self.nonmember):
            expected = {
                asset.pk
                for asset in assets
                if resolve_data_asset_access(asset, user=user).allowed
            }
            actual = set(
                filter_visible_data_assets(
                    DataAsset.objects.filter(pk__in=[asset.pk for asset in assets]),
                    user=user,
                ).values_list("pk", flat=True)
            )
            self.assertEqual(actual, expected)

    def test_context_full_access_requires_current_project_membership(self):
        context = self.create_context()

        self.assertTrue(resolve_context_access(context, user=self.viewer).allowed)
        self.assertFalse(resolve_context_access(context, user=self.nonmember).allowed)
        self.assertFalse(resolve_context_access(context, user=self.inactive).allowed)
        self.assertEqual(
            list(filter_visible_contexts(ContextEntity.objects.all(), user=self.viewer)),
            [context],
        )
        self.assertFalse(
            filter_visible_contexts(
                ContextEntity.objects.all(), user=self.nonmember
            ).exists()
        )

    def test_context_projection_only_returns_profile_public_fields(self):
        context = self.create_context()
        self.link_context(self.public_asset, context)

        public = project_context_for_asset(self.public_asset, context)
        member = project_context_for_asset(
            self.public_asset, context, user=self.viewer
        )

        self.assertTrue(public.allowed)
        self.assertFalse(public.full)
        self.assertEqual(
            public.metadata,
            {"scientific_name": "Oryza sativa", "tissue": "leaf"},
        )
        self.assertTrue(member.allowed)
        self.assertTrue(member.full)
        self.assertEqual(member.metadata, context.metadata)
        self.assertNotIn("description", public.metadata)

    def test_context_projection_requires_visible_linked_asset(self):
        context = self.create_context()
        hidden = self.create_asset("ASSET_HIDDEN_CONTEXT")
        self.link_context(hidden, context)

        self.assertEqual(
            project_context_for_asset(hidden, context, user=self.nonmember).reason,
            "asset_not_visible",
        )
        self.assertEqual(
            project_context_for_asset(self.public_asset, context).reason,
            "context_not_asset_member",
        )

    def test_cross_project_reference_is_reauthorized_on_every_use(self):
        source = self.create_asset(
            "ASSET_REL_SOURCE",
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
        )
        target = self.create_asset(
            "ASSET_REL_TARGET",
            project=self.other_project,
            status=DataAsset.STATUS_RELEASED,
            visibility=DataAsset.VISIBILITY_PUBLIC,
            created_by=self.nonmember,
        )
        relation = self.create_relation(source, target)

        self.assertTrue(resolve_data_asset_relation_access(relation).allowed)
        target.visibility = DataAsset.VISIBILITY_PRIVATE
        target.save(update_fields=["visibility"])
        self.assertEqual(
            resolve_data_asset_relation_access(relation).reason,
            "cross_project_target_not_public_released",
        )

    def test_same_project_relation_authorizes_both_endpoints(self):
        source = self.create_asset(
            "ASSET_REL_INTERNAL",
            visibility=DataAsset.VISIBILITY_INTERNAL,
        )
        target = self.create_asset("ASSET_REL_PRIVATE")
        relation = self.create_relation(source, target)

        self.assertEqual(
            resolve_data_asset_relation_access(relation, user=self.viewer).reason,
            "relation_target_not_visible",
        )
        self.assertTrue(
            resolve_data_asset_relation_access(relation, user=self.owner).allowed
        )

    def test_file_access_requires_visible_explicit_membership(self):
        data_file = DataFile.objects.create(
            file_code="FILE_ASSET_ACCESS",
            file_name="reads.fastq.gz",
            file_path="/not-used/reads.fastq.gz",
        )
        AssetFileMembership.objects.create(
            asset=self.public_asset,
            data_file=data_file,
            file_role="read_fastq",
            created_by=self.creator,
        )
        unrelated = DataFile.objects.create(
            file_code="FILE_ASSET_UNRELATED",
            file_name="unrelated.fastq.gz",
            file_path="/not-used/unrelated.fastq.gz",
        )

        self.assertTrue(
            resolve_data_asset_file_access(self.public_asset, data_file).allowed
        )
        self.assertEqual(
            resolve_data_asset_file_access(self.public_asset, unrelated).reason,
            "file_not_asset_member",
        )

    def test_old_data_access_token_is_not_a_new_warehouse_principal(self):
        token, _raw = DataAccessToken.issue(
            name="legacy-token",
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )
        internal = self.create_asset(
            "ASSET_TOKEN_REJECTED", visibility=DataAsset.VISIBILITY_INTERNAL
        )

        self.assertEqual(
            resolve_data_asset_access(internal, user=token).reason,
            "authentication_required",
        )

    def test_unknown_state_or_visibility_fails_closed(self):
        self.public_asset.status = "unexpected"
        self.assertEqual(
            resolve_data_asset_access(self.public_asset).reason,
            "asset_status_unknown",
        )
        self.public_asset.status = DataAsset.STATUS_RELEASED
        self.public_asset.visibility = "unexpected"
        self.assertEqual(
            resolve_data_asset_access(self.public_asset).reason,
            "asset_visibility_unknown",
        )
