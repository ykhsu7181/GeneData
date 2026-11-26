"""Single loading and validation boundary for versioned DataAsset registries."""

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


DEFAULT_REGISTRY_DIRECTORY = Path(__file__).resolve().parent.parent / "data_asset_registry"
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PROFILE_REFERENCE_PATTERN = re.compile(
    r"^(?P<type>[a-z][a-z0-9_]*)/(?P<profile>[a-z][a-z0-9_]*)$"
)
ASSET_PROFILE_FIELDS = frozenset(
    {
        "data_type_key", "profile_key", "profile_family", "schema_version",
        "deprecated", "replacement", "file_role_rules", "context_rules",
        "context_link_rules", "outgoing_relations", "public_metadata_fields",
        "metadata_schema",
    }
)
CONTEXT_PROFILE_FIELDS = frozenset(
    {
        "context_type_key", "profile_key", "profile_family", "schema_version",
        "deprecated", "replacement", "outgoing_relations",
        "public_metadata_fields", "metadata_schema",
    }
)
RELATION_FIELDS = frozenset(
    {
        "key", "version", "deprecated", "replacement", "source_kind",
        "target_kind", "directed", "self_link", "acyclic",
        "cross_project_policy", "same_profile_family", "outgoing_max",
        "incoming_max",
    }
)
NAMESPACE_FIELDS = frozenset(
    {
        "key", "version", "name", "deprecated", "replacement", "pattern",
        "normalization", "resolver_url_template", "allowed_target_kinds",
        "allowed_context_types",
    }
)
SAFE_NORMALIZATIONS = frozenset(
    {"strip", "uppercase", "lowercase", "strip_uppercase", "strip_lowercase"}
)
TARGET_KINDS = frozenset({"project", "data_asset", "context"})
RELATION_KINDS = frozenset({"data_asset", "context"})
CROSS_PROJECT_POLICIES = frozenset({"same_project", "public_released_only"})


class DataAssetRegistryError(ValueError):
    """Base error for invalid registry definitions or values."""


class DataAssetProfileNotFound(DataAssetRegistryError):
    """Raised when a requested asset profile cannot be resolved."""


class ContextProfileNotFound(DataAssetRegistryError):
    """Raised when a requested context profile cannot be resolved."""


class RegistryEntryNotFound(DataAssetRegistryError):
    """Raised when a relation or namespace entry cannot be resolved."""


class DataAssetMetadataError(DataAssetRegistryError):
    """Raised when metadata does not match its registered schema."""


@dataclass(frozen=True)
class FileRoleRule:
    role_class: str
    minimum: int
    maximum: Optional[int]


@dataclass(frozen=True)
class CardinalityRule:
    minimum: int
    maximum: Optional[int]
    allowed_target_profiles: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DataAssetProfile:
    data_type_key: str
    profile_key: str
    profile_family: str
    schema_version: str
    schema_digest: str
    _metadata_schema_json: str
    file_role_rules: Mapping[str, FileRoleRule]
    context_rules: Mapping[str, CardinalityRule]
    context_link_rules: Mapping[str, CardinalityRule]
    outgoing_relations: Mapping[str, CardinalityRule]
    public_metadata_fields: Tuple[str, ...]
    deprecated: bool
    replacement: Optional[Tuple[str, str]]

    @property
    def metadata_schema(self):
        return json.loads(self._metadata_schema_json)


@dataclass(frozen=True)
class ContextProfile:
    context_type_key: str
    profile_key: str
    profile_family: str
    schema_version: str
    schema_digest: str
    _metadata_schema_json: str
    outgoing_relations: Mapping[str, CardinalityRule]
    public_metadata_fields: Tuple[str, ...]
    deprecated: bool
    replacement: Optional[Tuple[str, str]]

    @property
    def metadata_schema(self):
        return json.loads(self._metadata_schema_json)


@dataclass(frozen=True)
class RelationRule:
    key: str
    version: str
    digest: str
    source_kind: str
    target_kind: str
    directed: bool
    self_link: str
    acyclic: bool
    cross_project_policy: str
    same_profile_family: bool
    outgoing_max: Optional[int]
    incoming_max: Optional[int]
    deprecated: bool
    replacement: Optional[str]


