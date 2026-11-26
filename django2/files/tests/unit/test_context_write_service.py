from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from files.models import ContextEntity, CoreAuditEvent, DataFile, ExternalIdentifier
from files.services.context_service import (
    ContextConflictError,
    ContextPermissionDenied,
    ContextServiceError,
    create_context,
    create_context_relation,
    replace_context_relation,
    transition_context,
    update_context_draft,
)
from files.services.external_identifier_service import (
    ExternalIdentifierConflict,
    ExternalIdentifierPermissionDenied,
    add_external_identifier,
    remove_external_identifier,
)
from files.services.data_asset_service import (
    AssetContextInput,
    AssetFileInput,
    DataAssetConflictError,
    create_data_asset,
    transition_data_asset,
)
from files.services.project_service import add_project_member, create_project


class ContextWriteServiceTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="context-owner")
        self.manager = users.create_user(username="context-manager")
        self.contributor = users.create_user(username="context-contributor")
        self.viewer = users.create_user(username="context-viewer")
        self.project = create_project(creator=self.owner, project_code="CONTEXT_PROJECT")
        add_project_member(
            project=self.project, actor=self.owner, user=self.manager, role="manager",
            reason="Context manager appointed",
        )
        add_project_member(
            project=self.project, actor=self.owner, user=self.contributor, role="contributor"
        )
        add_project_member(project=self.project, actor=self.manager, user=self.viewer, role="viewer")

    def create_context(self, code, kind="sample", profile="basic_sample", actor=None):
        return create_context(
            context_code=code, project=self.project, context_type_key=kind,
            profile_key=profile, actor=actor or self.contributor,
        )

    def test_create_edit_activate_and_archive_are_audited(self):
        context = self.create_context("SAMPLE_WRITE")
        update_context_draft(
            context=context, actor=self.contributor,
            metadata={"scientific_name": "Oryza sativa", "tissue": "leaf"},
        )
        transition_context(context=context, actor=self.manager, action="activate")
        transition_context(
            context=context, actor=self.owner, action="archive", reason="Sample retired"
        )
        context.refresh_from_db()
        self.assertEqual(context.status, ContextEntity.STATUS_ARCHIVED)
        self.assertEqual(
            list(CoreAuditEvent.objects.filter(context=context).values_list("event_type", flat=True)),
            ["context_created", "context_updated", "context_activated", "context_archived"],
        )

    def test_viewer_and_other_contributor_cannot_edit(self):
        context = self.create_context("SAMPLE_PERMISSION")
        other = get_user_model().objects.create_user(username="other-contributor")
        add_project_member(project=self.project, actor=self.manager, user=other, role="contributor")
        for actor in (self.viewer, other):
            with self.subTest(actor=actor.username), self.assertRaises(ContextPermissionDenied):
                update_context_draft(context=context, actor=actor, name="forbidden")

    def test_context_relation_validates_direction_target_and_cycle(self):
        subject = self.create_context("SUBJECT", "subject", "basic_subject", self.owner)
        other_subject = self.create_context(
            "OTHER_SUBJECT", "subject", "basic_subject", self.owner
        )
        sample = self.create_context("SAMPLE", actor=self.owner)
        relation = create_context_relation(
            source_context=sample, target_context=subject,
            relation_type="collected_from", actor=self.owner,
        )
        self.assertEqual(relation.target_context, subject)
        replaced = replace_context_relation(
            relation=relation, target_context=other_subject, actor=self.owner
        )
        self.assertEqual(replaced.target_context, other_subject)
        with self.assertRaises(ContextServiceError):
            create_context_relation(
                source_context=subject, target_context=sample,
                relation_type="collected_from", actor=self.owner,
            )

    def test_referenced_active_context_cannot_be_archived(self):
        context = self.create_context("SAMPLE_ACTIVE")
        transition_context(context=context, actor=self.manager, action="activate")
        data_file = DataFile.objects.create(
            file_code="CONTEXT_FREEZE_FILE", file_name="reads.fastq.gz",
            file_path="/not-used/context-freeze.fastq.gz", file_size=1,
            sha256="f" * 64, availability_status=DataFile.AVAILABILITY_AVAILABLE,
        )
        asset = create_data_asset(
            asset_code="CONTEXT_FREEZE_ASSET", project=self.project,
            data_type_key="sequence", profile_key="raw_read_collection",
            created_by=self.owner,
            file_memberships=[AssetFileInput(data_file, "read_fastq")],
            context_links=[AssetContextInput(context, "source_sample")],
        )
        transition_data_asset(asset=asset, actor=self.owner, action="submit")
        with self.assertRaises(ContextConflictError):
            transition_context(
                context=context, actor=self.owner, action="archive", reason="still referenced"
            )

    def test_archived_context_cannot_be_target_of_new_relations(self):
        subject = self.create_context(
            "ARCHIVED_SUBJECT", "subject", "basic_subject", self.owner
        )
        transition_context(context=subject, actor=self.manager, action="activate")
        transition_context(
            context=subject, actor=self.owner, action="archive", reason="Subject retired"
        )
        sample = self.create_context("SOURCE_SAMPLE", actor=self.owner)
        with self.assertRaisesRegex(ContextConflictError, "archived ContextEntity"):
            create_context_relation(
                source_context=sample,
                target_context=subject,
                relation_type="collected_from",
                actor=self.owner,
            )

        archived_sample = self.create_context("ARCHIVED_SAMPLE", actor=self.owner)
        transition_context(context=archived_sample, actor=self.manager, action="activate")
        transition_context(
            context=archived_sample,
            actor=self.owner,
            action="archive",
            reason="Sample retired",
        )
        with self.assertRaisesRegex(DataAssetConflictError, "archived ContextEntity"):
            create_data_asset(
                asset_code="ARCHIVED_CONTEXT_ASSET",
                project=self.project,
                data_type_key="sequence",
                profile_key="raw_read_collection",
                created_by=self.owner,
                context_links=[
                    AssetContextInput(archived_sample, "source_sample")
                ],
            )

    def test_external_identifier_normalizes_is_unique_and_updates_audit(self):
        context = self.create_context("SAMPLE_IDENTIFIER")
        identifier = add_external_identifier(
            namespace_key="biosample", display_value=" samn12345 ",
            context=context, actor=self.contributor,
        )
        self.assertEqual(identifier.normalized_value, "SAMN12345")
        with self.assertRaises(ExternalIdentifierConflict):
            add_external_identifier(
                namespace_key="biosample", display_value="SAMN12345",
                context=context, actor=self.contributor,
            )
        remove_external_identifier(identifier=identifier, actor=self.contributor)
        self.assertFalse(ExternalIdentifier.objects.filter(pk=identifier.pk).exists())
        self.assertEqual(
            CoreAuditEvent.objects.filter(context=context, event_type="context_updated").count(), 2
        )

    def test_external_identifier_rejects_wrong_kind_and_frozen_target(self):
        context = self.create_context("SAMPLE_IDENTIFIER_POLICY")
        with self.assertRaisesRegex(Exception, "target kind"):
            add_external_identifier(
                namespace_key="bioproject", display_value="PRJNA12345",
                context=context, actor=self.contributor,
            )
        transition_context(context=context, actor=self.manager, action="activate")
        with self.assertRaises(ExternalIdentifierPermissionDenied):
            add_external_identifier(
                namespace_key="biosample", display_value="SAMN54321",
                context=context, actor=self.manager,
            )

    def test_context_profile_switch_revalidates_existing_external_identifiers(self):
        context = self.create_context("SAMPLE_PROFILE_SWITCH")
        add_external_identifier(
            namespace_key="biosample",
            display_value="SAMN98765",
            context=context,
            actor=self.contributor,
        )

        with self.assertRaisesRegex(ContextServiceError, "external identifiers"):
            update_context_draft(
                context=context,
                actor=self.contributor,
                context_type_key="subject",
                profile_key="basic_subject",
            )

        context.refresh_from_db()
        self.assertEqual(context.context_type_key, "sample")
        self.assertEqual(context.profile_key, "basic_sample")

    def test_context_transition_rolls_back_when_audit_append_fails(self):
        context = self.create_context("CONTEXT_AUDIT_ROLLBACK")
        with patch(
            "files.services.context_service.append_core_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ), self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            transition_context(context=context, actor=self.manager, action="activate")
        context.refresh_from_db()
        self.assertEqual(context.status, ContextEntity.STATUS_DRAFT)
