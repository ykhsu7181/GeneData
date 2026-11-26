from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from files.models import (
    CORE_AUDIT_EVENT_TYPES,
    ContextEntity,
    CoreAuditEvent,
    CoreAuditEventImmutableError,
    DataAsset,
    Project,
)
from files.services.core_audit_service import (
    CORE_AUDIT_DIGEST_ALGORITHM,
    EVENT_RULES,
    CoreAuditValidationError,
    append_core_audit_event,
    compute_core_audit_digest,
)
from files.services.data_asset_registry_service import load_data_asset_registry


class CoreAuditServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.actor = user_model.objects.create_user(username="audit-actor")
        self.subject = user_model.objects.create_user(username="audit-subject")
        self.creator = user_model.objects.create_user(username="audit-object-creator")
        self.project = Project.objects.create(project_code="PROJECT_CORE_AUDIT")
        self.other_project = Project.objects.create(project_code="PROJECT_CORE_AUDIT_OTHER")
        registry = load_data_asset_registry()
        asset_profile = registry.get_profile("sequence", "reference_genome")
        context_profile = registry.resolve_current_context_profile("sample", "basic_sample")
        self.asset = self.create_asset("ASSET_CORE_AUDIT", self.project, asset_profile)
        self.other_asset = self.create_asset(
            "ASSET_CORE_AUDIT_OTHER", self.other_project, asset_profile
        )
        self.context = ContextEntity.objects.create(
            context_code="CONTEXT_CORE_AUDIT",
            project=self.project,
            context_type_key=context_profile.context_type_key,
            profile_key=context_profile.profile_key,
            schema_version=context_profile.schema_version,
            schema_digest=context_profile.schema_digest,
            created_by=self.creator,
        )

    def create_asset(self, code, project, profile):
        return DataAsset.objects.create(
            asset_code=code,
            project=project,
            data_type_key=profile.data_type_key,
            profile_key=profile.profile_key,
            schema_version=profile.schema_version,
            schema_digest=profile.schema_digest,
            created_by=self.creator,
        )

    def append(self, event_type, **overrides):
        fields = {
            "project": self.project,
            "actor": self.actor,
            "event_type": event_type,
        }
        fields.update(overrides)
        return append_core_audit_event(**fields)

    def test_service_rules_cover_exactly_the_model_event_types(self):
        self.assertEqual(set(EVENT_RULES), set(CORE_AUDIT_EVENT_TYPES))
        self.assertEqual(
            set(dict(CoreAuditEvent.EVENT_TYPE_CHOICES)),
            set(CORE_AUDIT_EVENT_TYPES),
        )

    def test_service_appends_all_approved_event_types(self):
        content_a = {"name": "record", "metadata": {"version": 1}}
        content_b = {"name": "record", "metadata": {"version": 2}}
        payloads = {
            "membership_added": {"subject_user": self.subject, "to_value": "viewer"},
            "membership_role_changed": {
                "subject_user": self.subject,
                "from_value": "viewer",
                "to_value": "contributor",
            },
            "membership_removed": {"subject_user": self.subject, "from_value": "viewer"},
            "context_created": {
                "context": self.context,
                "to_value": "draft",
                "after_content": content_a,
            },
            "context_updated": {
                "context": self.context,
                "before_content": content_a,
                "after_content": content_b,
            },
            "context_activated": {
                "context": self.context,
                "from_value": "draft",
                "to_value": "active",
            },
            "context_archived": {
                "context": self.context,
                "from_value": "active",
                "to_value": "archived",
                "reason": "Context is no longer active.",
            },
            "asset_created": {
                "asset": self.asset,
                "to_value": "draft",
                "after_content": content_a,
            },
            "asset_updated": {
                "asset": self.asset,
                "before_content": content_a,
                "after_content": content_b,
            },
            "asset_submitted": {
                "asset": self.asset,
                "from_value": "draft",
                "to_value": "submitted",
            },
            "asset_returned": {
                "asset": self.asset,
                "from_value": "submitted",
                "to_value": "draft",
                "reason": "Required metadata is missing.",
            },
            "asset_approved": {
                "asset": self.asset,
                "from_value": "submitted",
                "to_value": "approved",
            },
            "asset_approval_withdrawn": {
                "asset": self.asset,
                "from_value": "approved",
                "to_value": "draft",
                "reason": "The approved contract changed.",
            },
            "asset_released": {
                "asset": self.asset,
                "from_value": "approved",
                "to_value": "released",
            },
            "asset_archived": {
                "asset": self.asset,
                "from_value": "released",
                "to_value": "archived",
                "reason": "Superseded by a newer released asset.",
            },
        }

        for event_type, fields in payloads.items():
            with self.subTest(event_type=event_type):
                event = self.append(event_type, **fields)
                self.assertEqual(event.event_type, event_type)
        self.assertEqual(CoreAuditEvent.objects.count(), len(CORE_AUDIT_EVENT_TYPES))

    def test_canonical_digest_is_stable_and_normalizes_unicode(self):
        decomposed = "A\u030A"
        composed = "Å"
        first = {
            "metadata": {"tags": ["reference", "v1"], "label": decomposed},
            "name": "水稻",
        }
        same_content_different_order = {
            "name": "水稻",
            "metadata": {"label": composed, "tags": ["reference", "v1"]},
        }

        self.assertEqual(CORE_AUDIT_DIGEST_ALGORITHM, "canonical-json-sha256-v1")
        self.assertEqual(
            compute_core_audit_digest(first),
            compute_core_audit_digest(same_content_different_order),
        )
        self.assertEqual(
            compute_core_audit_digest(first),
            "a5abaeb27a9d713dea010c85dc3c8e7036943bf4b9d86b3bb144903893c4d721",
        )

    def test_service_rejects_unknown_event_wrong_target_and_cross_project_target(self):
        with self.assertRaises(CoreAuditValidationError):
            self.append("custom_event", asset=self.asset)
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_submitted",
                context=self.context,
                from_value="draft",
                to_value="submitted",
            )
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_submitted",
                asset=self.other_asset,
                from_value="draft",
                to_value="submitted",
            )

    def test_service_rejects_invalid_transition_digest_and_missing_reason(self):
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_submitted",
                asset=self.asset,
                from_value="approved",
                to_value="submitted",
            )
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_updated",
                asset=self.asset,
                before_content={"name": "unchanged"},
                after_content={"name": "unchanged"},
            )
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_created",
                asset=self.asset,
                to_value="draft",
                after_content={"invalid": {"set-value"}},
            )
        with self.assertRaises(CoreAuditValidationError):
            self.append(
                "asset_archived",
                asset=self.asset,
                from_value="released",
                to_value="archived",
                reason="   ",
            )
        for privileged_role in ("owner", "manager"):
            with self.subTest(privileged_role=privileged_role), self.assertRaises(
                CoreAuditValidationError
            ):
                self.append(
                    "membership_added",
                    subject_user=self.subject,
                    to_value=privileged_role,
                )

    def test_database_rejects_target_transition_digest_and_reason_violations(self):
        base = {"project": self.project, "actor": self.actor}
        invalid_rows = [
            {
                **base,
                "event_type": "custom_event",
                "asset": self.asset,
            },
            {
                **base,
                "event_type": "asset_submitted",
                "from_value": "draft",
                "to_value": "submitted",
            },
            {
                **base,
                "event_type": "asset_submitted",
                "asset": self.asset,
                "context": self.context,
                "from_value": "draft",
                "to_value": "submitted",
            },
            {
                **base,
                "event_type": "asset_submitted",
                "context": self.context,
                "from_value": "draft",
                "to_value": "submitted",
            },
            {
                **base,
                "event_type": "asset_submitted",
                "asset": self.asset,
                "from_value": "approved",
                "to_value": "submitted",
            },
            {
                **base,
                "event_type": "asset_created",
                "asset": self.asset,
                "to_value": "draft",
            },
            {
                **base,
                "event_type": "asset_archived",
                "asset": self.asset,
                "from_value": "released",
                "to_value": "archived",
            },
            {
                **base,
                "event_type": "membership_added",
                "subject_user": self.subject,
                "to_value": "owner",
            },
            {
                **base,
                "event_type": "membership_role_changed",
                "subject_user": self.subject,
                "from_value": "owner",
                "to_value": "manager",
            },
            {
                **base,
                "event_type": "membership_removed",
                "subject_user": self.subject,
                "from_value": "owner",
            },
            {
                **base,
                "event_type": "membership_added",
                "subject_user": self.subject,
                "to_value": "manager",
            },
            {
                **base,
                "event_type": "membership_role_changed",
                "subject_user": self.subject,
                "from_value": "manager",
                "to_value": "contributor",
            },
            {
                **base,
                "event_type": "membership_removed",
                "subject_user": self.subject,
                "from_value": "manager",
            },
        ]
        for fields in invalid_rows:
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                CoreAuditEvent.objects.create(**fields)

    def test_event_is_immutable_through_model_and_queryset(self):
        event = self.append(
            "asset_submitted",
            asset=self.asset,
            from_value="draft",
            to_value="submitted",
        )
        event.reason = "attempted mutation"
        with self.assertRaises(CoreAuditEventImmutableError):
            event.save()
        with self.assertRaises(CoreAuditEventImmutableError):
            CoreAuditEvent.objects.filter(pk=event.pk).update(reason="attempted mutation")
        with self.assertRaises(CoreAuditEventImmutableError):
            CoreAuditEvent._base_manager.filter(pk=event.pk).update(
                reason="attempted base-manager mutation"
            )
        event.reason = "attempted bulk mutation"
        with self.assertRaises(CoreAuditEventImmutableError):
            CoreAuditEvent.objects.bulk_update([event], ["reason"])
        with self.assertRaises(CoreAuditEventImmutableError):
            event.delete()
        with self.assertRaises(CoreAuditEventImmutableError):
            CoreAuditEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(CoreAuditEventImmutableError):
            CoreAuditEvent._base_manager.filter(pk=event.pk).delete()
        self.assertTrue(CoreAuditEvent.objects.filter(pk=event.pk).exists())

    def test_audit_append_participates_in_caller_transaction(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.append(
                "asset_submitted",
                asset=self.asset,
                from_value="draft",
                to_value="submitted",
            )
            raise RuntimeError("roll back domain operation")
        self.assertFalse(CoreAuditEvent.objects.exists())

    def test_audit_foreign_keys_protect_all_recorded_facts(self):
        asset_event = self.append(
            "asset_submitted",
            asset=self.asset,
            from_value="draft",
            to_value="submitted",
        )
        context_event = self.append(
            "context_activated",
            context=self.context,
            from_value="draft",
            to_value="active",
        )
        member_project = Project.objects.create(project_code="PROJECT_MEMBER_AUDIT_ONLY")
        member_event = append_core_audit_event(
            project=member_project,
            actor=self.actor,
            event_type="membership_added",
            subject_user=self.subject,
            to_value="viewer",
        )

        for target in [self.asset, self.context, self.actor, self.subject, member_project]:
            with self.subTest(target=target), self.assertRaises(ProtectedError):
                target.delete()
        self.assertEqual(
            {asset_event.pk, context_event.pk, member_event.pk},
            set(CoreAuditEvent.objects.values_list("pk", flat=True)),
        )

    def test_model_has_no_generic_target_or_payload_snapshot(self):
        field_names = {field.name for field in CoreAuditEvent._meta.fields}
        self.assertFalse({"related_type", "related_id", "payload", "metadata"} & field_names)
