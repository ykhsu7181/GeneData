"""Fail-closed access and protected-path decisions for DataFile APIs."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from django.conf import settings

from files.models import DataAccessToken, DataFile, Dataset, FileRelation


ACTION_METADATA = 'metadata'
ACTION_CONTENT = 'content'
ACTION_SEQUENCE = 'sequence'
ACTION_MANIFEST = 'manifest'
ACTION_BATCH = 'batch'
ACTION_ARCHIVE = 'archive'
ACTION_ARCHIVE_DOWNLOAD = 'archive_download'

ACTION_SCOPES = {
    ACTION_METADATA: DataAccessToken.SCOPE_METADATA_READ,
    ACTION_CONTENT: DataAccessToken.SCOPE_FILE_READ,
    ACTION_SEQUENCE: DataAccessToken.SCOPE_SEQUENCE_READ,
    ACTION_MANIFEST: DataAccessToken.SCOPE_DATASET_MANIFEST,
    ACTION_BATCH: DataAccessToken.SCOPE_BATCH_CREATE,
    ACTION_ARCHIVE: DataAccessToken.SCOPE_BATCH_ARCHIVE,
    ACTION_ARCHIVE_DOWNLOAD: DataAccessToken.SCOPE_BATCH_DOWNLOAD,
}

LEVEL_RANK = {
    DataFile.ACCESS_LEVEL_PUBLIC: 0,
    DataFile.ACCESS_LEVEL_INTERNAL: 1,
    DataFile.ACCESS_LEVEL_PRIVATE: 2,
}


@dataclass(frozen=True)
class DataFileAccessDecision:
    allowed: bool
    reason: str
    effective_access_level: str
    required_scope: str = ''


@dataclass(frozen=True)
class ProtectedFileLocation:
    allowed: bool
    reason: str
    root_name: str = ''
    resolved_path: str = ''
    internal_uri: str = ''


def resolve_datafile_access(data_file, *, principal=None, action=ACTION_METADATA):
    """Return one deterministic, fail-closed access decision for a DataFile."""
    if action not in ACTION_SCOPES:
        raise ValueError(f'Unsupported DataFile access action: {action}')

    if not data_file.is_current:
        return _deny('file_not_current')
    if data_file.publication_status != DataFile.PUBLICATION_RELEASED:
        return _deny('file_not_released')
    if data_file.published_at is None:
        return _deny('file_release_incomplete')
    if data_file.content_version is None:
        return _deny('file_checksum_unverified')

    effective_level, policy_reason = resolve_datafile_access_level(data_file)
    if effective_level == DataFile.ACCESS_LEVEL_PRIVATE:
        return _deny(policy_reason, effective_level=effective_level)

    required_scope = ACTION_SCOPES[action]
    if action == ACTION_METADATA and effective_level == DataFile.ACCESS_LEVEL_PUBLIC:
        return DataFileAccessDecision(
            allowed=True,
            reason='public_metadata',
            effective_access_level=effective_level,
            required_scope=required_scope,
        )
    if (
        action == ACTION_CONTENT
        and effective_level == DataFile.ACCESS_LEVEL_PUBLIC
        and getattr(settings, 'GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT', False)
    ):
        return DataFileAccessDecision(
            allowed=True,
            reason='public_content',
            effective_access_level=effective_level,
            required_scope=required_scope,
        )

    if principal is None:
        return _deny(
            'authentication_required',
            effective_level=effective_level,
            required_scope=required_scope,
        )
    if not isinstance(principal, DataAccessToken) or not principal.is_active:
        return _deny(
            'invalid_or_inactive_token',
            effective_level=effective_level,
            required_scope=required_scope,
        )
    if not principal.has_scope(required_scope):
        return _deny(
            'insufficient_scope',
            effective_level=effective_level,
            required_scope=required_scope,
        )
    if (
        effective_level == DataFile.ACCESS_LEVEL_INTERNAL
        and principal.access_tier != DataAccessToken.ACCESS_TIER_INTERNAL
    ):
        return _deny(
            'insufficient_access_tier',
            effective_level=effective_level,
            required_scope=required_scope,
        )

    return DataFileAccessDecision(
        allowed=True,
        reason='token_authorized',
        effective_access_level=effective_level,
        required_scope=required_scope,
    )


def resolve_protected_datafile_path(data_file, *, roots=None):
    """Map a DataFile to an internal URI without permitting root or symlink escape."""
    if not data_file.file_path:
        return ProtectedFileLocation(False, 'file_path_missing')

    try:
        candidate = Path(data_file.file_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return ProtectedFileLocation(False, 'file_missing')
    if not candidate.is_file():
        return ProtectedFileLocation(False, 'not_a_file')

    configured_roots = roots if roots is not None else getattr(
        settings, 'GENEDATA_PROTECTED_FILE_ROOTS', {}
    )
    normalized_roots = []
    for root_name, root_config in configured_roots.items():
        try:
            root = Path(root_config['path']).resolve(strict=True)
        except (KeyError, TypeError, OSError, RuntimeError, ValueError):
            continue
        if root.is_dir():
            normalized_roots.append((root_name, root_config, root))

    for root_name, root_config, root in sorted(
        normalized_roots,
        key=lambda item: len(item[2].parts),
        reverse=True,
    ):
        try:
            relative_path = candidate.relative_to(root)
        except ValueError:
            continue

        internal_prefix = str(root_config.get('internal_uri') or '').strip()
        if not internal_prefix.startswith('/'):
            continue
        internal_uri = f"{internal_prefix.rstrip('/')}/{quote(relative_path.as_posix(), safe='/')}"
        return ProtectedFileLocation(
            allowed=True,
            reason='protected_root_match',
            root_name=str(root_name),
            resolved_path=str(candidate),
            internal_uri=internal_uri,
        )

    return ProtectedFileLocation(False, 'outside_protected_roots')


def resolve_datafile_access_level(data_file, *, access_level=None):
    """Resolve file and Dataset policy without applying publication gates."""
    dataset_levels, integrity_error = get_datafile_dataset_access_levels(data_file)
    if integrity_error:
        return DataFile.ACCESS_LEVEL_PRIVATE, 'policy_integrity_error'

    configured_level = access_level or data_file.access_level
    if configured_level == DataFile.ACCESS_LEVEL_INHERITED:
        if not dataset_levels:
            return DataFile.ACCESS_LEVEL_PRIVATE, 'no_inherited_access_policy'
        return _most_restrictive(dataset_levels), 'dataset_policy_denied'

    levels = [configured_level]
    levels.extend(dataset_levels)
    effective_level = _most_restrictive(levels)
    reason = 'file_or_dataset_policy_denied' if effective_level == DataFile.ACCESS_LEVEL_PRIVATE else 'ok'
    return effective_level, reason


def get_datafile_dataset_access_levels(data_file):
    """Return related Dataset access levels plus an integrity-error flag."""
    dataset_ids = set()
    if data_file.dataset_id is not None:
        dataset_ids.add(data_file.dataset_id)

    related_ids = FileRelation.objects.filter(
        file=data_file,
        related_type='dataset',
    ).values_list('related_id', flat=True)
    for related_id in related_ids:
        try:
            dataset_ids.add(int(related_id))
        except (TypeError, ValueError):
            return [], True

    if not dataset_ids:
        return [], False

    datasets = list(Dataset.objects.filter(id__in=dataset_ids))
    if len(datasets) != len(dataset_ids):
        return [], True
    return [_dataset_access_level(dataset) for dataset in datasets], False


def _dataset_access_level(dataset):
    if dataset.status != 'released':
        return DataFile.ACCESS_LEVEL_PRIVATE
    if dataset.visibility == 'public':
        return DataFile.ACCESS_LEVEL_PUBLIC
    if dataset.visibility == 'lab_internal':
        return DataFile.ACCESS_LEVEL_INTERNAL
    return DataFile.ACCESS_LEVEL_PRIVATE


def _most_restrictive(levels):
    return max(levels, key=lambda level: LEVEL_RANK.get(level, LEVEL_RANK[DataFile.ACCESS_LEVEL_PRIVATE]))


def _deny(reason, *, effective_level=DataFile.ACCESS_LEVEL_PRIVATE, required_scope=''):
    return DataFileAccessDecision(
        allowed=False,
        reason=reason,
        effective_access_level=effective_level,
        required_scope=required_scope,
    )
