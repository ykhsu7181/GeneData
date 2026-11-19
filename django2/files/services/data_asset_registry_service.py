"""Single loading and validation boundary for DataAsset profile definitions."""

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.validators import validator_for


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "data_asset_registry" / "registry.json"
)
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DATA_TYPE_KEYS = frozenset({"sequence", "feature", "matrix", "table", "image"})
CONTEXT_TYPES = frozenset({"accession", "sample", "assembly", "annotation"})
PROFILE_FIELDS = frozenset(
    {
        "data_type_key",
        "profile_key",
        "schema_version",
        "deprecated",
        "replacement",
        "file_role_rules",
        "context_rules",
        "metadata_schema",
    }
)


class DataAssetRegistryError(ValueError):
    """Base error for invalid registry definitions or values."""


class DataAssetProfileNotFound(DataAssetRegistryError):
    """Raised when a requested type/profile pair is not registered."""


class DataAssetMetadataError(DataAssetRegistryError):
    """Raised when metadata does not match its registered schema."""


@dataclass(frozen=True)
class FileRoleRule:
    role_class: str
    minimum: int
    maximum: Optional[int]


@dataclass(frozen=True)
class ContextRule:
    minimum: int
    maximum: Optional[int]


@dataclass(frozen=True)
class DataAssetProfile:
    data_type_key: str
    profile_key: str
    schema_version: str
    schema_digest: str
    _metadata_schema_json: str
    file_role_rules: Mapping[str, FileRoleRule]
    context_rules: Mapping[str, ContextRule]
    deprecated: bool
    replacement: Optional[Tuple[str, str]]

    @property
    def metadata_schema(self):
        """Return an isolated copy so cached profile contracts cannot be mutated."""
        return json.loads(self._metadata_schema_json)


class DataAssetRegistry:
    def __init__(self, *, registry_version, profiles):
        self.registry_version = registry_version
        self._profiles = MappingProxyType(dict(profiles))

    @property
    def profile_keys(self):
        return tuple(sorted(self._profiles))

    def get_profile(self, data_type_key, profile_key):
        key = (data_type_key, profile_key)
        try:
            return self._profiles[key]
        except KeyError as exc:
            raise DataAssetProfileNotFound(
                f"Unknown DataAsset profile: {data_type_key}/{profile_key}"
            ) from exc

    def validate_metadata(self, data_type_key, profile_key, metadata):
        profile = self.get_profile(data_type_key, profile_key)
        if not isinstance(metadata, dict):
            raise DataAssetMetadataError("DataAsset metadata must be a JSON object")

        metadata_schema = profile.metadata_schema
        validator_class = validator_for(metadata_schema)
        validator = validator_class(metadata_schema)
        errors = sorted(validator.iter_errors(metadata), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.path) or "metadata"
            raise DataAssetMetadataError(f"Invalid {location}: {error.message}")
        return profile

    def validate_file_role(self, data_type_key, profile_key, file_role):
        profile = self.get_profile(data_type_key, profile_key)
        if file_role not in profile.file_role_rules:
            raise DataAssetRegistryError(
                f"Unknown file role for {data_type_key}/{profile_key}: {file_role}"
            )
        return profile

    def validate_asset_contract(
        self,
        data_type_key,
        profile_key,
        *,
        metadata,
        file_roles,
        context_counts,
    ):
        """Validate the complete logical contract for one formal asset creation."""
        profile = self.validate_metadata(data_type_key, profile_key, metadata)
        if isinstance(file_roles, (str, bytes)):
            raise DataAssetRegistryError("DataAsset file_roles must be an iterable of roles")
        if not isinstance(context_counts, Mapping):
            raise DataAssetRegistryError("DataAsset context_counts must be a mapping")
        try:
            file_roles = tuple(file_roles)
        except TypeError as exc:
            raise DataAssetRegistryError(
                "DataAsset file_roles must be an iterable of roles"
            ) from exc
        if any(not isinstance(role, str) for role in file_roles):
            raise DataAssetRegistryError("DataAsset file roles must be strings")

        _validate_actual_counts(
            Counter(file_roles),
            profile.file_role_rules,
            item_name="File role",
            profile=profile,
        )
        _validate_context_counts(context_counts, profile)
        return profile


def load_data_asset_registry(path=None):
    """Load a validated registry; the packaged registry is cached read-only."""
    if path is None:
        return _load_default_registry()
    return _load_registry(Path(path))


@lru_cache(maxsize=1)
def _load_default_registry():
    return _load_registry(DEFAULT_REGISTRY_PATH)


