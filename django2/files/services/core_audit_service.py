import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from files.models import CORE_AUDIT_EVENT_TYPES, CoreAuditEvent


class CoreAuditValidationError(ValueError):
    pass


CORE_AUDIT_DIGEST_ALGORITHM = "canonical-json-sha256-v1"


@dataclass(frozen=True)
class AuditEventRule:
    target_kind: str
    from_values: frozenset
    to_values: frozenset
    exact_transition: Optional[tuple] = None
    content_mode: str = "none"
    reason_required: bool = False
    privileged_role_reason: bool = False


_ROLES = frozenset({"owner", "manager", "contributor", "viewer"})
_PRIVILEGED_ROLES = frozenset({"owner", "manager"})

EVENT_RULES = {
    "membership_added": AuditEventRule(
        "subject_user", frozenset({""}), _ROLES, privileged_role_reason=True
    ),
    "membership_role_changed": AuditEventRule(
        "subject_user", _ROLES, _ROLES, privileged_role_reason=True
    ),
    "membership_removed": AuditEventRule(
        "subject_user", _ROLES, frozenset({""}), privileged_role_reason=True
    ),
    "context_created": AuditEventRule(
        "context",
        frozenset({""}),
        frozenset({"draft"}),
        exact_transition=("", "draft"),
        content_mode="created",
    ),
    "context_updated": AuditEventRule(
        "context",
        frozenset({""}),
        frozenset({""}),
        exact_transition=("", ""),
        content_mode="updated",
    ),
    "context_activated": AuditEventRule(
        "context", frozenset({"draft"}), frozenset({"active"}), exact_transition=("draft", "active")
    ),
    "context_archived": AuditEventRule(
        "context",
        frozenset({"active"}),
        frozenset({"archived"}),
        exact_transition=("active", "archived"),
        reason_required=True,
    ),
    "asset_created": AuditEventRule(
        "asset",
        frozenset({""}),
        frozenset({"draft"}),
        exact_transition=("", "draft"),
        content_mode="created",
    ),
    "asset_updated": AuditEventRule(
        "asset",
        frozenset({""}),
        frozenset({""}),
        exact_transition=("", ""),
        content_mode="updated",
    ),
    "asset_submitted": AuditEventRule(
        "asset", frozenset({"draft"}), frozenset({"submitted"}), exact_transition=("draft", "submitted")
    ),
    "asset_returned": AuditEventRule(
        "asset",
        frozenset({"submitted"}),
        frozenset({"draft"}),
        exact_transition=("submitted", "draft"),
        reason_required=True,
    ),
    "asset_approved": AuditEventRule(
        "asset", frozenset({"submitted"}), frozenset({"approved"}), exact_transition=("submitted", "approved")
    ),
    "asset_approval_withdrawn": AuditEventRule(
        "asset",
        frozenset({"approved"}),
        frozenset({"draft"}),
        exact_transition=("approved", "draft"),
        reason_required=True,
    ),
    "asset_released": AuditEventRule(
        "asset", frozenset({"approved"}), frozenset({"released"}), exact_transition=("approved", "released")
    ),
    "asset_archived": AuditEventRule(
        "asset",
        frozenset({"released"}),
        frozenset({"archived"}),
        exact_transition=("released", "archived"),
        reason_required=True,
    ),
}


def append_core_audit_event(
    *,
    project,
    actor,
    event_type: str,
    asset=None,
    context=None,
    subject_user=None,
    from_value: str = "",
    to_value: str = "",
    before_content=None,
    after_content=None,
    reason: str = "",
) -> CoreAuditEvent:
    rule = EVENT_RULES.get(event_type)
    if rule is None:
        raise CoreAuditValidationError("Unknown core audit event type.")
    if set(EVENT_RULES) != set(CORE_AUDIT_EVENT_TYPES):
        raise CoreAuditValidationError("Core audit event rules are incomplete.")
    if project is None or project.pk is None:
        raise CoreAuditValidationError("A persisted project is required.")
    if actor is None or actor.pk is None or not actor.is_active:
        raise CoreAuditValidationError("An active persisted actor is required.")

    targets = {"asset": asset, "context": context, "subject_user": subject_user}
    present_targets = [key for key, value in targets.items() if value is not None]
    if present_targets != [rule.target_kind]:
        raise CoreAuditValidationError("The audit event target does not match its event type.")
    target = targets[rule.target_kind]
    if target.pk is None:
        raise CoreAuditValidationError("A persisted audit target is required.")
    if rule.target_kind in {"asset", "context"} and target.project_id != project.pk:
        raise CoreAuditValidationError("The audit target must belong to the event project.")

    from_value = str(from_value or "")
    to_value = str(to_value or "")
    if from_value not in rule.from_values or to_value not in rule.to_values:
        raise CoreAuditValidationError("Invalid values for the audit event transition.")
    if rule.exact_transition is not None and (from_value, to_value) != rule.exact_transition:
        raise CoreAuditValidationError("Invalid transition for the audit event type.")
    if event_type == "membership_role_changed" and from_value == to_value:
        raise CoreAuditValidationError("A role change must change the role.")

    before_digest, after_digest = _compute_event_digests(
        rule.content_mode,
        before_content=before_content,
        after_content=after_content,
    )

    reason = str(reason or "").strip()
    privileged_change = (
        rule.privileged_role_reason
        and bool(_PRIVILEGED_ROLES & {from_value, to_value})
    )
    if (rule.reason_required or privileged_change) and not reason:
        raise CoreAuditValidationError("A reason is required for this audit event.")

    with transaction.atomic():
        return CoreAuditEvent.objects.create(
            project=project,
            actor=actor,
            event_type=event_type,
            asset=asset,
            context=context,
            subject_user=subject_user,
            from_value=from_value,
            to_value=to_value,
            before_digest=before_digest,
            after_digest=after_digest,
            reason=reason,
        )


def compute_core_audit_digest(content: Mapping) -> str:
    """Return the frozen canonical-json-sha256-v1 digest for audit content."""
    if not isinstance(content, Mapping):
        raise CoreAuditValidationError("Audit content must be a mapping.")
    normalized = _normalize_canonical_value(content)
    canonical = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _normalize_canonical_value(value):
    if isinstance(value, Mapping):
        normalized = {}
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise CoreAuditValidationError(
                    "Audit content object keys must be non-empty strings."
                )
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise CoreAuditValidationError(
                    "Audit content keys collide after Unicode normalization."
                )
            normalized[normalized_key] = _normalize_canonical_value(child)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_canonical_value(child) for child in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CoreAuditValidationError(
                "Audit content cannot contain non-finite numbers."
            )
        return value
    raise CoreAuditValidationError(
        f"Unsupported audit content value type: {type(value).__name__}."
    )


def _compute_event_digests(mode: str, *, before_content, after_content):
    if mode == "none":
        if before_content is not None or after_content is not None:
            raise CoreAuditValidationError("This event type does not accept content snapshots.")
        return "", ""
    if mode == "created":
        if before_content is not None or after_content is None:
            raise CoreAuditValidationError(
                "Created events require only the resulting content."
            )
        return "", compute_core_audit_digest(after_content)
    if mode == "updated":
        if before_content is None or after_content is None:
            raise CoreAuditValidationError(
                "Updated events require previous and resulting content."
            )
        before_digest = compute_core_audit_digest(before_content)
        after_digest = compute_core_audit_digest(after_content)
        if before_digest == after_digest:
            raise CoreAuditValidationError(
                "Updated events require a meaningful content change."
            )
        return before_digest, after_digest
    raise CoreAuditValidationError("Unknown audit content policy.")
