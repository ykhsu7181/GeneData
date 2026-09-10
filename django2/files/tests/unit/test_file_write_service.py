from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from files.models import DataFile, FileRelation
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)


class FileWriteServiceTestCase(TestCase):
    def test_unknown_role_is_rejected_before_relation_write(self):
        data_file = DataFile.objects.create(
            file_code="FILE_ROLE_VALIDATION",
            file_name="invalid-role.dat",
            file_path="/tmp/invalid-role.dat",
        )

        with self.assertRaises(ValueError):
            create_or_get_file_relation(
                data_file=data_file,
                related_type="accession",
                related_id="1",
                file_role="not_canonical",
            )

        self.assertFalse(FileRelation.objects.filter(file=data_file).exists())

    def test_datafile_creation_retries_after_file_code_conflict(self):
        original_create = DataFile.objects.create
        attempts = 0

        def create_with_first_collision(**values):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise IntegrityError("duplicate file_code")
            return original_create(**values)

        with patch(
            "files.services.file_write_service.make_next_file_code",
            side_effect=["FILE000001", "FILE000002"],
        ), patch.object(DataFile.objects, "create", side_effect=create_with_first_collision):
            data_file, created, reused, _ = create_or_get_datafile_from_path(
                file_path="/phase4/retry.fastq.gz",
                normalize_path=False,
            )

        self.assertTrue(created)
        self.assertFalse(reused)
        self.assertEqual(attempts, 2)
        self.assertEqual(data_file.file_code, "FILE000002")

    def test_datafile_service_preserves_manifest_creation_metadata(self):
        data_file, created, _, _ = create_or_get_datafile_from_path(
            file_path="/phase4/raw.fastq.gz",
            file_name="raw.fastq.gz",
            file_size=128,
            md5="abc",
            description='{"raw_data": {"sample_code": "S1"}}',
            normalize_path=False,
        )

        self.assertTrue(created)
        self.assertEqual(data_file.file_size, 128)
        self.assertEqual(data_file.md5, "abc")
        self.assertIn("sample_code", data_file.description)