def _load_registry(path):
    try:
        raw_registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataAssetRegistryError(f"Cannot read DataAsset registry: {path}") from exc

    if not isinstance(raw_registry, dict):
        raise DataAssetRegistryError("DataAsset registry must be a JSON object")
    _reject_unknown_fields(raw_registry, {"registry_version", "profiles"}, "registry")
    registry_version = _required_string(raw_registry, "registry_version", context="registry")
    if registry_version != "2":
        raise DataAssetRegistryError(
            f"Unsupported DataAsset registry version: {registry_version}"
        )
    raw_profiles = raw_registry.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise DataAssetRegistryError("DataAsset registry profiles must be a non-empty list")

    profiles = {}
    for index, raw_profile in enumerate(raw_profiles):
        profile = _parse_profile(raw_profile, index=index)
        key = (profile.data_type_key, profile.profile_key)
        if key in profiles:
            raise DataAssetRegistryError(
                f"Duplicate DataAsset profile: {profile.data_type_key}/{profile.profile_key}"
            )
        profiles[key] = profile

    for profile in profiles.values():
        if profile.replacement and profile.replacement not in profiles:
            replacement = "/".join(profile.replacement)
            raise DataAssetRegistryError(f"Unknown replacement profile: {replacement}")

    return DataAssetRegistry(registry_version=registry_version, profiles=profiles)