@dataclass(frozen=True)
class NamespaceRule:
    key: str
    version: str
    digest: str
    name: str
    pattern: str
    normalization: str
    resolver_url_template: str
    allowed_target_kinds: Tuple[str, ...]
    allowed_context_types: Tuple[str, ...]
    deprecated: bool
    replacement: Optional[str]

    def normalize(self, value):
        if not isinstance(value, str) or not value.strip():
            raise DataAssetRegistryError(
                f"External identifier for {self.key} must be a non-empty string"
            )
        normalized = _normalize_identifier(value, self.normalization)
        if not re.fullmatch(self.pattern, normalized):
            raise DataAssetRegistryError(
                f"External identifier does not match namespace {self.key}"
            )
        return normalized


class DataAssetRegistry:
    def __init__(
        self, *, registry_version, asset_profiles, asset_current_versions,
        context_profiles, context_current_versions, relation_rules,
        relation_current_versions, namespace_rules, namespace_current_versions,
    ):
        self.registry_version = registry_version
        self._asset_profiles = MappingProxyType(dict(asset_profiles))
        self._asset_current_versions = MappingProxyType(dict(asset_current_versions))
        self._context_profiles = MappingProxyType(dict(context_profiles))
        self._context_current_versions = MappingProxyType(dict(context_current_versions))
        self._relation_rules = MappingProxyType(dict(relation_rules))
        self._relation_current_versions = MappingProxyType(dict(relation_current_versions))
        self._namespace_rules = MappingProxyType(dict(namespace_rules))
        self._namespace_current_versions = MappingProxyType(dict(namespace_current_versions))

    @property
    def profile_keys(self):
        """Compatibility name for current asset profile keys."""
        return tuple(sorted(self._asset_current_versions))

    @property
    def asset_profile_version_keys(self):
        return tuple(sorted(self._asset_profiles))

    @property
    def context_profile_keys(self):
        return tuple(sorted(self._context_current_versions))

    @property
    def relation_keys(self):
        return tuple(sorted(self._relation_current_versions))

    @property
    def namespace_keys(self):
        return tuple(sorted(self._namespace_current_versions))

    def get_profile(self, data_type_key, profile_key):
        return self.resolve_current_asset_profile(data_type_key, profile_key)

    def resolve_current_asset_profile(self, data_type_key, profile_key):
        key = (data_type_key, profile_key)
        try:
            version = self._asset_current_versions[key]
            return self._asset_profiles[(data_type_key, profile_key, version)]
        except KeyError as exc:
            raise DataAssetProfileNotFound(
                f"Unknown current DataAsset profile: {data_type_key}/{profile_key}"
            ) from exc

    def resolve_exact_asset_profile(
        self, data_type_key, profile_key, schema_version, schema_digest
    ):
        key = (data_type_key, profile_key, schema_version)
        try:
            profile = self._asset_profiles[key]
        except KeyError as exc:
            raise DataAssetProfileNotFound(
                f"Unknown DataAsset profile version: {data_type_key}/{profile_key}@{schema_version}"
            ) from exc
        _require_digest(profile.schema_digest, schema_digest, "DataAsset profile", key)
        return profile

    def resolve_current_context_profile(self, context_type_key, profile_key):
        key = (context_type_key, profile_key)
        try:
            version = self._context_current_versions[key]
            return self._context_profiles[(context_type_key, profile_key, version)]
        except KeyError as exc:
            raise ContextProfileNotFound(
                f"Unknown current Context profile: {context_type_key}/{profile_key}"
            ) from exc

    def resolve_exact_context_profile(
        self, context_type_key, profile_key, schema_version, schema_digest
    ):
        key = (context_type_key, profile_key, schema_version)
        try:
            profile = self._context_profiles[key]
        except KeyError as exc:
            raise ContextProfileNotFound(
                f"Unknown Context profile version: {context_type_key}/{profile_key}@{schema_version}"
            ) from exc
        _require_digest(profile.schema_digest, schema_digest, "Context profile", key)
        return profile

    def resolve_current_relation(self, key):
        try:
            version = self._relation_current_versions[key]
            return self._relation_rules[(key, version)]
        except KeyError as exc:
            raise RegistryEntryNotFound(f"Unknown current relation rule: {key}") from exc

    def resolve_exact_relation(self, key, version, digest):
        try:
            rule = self._relation_rules[(key, version)]
        except KeyError as exc:
            raise RegistryEntryNotFound(f"Unknown relation rule version: {key}@{version}") from exc
        _require_digest(rule.digest, digest, "Relation rule", (key, version))
        return rule

    def resolve_current_namespace(self, key):
        try:
            version = self._namespace_current_versions[key]
            return self._namespace_rules[(key, version)]
        except KeyError as exc:
            raise RegistryEntryNotFound(f"Unknown current namespace: {key}") from exc

    def resolve_exact_namespace(self, key, version, digest):
        try:
            rule = self._namespace_rules[(key, version)]
        except KeyError as exc:
            raise RegistryEntryNotFound(f"Unknown namespace version: {key}@{version}") from exc
        _require_digest(rule.digest, digest, "Namespace", (key, version))
        return rule

    def validate_metadata(self, data_type_key, profile_key, metadata):
        profile = self.get_profile(data_type_key, profile_key)
        _validate_metadata(profile.metadata_schema, metadata, "DataAsset")
        return profile

    def validate_file_role(self, data_type_key, profile_key, file_role):
        profile = self.get_profile(data_type_key, profile_key)
        if file_role not in profile.file_role_rules:
            raise DataAssetRegistryError(
                f"Unknown file role for {data_type_key}/{profile_key}: {file_role}"
            )
        return profile

    def validate_asset_contract(
        self, data_type_key, profile_key, *, metadata, file_roles, context_counts,
    ):
        """Validate the current legacy creation contract until Gate D switches it."""
        profile = self.validate_metadata(data_type_key, profile_key, metadata)
        if isinstance(file_roles, (str, bytes)):
            raise DataAssetRegistryError("DataAsset file_roles must be an iterable of roles")
        if not isinstance(context_counts, Mapping):
            raise DataAssetRegistryError("DataAsset context_counts must be a mapping")
        try:
            file_roles = tuple(file_roles)
        except TypeError as exc:
            raise DataAssetRegistryError("DataAsset file_roles must be an iterable of roles") from exc
        if any(not isinstance(role, str) for role in file_roles):
            raise DataAssetRegistryError("DataAsset file roles must be strings")
        profile_name = f"{profile.data_type_key}/{profile.profile_key}"
        _validate_actual_counts(
            Counter(file_roles), profile.file_role_rules,
            item_name="File role", profile_name=profile_name,
        )
        _validate_actual_counts(
            _validate_count_mapping(context_counts, "DataAsset context"),
            profile.context_rules, item_name="Context", profile_name=profile_name,
        )
        return profile


