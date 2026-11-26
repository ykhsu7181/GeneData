"""Pure lifecycle policy shared by future DataAsset write services."""

from dataclasses import dataclass
from types import MappingProxyType


class LifecyclePolicyError(ValueError):
    """Raised when an action is unknown or invalid for the current state."""


@dataclass(frozen=True)
class TransitionRule:
    source: str
    target: str
    allowed_roles: frozenset
    validation_level: str
    reason_required: bool = False


DATA_ASSET_TRANSITIONS = MappingProxyType(
    {
        "submit": TransitionRule(
            "draft", "submitted", frozenset({"owner", "manager", "contributor"}), "complete"
        ),
        "return": TransitionRule(
            "submitted", "draft", frozenset({"owner", "manager"}), "legal", True
        ),
        "approve": TransitionRule(
            "submitted", "approved", frozenset({"owner", "manager"}), "complete"
        ),
        "withdraw_approval": TransitionRule(
            "approved", "draft", frozenset({"owner", "manager"}), "legal", True
        ),
        "release": TransitionRule(
            "approved", "released", frozenset({"owner"}), "release"
        ),
        "archive": TransitionRule(
            "released", "archived", frozenset({"owner"}), "archive", True
        ),
    }
)
CONTEXT_TRANSITIONS = MappingProxyType(
    {
        "activate": TransitionRule(
            "draft", "active", frozenset({"owner", "manager"}), "complete"
        ),
        "archive": TransitionRule(
            "active", "archived", frozenset({"owner", "manager"}), "archive", True
        ),
    }
)


def resolve_data_asset_transition(action, current_status, role):
    return _resolve_transition(DATA_ASSET_TRANSITIONS, "DataAsset", action, current_status, role)


def resolve_context_transition(action, current_status, role):
    return _resolve_transition(CONTEXT_TRANSITIONS, "ContextEntity", action, current_status, role)


def _resolve_transition(rules, object_name, action, current_status, role):
    try:
        rule = rules[action]
    except KeyError as exc:
        raise LifecyclePolicyError(f"Unknown {object_name} lifecycle action: {action}") from exc
    if current_status != rule.source:
        raise LifecyclePolicyError(
            f"Cannot {action} {object_name} from {current_status}; expected {rule.source}"
        )
    if role not in rule.allowed_roles:
        raise LifecyclePolicyError(f"Role {role} cannot {action} {object_name}")
    return rule