def _parse_profile(raw_profile, *, index):
    context = f"profiles[{index}]"
    if not isinstance(raw_profile, dict):
        raise DataAssetRegistryError(f"{context} must be a JSON object")
    _reject_unknown_fields(raw_profile, PROFILE_FIELDS, context)

    data_type_key = _required_data_type_key(
        raw_profile,
        "data_type_key",
        context=context,
    )
    profile_key = _required_key(raw_profile, "profile_key", context=context)
    schema_version = _required_string(raw_profile, "schema_version", context=context)
    metadata_schema = raw_profile.get("metadata_schema")
    if not isinstance(metadata_schema, dict):
        raise DataAssetRegistryError(f"{context}.metadata_schema must be a JSON object")
    try:
        validator_for(metadata_schema).check_schema(metadata_schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise DataAssetRegistryError(f"Invalid JSON Schema in {context}") from exc

    deprecated = raw_profile.get("deprecated", False)
    if not isinstance(deprecated, bool):
        raise DataAssetRegistryError(f"{context}.deprecated must be boolean")
    file_role_rules = _parse_file_role_rules(
        raw_profile.get("file_role_rules"),
        context=context,
        require_core=not deprecated,
    )
    context_rules = _parse_context_rules(raw_profile.get("context_rules"), context=context)

    replacement = _parse_replacement(raw_profile.get("replacement"), context=context)
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")

    contract = {
        "data_type_key": data_type_key,
        "profile_key": profile_key,
        "schema_version": schema_version,
        "metadata_schema": metadata_schema,
        "file_role_rules": {
            role: {
                "class": rule.role_class,
                "min": rule.minimum,
                "max": rule.maximum,
            }
            for role, rule in file_role_rules.items()
        },
        "context_rules": {
            name: {"min": rule.minimum, "max": rule.maximum}
            for name, rule in context_rules.items()
        },
        "deprecated": deprecated,
        "replacement": (
            {"data_type_key": replacement[0], "profile_key": replacement[1]}
            if replacement
            else None
        ),
    }
    return DataAssetProfile(
        data_type_key=data_type_key,
        profile_key=profile_key,
        schema_version=schema_version,
        schema_digest=_profile_digest(contract),
        _metadata_schema_json=_canonical_json(metadata_schema),
        file_role_rules=MappingProxyType(file_role_rules),
        context_rules=MappingProxyType(context_rules),
        deprecated=deprecated,
        replacement=replacement,
    )


def _parse_file_role_rules(value, *, context, require_core):
    rule_context = f"{context}.file_role_rules"
    if not isinstance(value, dict) or not value:
        raise DataAssetRegistryError(f"{rule_context} must be a non-empty object")
    rules = {}
    for role, raw_rule in value.items():
        if not isinstance(role, str) or not KEY_PATTERN.fullmatch(role):
            raise DataAssetRegistryError(f"Invalid file role in {context}: {role!r}")
        if not isinstance(raw_rule, dict):
            raise DataAssetRegistryError(f"{rule_context}.{role} must be an object")
        _reject_unknown_fields(raw_rule, {"class", "min", "max"}, f"{rule_context}.{role}")
        role_class = raw_rule.get("class")
        if role_class not in {"core", "auxiliary"}:
            raise DataAssetRegistryError(
                f"{rule_context}.{role}.class must be core or auxiliary"
            )
        minimum, maximum = _parse_cardinality(raw_rule, context=f"{rule_context}.{role}")
        rules[role] = FileRoleRule(role_class, minimum, maximum)
    if require_core and not any(
        rule.role_class == "core" and rule.minimum >= 1 for rule in rules.values()
    ):
        raise DataAssetRegistryError(
            f"{rule_context} must require at least one core file role"
        )
    return rules


def _parse_context_rules(value, *, context):
    rule_context = f"{context}.context_rules"
    if not isinstance(value, dict):
        raise DataAssetRegistryError(f"{rule_context} must be an object")
    rules = {}
    for name, raw_rule in value.items():
        if name not in CONTEXT_TYPES:
            raise DataAssetRegistryError(f"Unknown context type in {context}: {name!r}")
        if not isinstance(raw_rule, dict):
            raise DataAssetRegistryError(f"{rule_context}.{name} must be an object")
        _reject_unknown_fields(raw_rule, {"min", "max"}, f"{rule_context}.{name}")
        minimum, maximum = _parse_cardinality(raw_rule, context=f"{rule_context}.{name}")
        rules[name] = ContextRule(minimum, maximum)
    return rules


def _parse_cardinality(raw_rule, *, context):
    if "min" not in raw_rule or "max" not in raw_rule:
        raise DataAssetRegistryError(f"{context} must declare min and max")
    minimum = raw_rule["min"]
    maximum = raw_rule["max"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
        raise DataAssetRegistryError(f"{context}.min must be a non-negative integer")
    if maximum is not None and (
        isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0
    ):
        raise DataAssetRegistryError(
            f"{context}.max must be null or a non-negative integer"
        )
    if maximum is not None and maximum < minimum:
        raise DataAssetRegistryError(f"{context}.max must be greater than or equal to min")
    return minimum, maximum


def _validate_actual_counts(actual_counts, rules, *, item_name, profile):
    profile_name = f"{profile.data_type_key}/{profile.profile_key}"
    for name in actual_counts:
        if name not in rules:
            raise DataAssetRegistryError(
                f"{item_name} {name} is not allowed for {profile_name}"
            )
    for name, rule in rules.items():
        count = actual_counts.get(name, 0)
        if count < rule.minimum:
            raise DataAssetRegistryError(
                f"{item_name} {name} requires at least {rule.minimum} for {profile_name}; got {count}"
            )
        if rule.maximum is not None and count > rule.maximum:
            raise DataAssetRegistryError(
                f"{item_name} {name} allows at most {rule.maximum} for {profile_name}; got {count}"
            )


def _validate_context_counts(context_counts, profile):
    normalized = {}
    for name, count in context_counts.items():
        if name not in CONTEXT_TYPES:
            raise DataAssetRegistryError(f"Unknown DataAsset context type: {name}")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DataAssetRegistryError(
                f"DataAsset context count for {name} must be a non-negative integer"
            )
        normalized[name] = count
    _validate_actual_counts(
        normalized,
        profile.context_rules,
        item_name="Context",
        profile=profile,
    )


def _required_string(mapping, field, *, context):
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DataAssetRegistryError(f"{context}.{field} must be a non-empty string")
    return value.strip()


def _required_key(mapping, field, *, context):
    value = _required_string(mapping, field, context=context)
    if not KEY_PATTERN.fullmatch(value):
        raise DataAssetRegistryError(f"Invalid {context}.{field}: {value!r}")
    return value


def _required_data_type_key(mapping, field, *, context):
    value = _required_key(mapping, field, context=context)
    if value not in DATA_TYPE_KEYS:
        allowed = ", ".join(sorted(DATA_TYPE_KEYS))
        raise DataAssetRegistryError(
            f"Unsupported {context}.{field}: {value!r}; allowed: {allowed}"
        )
    return value


def _parse_replacement(value, *, context):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DataAssetRegistryError(f"{context}.replacement must be null or an object")
    _reject_unknown_fields(
        value,
        {"data_type_key", "profile_key"},
        f"{context}.replacement",
    )
    return (
        _required_data_type_key(
            value,
            "data_type_key",
            context=f"{context}.replacement",
        ),
        _required_key(value, "profile_key", context=f"{context}.replacement"),
    )


def _reject_unknown_fields(mapping, allowed, context):
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise DataAssetRegistryError(
            f"Unknown field(s) in {context}: {', '.join(unknown)}"
        )


def _profile_digest(contract):
    canonical = _canonical_json(contract).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