def load_data_asset_registry(path=None):
    """Load one complete registry package; the packaged registry is cached read-only."""
    if path is None:
        return _load_default_registry()
    return _load_registry_package(Path(path))


@lru_cache(maxsize=1)
def _load_default_registry():
    return _load_registry_package(DEFAULT_REGISTRY_DIRECTORY)


def _load_registry_package(directory):
    if not directory.is_dir():
        raise DataAssetRegistryError(f"DataAsset registry path must be a directory: {directory}")
    asset_data = _read_json(directory / "asset_profiles.json")
    context_data = _read_json(directory / "context_profiles.json")
    relation_data = _read_json(directory / "relation_registry.json")
    namespace_data = _read_json(directory / "namespace_registry.json")

    asset_profiles, asset_current = _load_versioned_entries(
        asset_data, file_name="asset_profiles.json", parser=_parse_asset_profile,
        identity=lambda item: (item.data_type_key, item.profile_key, item.schema_version),
        current_identity=_parse_profile_reference,
        current_lookup=lambda key, version: (key[0], key[1], version),
    )
    context_profiles, context_current = _load_versioned_entries(
        context_data, file_name="context_profiles.json", parser=_parse_context_profile,
        identity=lambda item: (item.context_type_key, item.profile_key, item.schema_version),
        current_identity=_parse_profile_reference,
        current_lookup=lambda key, version: (key[0], key[1], version),
    )
    relation_rules, relation_current = _load_versioned_entries(
        relation_data, file_name="relation_registry.json", parser=_parse_relation_rule,
        identity=lambda item: (item.key, item.version),
        current_identity=lambda value, context: (_required_key_value(value, context),),
        current_lookup=lambda key, version: (key[0], version),
    )
    namespace_rules, namespace_current = _load_versioned_entries(
        namespace_data, file_name="namespace_registry.json", parser=_parse_namespace_rule,
        identity=lambda item: (item.key, item.version),
        current_identity=lambda value, context: (_required_key_value(value, context),),
        current_lookup=lambda key, version: (key[0], version),
    )
    _validate_replacements(asset_profiles, asset_current, "DataAsset profile")
    _validate_replacements(context_profiles, context_current, "Context profile")
    _validate_key_replacements(relation_rules, relation_current, "Relation rule")
    _validate_key_replacements(namespace_rules, namespace_current, "Namespace")
    _validate_profile_relation_references(asset_profiles, context_profiles, relation_current)
    versions = {
        asset_data["registry_version"], context_data["registry_version"],
        relation_data["registry_version"], namespace_data["registry_version"],
    }
    if len(versions) != 1:
        raise DataAssetRegistryError("Registry package versions must match")
    return DataAssetRegistry(
        registry_version=versions.pop(), asset_profiles=asset_profiles,
        asset_current_versions=asset_current, context_profiles=context_profiles,
        context_current_versions=context_current, relation_rules=relation_rules,
        relation_current_versions=relation_current, namespace_rules=namespace_rules,
        namespace_current_versions=namespace_current,
    )


