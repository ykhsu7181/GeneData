import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless

from django.test import TestCase
from django.utils import timezone

from files.models import DataAccessToken, DataFile, Dataset, FileRelation
from files.services.datafile_access_service import (
    ACTION_CONTENT,
    ACTION_MANIFEST,
    ACTION_METADATA,
    ACTION_SEQUENCE,
    resolve_datafile_access,
    resolve_protected_datafile_path,
)


class DataFileAccessServiceTests(TestCase):
    def setUp(self):
        self.public_dataset = Dataset.objects.create(
            dataset_code='DS_PUBLIC_ACCESS',
            visibility='public',
            status='released',
        )
        self.internal_dataset = Dataset.objects.create(
            dataset_code='DS_INTERNAL_ACCESS',
            visibility='lab_internal',
            status='released',
        )
        self.private_dataset = Dataset.objects.create(
            dataset_code='DS_PRIVATE_ACCESS',
            visibility='private',
            status='released',
        )

    def create_file(self, code, **overrides):
        values = {
            'file_code': code,
            'file_name': f'{code}.fasta',
            'file_path': f'/not-used/{code}.fasta',
            'dataset': self.public_dataset,
            'is_current': True,
            'access_level': DataFile.ACCESS_LEVEL_INHERITED,
            'publication_status': DataFile.PUBLICATION_RELEASED,
            'published_at': timezone.now(),
            'sha256': 'a' * 64,
        }
        values.update(overrides)
        return DataFile.objects.create(**values)

    def issue_token(self, *, scopes, access_tier=DataAccessToken.ACCESS_TIER_PUBLIC, **extra):
        token, _raw = DataAccessToken.issue(
            name=f'token-{DataAccessToken.objects.count()}',
            scopes=scopes,
            access_tier=access_tier,
            **extra,
        )
        return token

    def test_draft_and_non_current_files_are_denied(self):
        draft = self.create_file('DF_DRAFT', publication_status=DataFile.PUBLICATION_DRAFT)
        withdrawn = self.create_file(
            'DF_WITHDRAWN', publication_status=DataFile.PUBLICATION_WITHDRAWN
        )
        stale = self.create_file('DF_STALE', is_current=False)

        self.assertEqual(resolve_datafile_access(draft).reason, 'file_not_released')
        self.assertEqual(resolve_datafile_access(withdrawn).reason, 'file_not_released')
        self.assertEqual(resolve_datafile_access(stale).reason, 'file_not_current')

    def test_release_requires_timestamp_and_verified_sha256(self):
        no_timestamp = self.create_file('DF_NO_PUBLISHED_AT', published_at=None)
        no_checksum = self.create_file('DF_NO_SHA256', sha256=None)
        invalid_checksum = self.create_file('DF_BAD_SHA256', sha256='z' * 64)

        self.assertEqual(
            resolve_datafile_access(no_timestamp).reason,
            'file_release_incomplete',
        )
        self.assertEqual(
            resolve_datafile_access(no_checksum).reason,
            'file_checksum_unverified',
        )
        self.assertEqual(
            resolve_datafile_access(invalid_checksum).reason,
            'file_checksum_unverified',
        )

    def test_public_released_metadata_allows_anonymous_access(self):
        data_file = self.create_file('DF_PUBLIC_METADATA')

        decision = resolve_datafile_access(data_file, action=ACTION_METADATA)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PUBLIC)

    def test_public_content_requires_token_and_scope(self):
        data_file = self.create_file('DF_PUBLIC_CONTENT')
        metadata_only = self.issue_token(scopes=[DataAccessToken.SCOPE_METADATA_READ])
        file_reader = self.issue_token(scopes=[DataAccessToken.SCOPE_FILE_READ])

        anonymous = resolve_datafile_access(data_file, action=ACTION_CONTENT)
        wrong_scope = resolve_datafile_access(
            data_file, principal=metadata_only, action=ACTION_CONTENT
        )
        allowed = resolve_datafile_access(
            data_file, principal=file_reader, action=ACTION_CONTENT
        )

        self.assertEqual(anonymous.reason, 'authentication_required')
        self.assertEqual(wrong_scope.reason, 'insufficient_scope')
        self.assertTrue(allowed.allowed)

    def test_each_action_requires_its_own_scope(self):
        data_file = self.create_file('DF_ACTION_SCOPES')
        token = self.issue_token(
            scopes=[
                DataAccessToken.SCOPE_SEQUENCE_READ,
                DataAccessToken.SCOPE_DATASET_MANIFEST,
            ]
        )

        self.assertTrue(
            resolve_datafile_access(data_file, principal=token, action=ACTION_SEQUENCE).allowed
        )
        self.assertTrue(
            resolve_datafile_access(data_file, principal=token, action=ACTION_MANIFEST).allowed
        )
        self.assertFalse(
            resolve_datafile_access(data_file, principal=token, action=ACTION_CONTENT).allowed
        )

    def test_internal_data_requires_internal_token(self):
        data_file = self.create_file('DF_INTERNAL', dataset=self.internal_dataset)
        public_token = self.issue_token(scopes=[DataAccessToken.SCOPE_FILE_READ])
        internal_token = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        denied = resolve_datafile_access(
            data_file, principal=public_token, action=ACTION_CONTENT
        )
        allowed = resolve_datafile_access(
            data_file, principal=internal_token, action=ACTION_CONTENT
        )

        self.assertEqual(denied.reason, 'insufficient_access_tier')
        self.assertTrue(allowed.allowed)

    def test_private_file_policy_overrides_public_dataset(self):
        data_file = self.create_file(
            'DF_EXPLICIT_PRIVATE', access_level=DataFile.ACCESS_LEVEL_PRIVATE
        )
        internal_token = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        decision = resolve_datafile_access(
            data_file, principal=internal_token, action=ACTION_CONTENT
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PRIVATE)

    def test_mixed_dataset_relations_use_most_restrictive_policy(self):
        data_file = self.create_file('DF_MIXED_RELATIONS')
        FileRelation.objects.create(
            file=data_file,
            related_type='dataset',
            related_id=str(self.private_dataset.id),
            related_code=self.private_dataset.dataset_code,
            file_role='source',
        )
        token = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        decision = resolve_datafile_access(
            data_file, principal=token, action=ACTION_CONTENT
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PRIVATE)

    def test_inherited_file_without_dataset_policy_is_denied(self):
        data_file = self.create_file('DF_NO_POLICY', dataset=None)

        decision = resolve_datafile_access(data_file, action=ACTION_METADATA)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, 'no_inherited_access_policy')

    def test_explicit_public_policy_can_publish_file_without_dataset(self):
        data_file = self.create_file(
            'DF_EXPLICIT_PUBLIC',
            dataset=None,
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
        )

        decision = resolve_datafile_access(data_file, action=ACTION_METADATA)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PUBLIC)

    def test_unreleased_dataset_denies_inherited_file(self):
        draft_dataset = Dataset.objects.create(
            dataset_code='DS_DRAFT_ACCESS',
            visibility='public',
            status='draft',
        )
        data_file = self.create_file('DF_DRAFT_DATASET', dataset=draft_dataset)

        decision = resolve_datafile_access(data_file, action=ACTION_METADATA)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_access_level, DataFile.ACCESS_LEVEL_PRIVATE)

    def test_invalid_dataset_relation_fails_closed(self):
        data_file = self.create_file('DF_INVALID_RELATION', dataset=None)
        FileRelation.objects.create(
            file=data_file,
            related_type='dataset',
            related_id='not-a-dataset-id',
            file_role='source',
        )

        decision = resolve_datafile_access(data_file, action=ACTION_METADATA)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, 'policy_integrity_error')

    def test_expired_or_revoked_token_is_denied(self):
        data_file = self.create_file('DF_INACTIVE_TOKEN')
        expired = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        revoked = self.issue_token(
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            revoked_at=timezone.now(),
        )

        self.assertEqual(
            resolve_datafile_access(data_file, principal=expired, action=ACTION_CONTENT).reason,
            'invalid_or_inactive_token',
        )
        self.assertEqual(
            resolve_datafile_access(data_file, principal=revoked, action=ACTION_CONTENT).reason,
            'invalid_or_inactive_token',
        )


class ProtectedDataFilePathTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name, 'protected')
        self.outside = Path(self.temp_dir.name, 'outside')
        self.root.mkdir()
        self.outside.mkdir()
        self.roots = {
            'test': {
                'path': str(self.root),
                'internal_uri': '/_protected_test/',
            }
        }

    def create_disk_file(self, path, content=b'>Chr1\nACGT\n'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def create_data_file(self, code, path):
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
        )

    def test_file_inside_root_maps_to_internal_uri(self):
        path = self.create_disk_file(self.root / 'IR64 data' / 'genome.fasta')
        data_file = self.create_data_file('DF_PATH_INSIDE', path)

        location = resolve_protected_datafile_path(data_file, roots=self.roots)

        self.assertTrue(location.allowed)
        self.assertEqual(location.root_name, 'test')
        self.assertEqual(
            location.internal_uri,
            '/_protected_test/IR64%20data/genome.fasta',
        )

    def test_most_specific_nested_root_wins(self):
        nested_root = self.root / 'derived'
        path = self.create_disk_file(nested_root / 'index.fai')
        data_file = self.create_data_file('DF_PATH_NESTED', path)
        roots = {
            **self.roots,
            'nested': {
                'path': str(nested_root),
                'internal_uri': '/_protected_nested/',
            },
        }

        location = resolve_protected_datafile_path(data_file, roots=roots)

        self.assertTrue(location.allowed)
        self.assertEqual(location.root_name, 'nested')
        self.assertEqual(location.internal_uri, '/_protected_nested/index.fai')

    def test_file_outside_root_is_denied(self):
        path = self.create_disk_file(self.outside / 'genome.fasta')
        data_file = self.create_data_file('DF_PATH_OUTSIDE', path)

        location = resolve_protected_datafile_path(data_file, roots=self.roots)

        self.assertFalse(location.allowed)
        self.assertEqual(location.reason, 'outside_protected_roots')

    def test_missing_file_is_denied(self):
        data_file = self.create_data_file('DF_PATH_MISSING', self.root / 'missing.fasta')

        location = resolve_protected_datafile_path(data_file, roots=self.roots)

        self.assertFalse(location.allowed)
        self.assertEqual(location.reason, 'file_missing')

    @skipUnless(hasattr(os, 'symlink'), 'symbolic links are not supported')
    def test_symlink_escape_is_denied(self):
        target = self.create_disk_file(self.outside / 'secret.fasta')
        link = self.root / 'linked.fasta'
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f'symbolic link creation is unavailable: {exc}')
        data_file = self.create_data_file('DF_PATH_SYMLINK', link)

        location = resolve_protected_datafile_path(data_file, roots=self.roots)

        self.assertFalse(location.allowed)
        self.assertEqual(location.reason, 'outside_protected_roots')
