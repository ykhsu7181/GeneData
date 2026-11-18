"""Single loading and validation boundary for DataAsset profile definitions."""

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Optional, Tuple

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.validators import validator_for


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "data_asset_registry" / "registry.json"
)
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class DataAssetRegistryError(ValueError):
    """Base error for invalid registry definitions or values."""


class DataAssetProfileNotFound(DataAssetRegistryError):
    """Raised when a requested type/profile pair is not registered."""


class DataAssetMetadataError(DataAssetRegistryError):
    """Raised when metadata does not match its registered schema."""


@dataclass(frozen=True)
class DataAssetProfile:
    data_type_key: str
    profile_key: str
    schema_version: str
    schema_digest: str
    metadata_schema: dict
    file_roles: frozenset
    deprecated: bool
    replacement: Optional[Tuple[str, str]]


class DataAssetRegistry:
    def __init__(self, *, registry_version, profiles):
        self.registry_version = registry_version
        self._profiles = profiles

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

        validator_class = validator_for(profile.metadata_schema)
        validator = validator_class(profile.metadata_schema)
        errors = sorted(validator.iter_errors(metadata), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.path) or "metadata"
            raise DataAssetMetadataError(f"Invalid {location}: {error.message}")
        return profile

    def validate_file_role(self, data_type_key, profile_key, file_role):
        profile = self.get_profile(data_type_key, profile_key)
        if file_role not in profile.file_roles:
            raise DataAssetRegistryError(
                f"Unknown file role for {data_type_key}/{profile_key}: {file_role}"
            )
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
    registry_version = _required_string(raw_registry, "registry_version", context="registry")
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

    data_type_key = _required_key(raw_profile, "data_type_key", context=context)
    profile_key = _required_key(raw_profile, "profile_key", context=context)
    schema_version = _required_string(raw_profile, "schema_version", context=context)
    metadata_schema = raw_profile.get("metadata_schema")
    if not isinstance(metadata_schema, dict):
        raise DataAssetRegistryError(f"{context}.metadata_schema must be a JSON object")
    try:
        validator_for(metadata_schema).check_schema(metadata_schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise DataAssetRegistryError(f"Invalid JSON Schema in {context}") from exc

    raw_roles = raw_profile.get("file_roles")
    if not isinstance(raw_roles, list) or not raw_roles:
        raise DataAssetRegistryError(f"{context}.file_roles must be a non-empty list")
    file_roles = []
    for role in raw_roles:
        if not isinstance(role, str) or not KEY_PATTERN.fullmatch(role):
            raise DataAssetRegistryError(f"Invalid file role in {context}: {role!r}")
        file_roles.append(role)
    if len(file_roles) != len(set(file_roles)):
        raise DataAssetRegistryError(f"Duplicate file role in {context}")

    deprecated = raw_profile.get("deprecated", False)
    if not isinstance(deprecated, bool):
        raise DataAssetRegistryError(f"{context}.deprecated must be boolean")
    replacement = _parse_replacement(raw_profile.get("replacement"), context=context)
    if replacement and not deprecated:
        raise DataAssetRegistryError(f"{context}.replacement requires deprecated=true")

    return DataAssetProfile(
        data_type_key=data_type_key,
        profile_key=profile_key,
        schema_version=schema_version,
        schema_digest=_schema_digest(metadata_schema),
        metadata_schema=metadata_schema,
        file_roles=frozenset(file_roles),
        deprecated=deprecated,
        replacement=replacement,
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


def _parse_replacement(value, *, context):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DataAssetRegistryError(f"{context}.replacement must be null or an object")
    return (
        _required_key(value, "data_type_key", context=f"{context}.replacement"),
        _required_key(value, "profile_key", context=f"{context}.replacement"),
    )


def _schema_digest(schema):
    canonical = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