def _read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataAssetRegistryError(f"Cannot read registry file: {path}") from exc
    if not isinstance(value, dict):
        raise DataAssetRegistryError(f"Registry file must contain an object: {path}")
    _reject_unknown_fields(value, {"registry_version", "current_versions", "entries"}, path.name)
    version = _required_string(value, "registry_version", context=path.name)
    if version != "3":
        raise DataAssetRegistryError(
            f"Unsupported registry package version in {path.name}: {version}"
        )
    if not isinstance(value.get("current_versions"), dict):
        raise DataAssetRegistryError(f"{path.name}.current_versions must be an object")
    if not isinstance(value.get("entries"), list) or not value["entries"]:
        raise DataAssetRegistryError(f"{path.name}.entries must be a non-empty list")
    return value


def _load_versioned_entries(
    data, *, file_name, parser, identity, current_identity, current_lookup,
):
    entries = {}
    for index, raw_entry in enumerate(data["entries"]):
        entry = parser(raw_entry, context=f"{file_name}.entries[{index}]")
        entry_identity = identity(entry)
        if entry_identity in entries:
            raise DataAssetRegistryError(
                f"Duplicate registry entry in {file_name}: {entry_identity}"
            )
        entries[entry_identity] = entry
    current_versions = {}
    for raw_key, raw_version in data["current_versions"].items():
        key = current_identity(raw_key, f"{file_name}.current_versions key")
        version = _required_string_value(
            raw_version, f"{file_name}.current_versions[{raw_key!r}]"
        )
        lookup = current_lookup(key, version)
        if lookup not in entries:
            raise DataAssetRegistryError(
                f"Current registry entry does not exist in {file_name}: {raw_key}@{version}"
            )
        entry = entries[lookup]
        if entry.deprecated:
            raise DataAssetRegistryError(
                f"Deprecated registry entry cannot be current in {file_name}: {raw_key}@{version}"
            )
        current_versions[key if len(key) > 1 else key[0]] = version
    return entries, current_versions


def _parse_asset_profile(raw_profile, *, context):
    if not isinstance(raw_profile, dict):
        raise DataAssetRegistryError(f"{context} must be an object")
    _reject_unknown_fields(raw_profile, ASSET_PROFILE_FIELDS, context)
    data_type_key = _required_key(raw_profile, "data_type_key", context=context)
    profile_key = _required_key(raw_profile, "profile_key", context=context)
    schema_version = _required_string(raw_profile, "schema_version", context=context)
    metadata_schema = _parse_metadata_schema(raw_profile, context)
    deprecated = _optional_bool(raw_profile, "deprecated", context, False)
    replacement = _parse_profile_replacement(raw_profile.get("replacement"), context)
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")
    file_rules = _parse_file_role_rules(
        raw_profile.get("file_role_rules"), context=context, require_core=not deprecated
    )
    context_rules = _parse_cardinality_rules(
        raw_profile.get("context_rules", {}), context=f"{context}.context_rules",
        allow_targets=False,
    )
    context_link_rules = _parse_cardinality_rules(
        raw_profile.get("context_link_rules", {}),
        context=f"{context}.context_link_rules", allow_targets=True,
    )
    outgoing_relations = _parse_cardinality_rules(
        raw_profile.get("outgoing_relations", {}),
        context=f"{context}.outgoing_relations", allow_targets=True,
    )
    public_fields = _parse_public_fields(
        raw_profile.get("public_metadata_fields", []), metadata_schema, context
    )
    profile_family = raw_profile.get("profile_family", profile_key)
    if not isinstance(profile_family, str) or not KEY_PATTERN.fullmatch(profile_family):
        raise DataAssetRegistryError(f"Invalid {context}.profile_family")
    legacy_contract = not any(
        field in raw_profile
        for field in (
            "profile_family", "context_link_rules", "outgoing_relations",
            "public_metadata_fields",
        )
    )
    contract = {
        "data_type_key": data_type_key, "profile_key": profile_key,
        "schema_version": schema_version, "metadata_schema": metadata_schema,
        "file_role_rules": _serialize_file_rules(file_rules),
        "context_rules": _serialize_cardinality_rules(context_rules, False),
        "deprecated": deprecated,
        "replacement": _serialize_profile_replacement(replacement),
    }
    if not legacy_contract:
        contract.update(
            {
                "profile_family": profile_family,
                "context_link_rules": _serialize_cardinality_rules(context_link_rules, True),
                "outgoing_relations": _serialize_cardinality_rules(outgoing_relations, True),
                "public_metadata_fields": list(public_fields),
            }
        )
    return DataAssetProfile(
        data_type_key=data_type_key, profile_key=profile_key,
        profile_family=profile_family, schema_version=schema_version,
        schema_digest=_digest(contract),
        _metadata_schema_json=_canonical_json(metadata_schema),
        file_role_rules=MappingProxyType(file_rules),
        context_rules=MappingProxyType(context_rules),
        context_link_rules=MappingProxyType(context_link_rules),
        outgoing_relations=MappingProxyType(outgoing_relations),
        public_metadata_fields=public_fields, deprecated=deprecated,
        replacement=replacement,
    )


