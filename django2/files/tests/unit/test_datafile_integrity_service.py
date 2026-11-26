import hashlib
import tempfile
from pathlib import Path

from django.db import IntegrityError, transaction
from django.test import TestCase

from files.models import DataFile
from files.services.datafile_integrity_service import (
    mark_datafile_unavailable,
    verify_and_mark_datafile_available,
)


class DataFileIntegrityServiceTests(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.root = Path(self.temp_directory.name)
        self.content = b"verified scientific content\n"
        self.path = self.root / "asset.dat"
        self.path.write_bytes(self.content)
        self.roots = {
            "test": {
                "path": str(self.root),
                "internal_uri": "/_protected_test/",
            }
        }

    def create_file(self, **overrides):
        fields = {
            "file_code": "INTEGRITY_FILE",
            "file_name": self.path.name,
            "file_path": str(self.path),
            "file_size": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
        }
        fields.update(overrides)
        return DataFile.objects.create(**fields)

    def test_new_datafile_defaults_to_blocked(self):
        data_file = self.create_file()
        self.assertEqual(data_file.availability_status, DataFile.AVAILABILITY_BLOCKED)

    def test_database_rejects_unknown_availability_status(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_file(availability_status="online")

    def test_matching_protected_file_becomes_available(self):
        data_file = self.create_file()
        result = verify_and_mark_datafile_available(data_file=data_file, roots=self.roots)
        data_file.refresh_from_db()
        self.assertTrue(result.available)
        self.assertEqual(result.reason, "integrity_verified")
        self.assertEqual(data_file.availability_status, DataFile.AVAILABILITY_AVAILABLE)

    def test_outside_root_remains_blocked(self):
        data_file = self.create_file()
        result = verify_and_mark_datafile_available(
            data_file=data_file,
            roots={"other": {"path": str(self.root / "absent"), "internal_uri": "/x/"}},
        )
        self.assertEqual(result.status, DataFile.AVAILABILITY_BLOCKED)
        self.assertEqual(result.reason, "outside_protected_roots")

    def test_missing_file_is_marked_missing(self):
        data_file = self.create_file()
        self.path.unlink()
        result = verify_and_mark_datafile_available(data_file=data_file, roots=self.roots)
        self.assertEqual(result.status, DataFile.AVAILABILITY_MISSING)

    def test_size_or_checksum_mismatch_is_quarantined(self):
        size_mismatch = self.create_file(file_size=len(self.content) + 1)
        result = verify_and_mark_datafile_available(data_file=size_mismatch, roots=self.roots)
        self.assertEqual(result.status, DataFile.AVAILABILITY_QUARANTINED)

        size_mismatch.delete()
        digest_mismatch = self.create_file(sha256="0" * 64)
        result = verify_and_mark_datafile_available(data_file=digest_mismatch, roots=self.roots)
        self.assertEqual(result.status, DataFile.AVAILABILITY_QUARANTINED)

    def test_available_cannot_be_set_without_verification(self):
        data_file = self.create_file()
        with self.assertRaises(ValueError):
            mark_datafile_unavailable(
                data_file=data_file,
                status=DataFile.AVAILABILITY_AVAILABLE,
            )
