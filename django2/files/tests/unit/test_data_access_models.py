from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from files.models import DataAccessToken, DataFile


class DataAccessModelTests(TestCase):
    def test_datafile_defaults_are_fail_closed(self):
        data_file = DataFile.objects.create(
            file_code='DF_ACCESS_DEFAULTS',
            file_name='defaults.fasta',
            file_path='/not/published/defaults.fasta',
        )

        self.assertEqual(data_file.access_level, DataFile.ACCESS_LEVEL_INHERITED)
        self.assertEqual(data_file.publication_status, DataFile.PUBLICATION_DRAFT)
        self.assertIsNone(data_file.content_version)

    def test_content_version_uses_verified_sha256_shape(self):
        digest = 'a' * 64
        data_file = DataFile(sha256=digest.upper())

        self.assertEqual(data_file.content_version, f'sha256:{digest}')

    def test_content_version_rejects_non_hex_digest(self):
        self.assertIsNone(DataFile(sha256='z' * 64).content_version)

    def test_issue_returns_raw_token_but_only_hash_is_persisted(self):
        token, raw_token = DataAccessToken.issue(
            name='pipeline',
            scopes=[
                DataAccessToken.SCOPE_FILE_READ,
                DataAccessToken.SCOPE_METADATA_READ,
                DataAccessToken.SCOPE_FILE_READ,
            ],
        )

        self.assertTrue(raw_token.startswith(f'gdt_{token.token_prefix}_'))
        self.assertNotEqual(token.token_hash, raw_token)
        self.assertNotIn(raw_token, str(token.__dict__))
        self.assertEqual(
            token.scopes,
            [DataAccessToken.SCOPE_FILE_READ, DataAccessToken.SCOPE_METADATA_READ],
        )
        self.assertEqual(DataAccessToken.authenticate(raw_token), token)

    def test_unknown_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            DataAccessToken.issue(name='invalid', scopes=['admin:write'])

    def test_revoked_and_expired_tokens_do_not_authenticate(self):
        revoked, revoked_raw = DataAccessToken.issue(
            name='revoked',
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            revoked_at=timezone.now(),
        )
        expired, expired_raw = DataAccessToken.issue(
            name='expired',
            scopes=[DataAccessToken.SCOPE_FILE_READ],
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertFalse(revoked.is_active)
        self.assertFalse(expired.is_active)
        self.assertIsNone(DataAccessToken.authenticate(revoked_raw))
        self.assertIsNone(DataAccessToken.authenticate(expired_raw))

    def test_modified_secret_does_not_authenticate(self):
        token, raw_token = DataAccessToken.issue(
            name='pipeline',
            scopes=[DataAccessToken.SCOPE_FILE_READ],
        )

        self.assertIsNone(DataAccessToken.authenticate(f'{raw_token}modified'))
        self.assertTrue(token.is_active)