def _parse_context_profile(raw_profile, *, context):
    if not isinstance(raw_profile, dict):
        raise DataAssetRegistryError(f"{context} must be an object")
    _reject_unknown_fields(raw_profile, CONTEXT_PROFILE_FIELDS, context)
    context_type_key = _required_key(raw_profile, "context_type_key", context=context)
    profile_key = _required_key(raw_profile, "profile_key", context=context)
    profile_family = _required_key(raw_profile, "profile_family", context=context)
    schema_version = _required_string(raw_profile, "schema_version", context=context)
    metadata_schema = _parse_metadata_schema(raw_profile, context)
    deprecated = _optional_bool(raw_profile, "deprecated", context, False)
    replacement = _parse_profile_replacement(raw_profile.get("replacement"), context)
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")
    outgoing_relations = _parse_cardinality_rules(
        raw_profile.get("outgoing_relations", {}),
        context=f"{context}.outgoing_relations", allow_targets=True,
    )
    public_fields = _parse_public_fields(
        raw_profile.get("public_metadata_fields", []), metadata_schema, context
    )
    contract = {
        "context_type_key": context_type_key, "profile_key": profile_key,
        "profile_family": profile_family, "schema_version": schema_version,
        "metadata_schema": metadata_schema,
        "outgoing_relations": _serialize_cardinality_rules(outgoing_relations, True),
        "public_metadata_fields": list(public_fields), "deprecated": deprecated,
        "replacement": _serialize_profile_replacement(replacement),
    }
    return ContextProfile(
        context_type_key=context_type_key, profile_key=profile_key,
        profile_family=profile_family, schema_version=schema_version,
        schema_digest=_digest(contract),
        _metadata_schema_json=_canonical_json(metadata_schema),
        outgoing_relations=MappingProxyType(outgoing_relations),
        public_metadata_fields=public_fields, deprecated=deprecated,
        replacement=replacement,
    )


def _parse_relation_rule(raw_rule, *, context):
    if not isinstance(raw_rule, dict):
        raise DataAssetRegistryError(f"{context} must be an object")
    _reject_unknown_fields(raw_rule, RELATION_FIELDS, context)
    key = _required_key(raw_rule, "key", context=context)
    version = _required_string(raw_rule, "version", context=context)
    source_kind = _required_string(raw_rule, "source_kind", context=context)
    target_kind = _required_string(raw_rule, "target_kind", context=context)
    if source_kind not in RELATION_KINDS or target_kind not in RELATION_KINDS:
        raise DataAssetRegistryError(f"Invalid source/target kind in {context}")
    directed = _optional_bool(raw_rule, "directed", context, None)
    if directed is not True:
        raise DataAssetRegistryError(f"{context}.directed must be true")
    self_link = _required_string(raw_rule, "self_link", context=context)
    if self_link != "forbidden":
        raise DataAssetRegistryError(f"{context}.self_link must be forbidden")
    acyclic = _optional_bool(raw_rule, "acyclic", context, False)
    cross_policy = _required_string(raw_rule, "cross_project_policy", context=context)
    if cross_policy not in CROSS_PROJECT_POLICIES:
        raise DataAssetRegistryError(f"Invalid cross-project policy in {context}")
    same_family = _optional_bool(raw_rule, "same_profile_family", context, False)
    outgoing_max = _optional_non_negative_int(raw_rule, "outgoing_max", context)
    incoming_max = _optional_non_negative_int(raw_rule, "incoming_max", context)
    deprecated = _optional_bool(raw_rule, "deprecated", context, False)
    replacement = _optional_key(raw_rule.get("replacement"), f"{context}.replacement")
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")
    contract = {
        "key": key, "version": version, "source_kind": source_kind,
        "target_kind": target_kind, "directed": directed, "self_link": self_link,
        "acyclic": acyclic, "cross_project_policy": cross_policy,
        "same_profile_family": same_family, "outgoing_max": outgoing_max,
        "incoming_max": incoming_max, "deprecated": deprecated,
        "replacement": replacement,
    }
    return RelationRule(digest=_digest(contract), **contract)


def _parse_namespace_rule(raw_rule, *, context):
    if not isinstance(raw_rule, dict):
        raise DataAssetRegistryError(f"{context} must be an object")
    _reject_unknown_fields(raw_rule, NAMESPACE_FIELDS, context)
    key = _required_key(raw_rule, "key", context=context)
    version = _required_string(raw_rule, "version", context=context)
    name = _required_string(raw_rule, "name", context=context)
    pattern = _required_string(raw_rule, "pattern", context=context)
    try:
        re.compile(pattern)
    except re.error as exc:
        raise DataAssetRegistryError(f"Invalid namespace pattern in {context}") from exc
    normalization = _required_string(raw_rule, "normalization", context=context)
    if normalization not in SAFE_NORMALIZATIONS:
        raise DataAssetRegistryError(f"Unknown normalization strategy in {context}")
    resolver = _required_string(raw_rule, "resolver_url_template", context=context)
    if "{value}" not in resolver:
        raise DataAssetRegistryError(f"{context}.resolver_url_template must contain {{value}}")
    targets = _parse_key_list(
        raw_rule.get("allowed_target_kinds"), f"{context}.allowed_target_kinds"
    )
    if not targets or not set(targets).issubset(TARGET_KINDS):
        raise DataAssetRegistryError(f"Invalid allowed target kinds in {context}")
    context_types = _parse_key_list(
        raw_rule.get("allowed_context_types", []), f"{context}.allowed_context_types"
    )
    if context_types and "context" not in targets:
        raise DataAssetRegistryError(
            f"{context}.allowed_context_types requires context target kind"
        )
    deprecated = _optional_bool(raw_rule, "deprecated", context, False)
    replacement = _optional_key(raw_rule.get("replacement"), f"{context}.replacement")
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")
    contract = {
        "key": key, "version": version, "name": name, "pattern": pattern,
        "normalization": normalization, "resolver_url_template": resolver,
        "allowed_target_kinds": list(targets),
        "allowed_context_types": list(context_types), "deprecated": deprecated,
        "replacement": replacement,
    }
    return NamespaceRule(
        key=key, version=version, name=name, pattern=pattern,
        normalization=normalization, resolver_url_template=resolver,
        allowed_target_kinds=targets, allowed_context_types=context_types,
        deprecated=deprecated, replacement=replacement, digest=_digest(contract),
    )


def _parse_file_role_rules(value, *, context, require_core):
    rule_context = f"{context}.file_role_rules"
    if not isinstance(value, dict) or not value:
        raise DataAssetRegistryError(f"{rule_context} must be a non-empty object")
    rules = {}
    for role, raw_rule in value.items():
        _required_key_value(role, f"file role in {context}")
        if not isinstance(raw_rule, dict):
            raise DataAssetRegistryError(f"{rule_context}.{role} must be an object")
        _reject_unknown_fields(raw_rule, {"class", "min", "max"}, f"{rule_context}.{role}")
        role_class = raw_rule.get("class")
        if role_class not in {"core", "auxiliary"}:
            raise DataAssetRegistryError(f"{rule_context}.{role}.class must be core or auxiliary")
        minimum, maximum = _parse_cardinality(raw_rule, context=f"{rule_context}.{role}")
        rules[role] = FileRoleRule(role_class, minimum, maximum)
    if require_core and not any(
        rule.role_class == "core" and rule.minimum >= 1 for rule in rules.values()
    ):
        raise DataAssetRegistryError(f"{rule_context} must require at least one core file role")
    return rules


def _parse_cardinality_rules(value, *, context, allow_targets):
    if not isinstance(value, dict):
        raise DataAssetRegistryError(f"{context} must be an object")
    rules = {}
    allowed = {"min", "max", "allowed_target_profiles"} if allow_targets else {"min", "max"}
    for key, raw_rule in value.items():
        _required_key_value(key, f"rule key in {context}")
        if not isinstance(raw_rule, dict):
            raise DataAssetRegistryError(f"{context}.{key} must be an object")
        _reject_unknown_fields(raw_rule, allowed, f"{context}.{key}")
        minimum, maximum = _parse_cardinality(raw_rule, context=f"{context}.{key}")
        targets = ()
        if allow_targets:
            targets = _parse_profile_reference_list(
                raw_rule.get("allowed_target_profiles", []),
                f"{context}.{key}.allowed_target_profiles",
            )
        rules[key] = CardinalityRule(minimum, maximum, targets)
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
        raise DataAssetRegistryError(f"{context}.max must be null or a non-negative integer")
    if maximum is not None and maximum < minimum:
        raise DataAssetRegistryError(f"{context}.max must be greater than or equal to min")
    return minimum, maximum


def _parse_metadata_schema(mapping, context):
    schema = mapping.get("metadata_schema")
    if not isinstance(schema, dict):
        raise DataAssetRegistryError(f"{context}.metadata_schema must be an object")
    try:
        validator_for(schema).check_schema(schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise DataAssetRegistryError(f"Invalid JSON Schema in {context}") from exc
    return schema


def _parse_public_fields(value, schema, context):
    fields = _parse_key_list(value, f"{context}.public_metadata_fields")
    unknown = sorted(set(fields) - set(schema.get("properties", {})))
    if unknown:
        raise DataAssetRegistryError(
            f"Unknown public metadata field(s) in {context}: {', '.join(unknown)}"
        )
    return fields


def _parse_profile_replacement(value, context):
    if value is None:
        return None
    return _parse_profile_reference(value, f"{context}.replacement")


def _parse_profile_reference(value, context):
    if not isinstance(value, str):
        raise DataAssetRegistryError(f"{context} must use type/profile syntax")
    match = PROFILE_REFERENCE_PATTERN.fullmatch(value)
    if not match:
        raise DataAssetRegistryError(f"Invalid profile reference in {context}: {value!r}")
    return match.group("type"), match.group("profile")


def _parse_profile_reference_list(value, context):
    if not isinstance(value, list):
        raise DataAssetRegistryError(f"{context} must be an array")
    normalized = tuple(
        "/".join(_parse_profile_reference(reference, f"{context}[{index}]"))
        for index, reference in enumerate(value)
    )
    if len(set(normalized)) != len(normalized):
        raise DataAssetRegistryError(f"{context} must not contain duplicates")
    return normalized


def _parse_key_list(value, context):
    if not isinstance(value, list):
        raise DataAssetRegistryError(f"{context} must be an array")
    normalized = tuple(_required_key_value(item, context) for item in value)
    if len(set(normalized)) != len(normalized):
        raise DataAssetRegistryError(f"{context} must not contain duplicates")
    return normalized


def _validate_profile_relation_references(asset_profiles, context_profiles, relation_current):
    current_relations = set(relation_current)
    asset_refs = {
        f"{profile.data_type_key}/{profile.profile_key}" for profile in asset_profiles.values()
    }
    context_refs = {
        f"{profile.context_type_key}/{profile.profile_key}" for profile in context_profiles.values()
    }
    for profile in asset_profiles.values():
        for relation_key, rule in profile.outgoing_relations.items():
            _require_relation(relation_key, current_relations, profile.profile_key)
            _require_known_targets(rule.allowed_target_profiles, asset_refs, profile.profile_key)
        for relation_key, rule in profile.context_link_rules.items():
            _require_relation(relation_key, current_relations, profile.profile_key)
            _require_known_targets(rule.allowed_target_profiles, context_refs, profile.profile_key)
    for profile in context_profiles.values():
        for relation_key, rule in profile.outgoing_relations.items():
            _require_relation(relation_key, current_relations, profile.profile_key)
            _require_known_targets(rule.allowed_target_profiles, context_refs, profile.profile_key)


def _require_relation(key, known, profile_key):
    if key not in known:
        raise DataAssetRegistryError(f"Unknown relation {key} in profile {profile_key}")


def _require_known_targets(targets, known, profile_key):
    unknown = sorted(set(targets) - known)
    if unknown:
        raise DataAssetRegistryError(
            f"Unknown target profile(s) in {profile_key}: {', '.join(unknown)}"
        )


def _validate_replacements(entries, current_versions, label):
    available_keys = set(current_versions)
    for item in entries.values():
        if item.replacement and item.replacement not in available_keys:
            raise DataAssetRegistryError(f"Unknown replacement {label}: {'/'.join(item.replacement)}")


def _validate_key_replacements(entries, current_versions, label):
    available_keys = set(current_versions)
    for item in entries.values():
        if item.replacement and item.replacement not in available_keys:
            raise DataAssetRegistryError(f"Unknown replacement {label}: {item.replacement}")


def _validate_metadata(schema, metadata, object_name):
    if not isinstance(metadata, dict):
        raise DataAssetMetadataError(f"{object_name} metadata must be a JSON object")
    validator = validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(metadata), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "metadata"
        raise DataAssetMetadataError(f"Invalid {location}: {error.message}")


def _validate_count_mapping(counts, label):
    normalized = {}
    for name, count in counts.items():
        _required_key_value(name, f"{label} type")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DataAssetRegistryError(
                f"{label} count for {name} must be a non-negative integer"
            )
        normalized[name] = count
    return normalized


def _validate_actual_counts(actual_counts, rules, *, item_name, profile_name):
    for name in actual_counts:
        if name not in rules:
            raise DataAssetRegistryError(f"{item_name} {name} is not allowed for {profile_name}")
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


def _serialize_file_rules(rules):
    return {
        role: {"class": rule.role_class, "min": rule.minimum, "max": rule.maximum}
        for role, rule in rules.items()
    }


def _serialize_cardinality_rules(rules, include_targets):
    result = {}
    for key, rule in rules.items():
        value = {"min": rule.minimum, "max": rule.maximum}
        if include_targets:
            value["allowed_target_profiles"] = list(rule.allowed_target_profiles)
        result[key] = value
    return result


def _serialize_profile_replacement(value):
    if value is None:
        return None
    return {"data_type_key": value[0], "profile_key": value[1]}


def _normalize_identifier(value, strategy):
    operations = {
        "strip": lambda item: item.strip(),
        "uppercase": lambda item: item.upper(),
        "lowercase": lambda item: item.lower(),
        "strip_uppercase": lambda item: item.strip().upper(),
        "strip_lowercase": lambda item: item.strip().lower(),
    }
    try:
        return operations[strategy](value)
    except KeyError as exc:
        raise DataAssetRegistryError(f"Unsupported normalization strategy: {strategy}") from exc


def _require_digest(expected, actual, label, key):
    if not isinstance(actual, str) or actual != expected:
        raise DataAssetRegistryError(f"{label} digest mismatch for {key}")


def _required_string(mapping, field, *, context):
    return _required_string_value(mapping.get(field), f"{context}.{field}")


def _required_string_value(value, context):
    if not isinstance(value, str) or not value.strip():
        raise DataAssetRegistryError(f"{context} must be a non-empty string")
    return value.strip()


def _required_key(mapping, field, *, context):
    return _required_key_value(
        _required_string(mapping, field, context=context), f"{context}.{field}"
    )


def _required_key_value(value, context):
    value = _required_string_value(value, context)
    if not KEY_PATTERN.fullmatch(value):
        raise DataAssetRegistryError(f"Invalid {context}: {value!r}")
    return value


def _optional_key(value, context):
    if value is None:
        return None
    return _required_key_value(value, context)


def _optional_bool(mapping, field, context, default):
    value = mapping.get(field, default)
    if not isinstance(value, bool):
        raise DataAssetRegistryError(f"{context}.{field} must be boolean")
    return value


def _optional_non_negative_int(mapping, field, context):
    value = mapping.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DataAssetRegistryError(
            f"{context}.{field} must be null or a non-negative integer"
        )
    return value


def _reject_unknown_fields(mapping, allowed, context):
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise DataAssetRegistryError(f"Unknown field(s) in {context}: {', '.join(unknown)}")


def _digest(contract):
    return hashlib.sha256(_canonical_json(contract).encode("utf-8")).hexdigest()


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
