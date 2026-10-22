import hashlib
import json
import tarfile
import tempfile
import zipfile
from io import StringIO
from pathlib import Path

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import DataAccessToken, DataFile, ExternalFileArchive, FileRelation
from files.services.external_file_batch_service import create_batch
from files.services.external_file_archive_service import cleanup_expired_archives


class ExternalFileArchiveApiV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.source_root = self.base / "source"
        self.archive_root = self.base / "archives"
        self.source_root.mkdir()
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.source_root), "internal_uri": "/_protected_test/"}
            },
            GENEDATA_EXTERNAL_ARCHIVE_ROOT=str(self.archive_root),
            GENEDATA_EXTERNAL_ARCHIVE_INTERNAL_URI="/_protected_archives/",
            GENEDATA_ARCHIVE_MIN_FREE_BYTES=0,
            GENEDATA_ARCHIVE_MAX_INPUT_BYTES=1024 * 1024,
            GENEDATA_ARCHIVE_TTL_HOURS=24,
            GENEDATA_ARCHIVE_MAX_ACTIVE_PER_TOKEN=3,
            GENEDATA_ARCHIVE_MAX_ACTIVE_PER_BATCH=2,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.token, self.raw_token = DataAccessToken.issue(
            name="archive-client",
            scopes=[
                DataAccessToken.SCOPE_BATCH_CREATE,
                DataAccessToken.SCOPE_BATCH_READ,
                DataAccessToken.SCOPE_BATCH_ARCHIVE,
                DataAccessToken.SCOPE_BATCH_DOWNLOAD,
            ],
        )
        self.first = self.make_file("FILE_ONE", "genome.fasta", b">chr1\nACGT\n")
        self.second = self.make_file("FILE_TWO", "genes.gff3", b"##gff-version 3\n")
        self.batch, _created = create_batch(
            {"file_codes": [self.first.file_code, self.second.file_code], "strict": True},
            principal=self.token,
        )

    def make_file(self, code, name, content):
        path = self.source_root / code / name
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        data_file = DataFile.objects.create(
            file_code=code,
            file_name=name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
            is_current=True,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="other",
            related_id="archive-test",
            file_role="genome_fasta" if name.endswith("fasta") else "annotation_gff3",
            is_primary=True,
        )
        return data_file

    def auth(self, raw_token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token or self.raw_token}"}

    def queue(self, archive_format="zip", **headers):
        return self.client.post(
            f"/gd/api/v1/file-batches/{self.batch.batch_id}/archives/",
            {"format": archive_format},
            content_type="application/json",
            **self.auth(),
            **headers,
        )

    def test_queue_is_asynchronous_idempotent_and_scope_protected(self):
        _wrong, wrong_raw = DataAccessToken.issue(
            name="batch-reader",
            scopes=[DataAccessToken.SCOPE_BATCH_READ],
        )
        denied = self.client.post(
            f"/gd/api/v1/file-batches/{self.batch.batch_id}/archives/",
            {"format": "zip"},
            content_type="application/json",
            **self.auth(wrong_raw),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["code"], "insufficient_scope")

        headers = {"HTTP_IDEMPOTENCY_KEY": "genescreen-archive-001"}
        created = self.queue(**headers)
        replay = self.queue(**headers)

        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()["status"], "queued")
        self.assertEqual(created["Retry-After"], "5")
        self.assertEqual(created["Location"], created.json()["status_url"])
        self.assertIsNone(created.json()["download_url"])
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["archive_id"], created.json()["archive_id"])
        self.assertEqual(ExternalFileArchive.objects.count(), 1)
        self.assertFalse(self.archive_root.exists())

        conflict = self.client.post(
            f"/gd/api/v1/file-batches/{self.batch.batch_id}/archives/",
            {"format": "tar.gz"},
            content_type="application/json",
            **self.auth(),
            **headers,
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "idempotency_conflict")

    def test_active_archive_queue_is_bounded(self):
        first = self.queue()
        self.assertEqual(first.status_code, 202)
        with override_settings(GENEDATA_ARCHIVE_MAX_ACTIVE_PER_BATCH=1):
            limited = self.queue("tar.gz")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["code"], "archive_queue_limit")

    def test_worker_builds_zip_with_manifest_and_verified_source_files(self):
        archive_id = self.queue().json()["archive_id"]
        output = StringIO()
        call_command("process_external_archive_jobs", once=True, stdout=output)
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)

        self.assertEqual(archive.status, ExternalFileArchive.STATUS_READY)
        self.assertEqual(archive.attempt_count, 1)
        archive_path = self.archive_root / archive.output_relative_path
        self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(), archive.archive_sha256)
        with zipfile.ZipFile(archive_path) as bundle:
            names = set(bundle.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("manifest.tsv", names)
            self.assertIn("files/0001-FILE_ONE/genome.fasta", names)
            self.assertIn("files/0002-FILE_TWO/genes.gff3", names)
            self.assertEqual(bundle.read("files/0001-FILE_ONE/genome.fasta"), b">chr1\nACGT\n")
            manifest = json.loads(bundle.read("manifest.json"))
            self.assertEqual(manifest["snapshot_sha256"], self.batch.snapshot_sha256)
            self.assertNotIn(str(self.source_root), str(manifest))
        self.assertIn(f"{archive_id}\tready", output.getvalue())

    def test_worker_builds_tar_gz(self):
        archive_id = self.queue("tar.gz").json()["archive_id"]
        call_command("process_external_archive_jobs", once=True, stdout=StringIO())
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)
        self.assertEqual(archive.status, ExternalFileArchive.STATUS_READY)
        with tarfile.open(self.archive_root / archive.output_relative_path, mode="r:gz") as bundle:
            self.assertIn("manifest.json", bundle.getnames())
            member = bundle.extractfile("files/0002-FILE_TWO/genes.gff3")
            self.assertEqual(member.read(), b"##gff-version 3\n")

    def test_worker_fails_closed_when_source_bytes_change(self):
        archive_id = self.queue().json()["archive_id"]
        Path(self.first.file_path).write_bytes(b">chr1\nTGCA\n")
        call_command("process_external_archive_jobs", once=True, stdout=StringIO())
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)

        self.assertEqual(archive.status, ExternalFileArchive.STATUS_FAILED)
        self.assertEqual(archive.error_code, "source_checksum_mismatch")
        self.assertFalse(archive.output_relative_path)
        self.assertNotIn(str(self.source_root), archive.error_detail)

    def test_worker_fails_when_archive_scope_is_revoked_after_queue(self):
        archive_id = self.queue().json()["archive_id"]
        self.token.scopes = [
            DataAccessToken.SCOPE_BATCH_CREATE,
            DataAccessToken.SCOPE_BATCH_READ,
            DataAccessToken.SCOPE_BATCH_DOWNLOAD,
        ]
        self.token.save(update_fields=["scopes"])
        call_command("process_external_archive_jobs", once=True, stdout=StringIO())
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)
        self.assertEqual(archive.status, ExternalFileArchive.STATUS_FAILED)
        self.assertEqual(archive.error_code, "archive_access_revoked")

    def test_ready_archive_status_and_download_are_owner_and_scope_isolated(self):
        archive_id = self.queue().json()["archive_id"]
        call_command("process_external_archive_jobs", once=True, stdout=StringIO())
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)

        status_response = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/", **self.auth()
        )
        download = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/content/", **self.auth()
        )
        conditional = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/content/",
            HTTP_IF_NONE_MATCH=f'"sha256-{archive.archive_sha256}"',
            **self.auth(),
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["download_url"], f"/gd/api/v1/file-archives/{archive_id}/content/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["X-Accel-Redirect"], f"/_protected_archives/{archive.output_relative_path}")
        self.assertEqual(download["X-Archive-SHA256"], archive.archive_sha256)
        self.assertNotIn(str(self.archive_root), str(download.items()))
        self.assertEqual(conditional.status_code, 304)

        _other, other_raw = DataAccessToken.issue(
            name="other-archive-client",
            scopes=[DataAccessToken.SCOPE_BATCH_READ, DataAccessToken.SCOPE_BATCH_DOWNLOAD],
        )
        hidden = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/", **self.auth(other_raw)
        )
        self.assertEqual(hidden.status_code, 404)

        self.first.access_level = DataFile.ACCESS_LEVEL_PRIVATE
        self.first.save(update_fields=["access_level"])
        policy_hidden = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/content/", **self.auth()
        )
        self.assertEqual(policy_hidden.status_code, 404)

    def test_cleanup_requires_expiry_and_removes_ready_output(self):
        archive_id = self.queue().json()["archive_id"]
        call_command("process_external_archive_jobs", once=True, stdout=StringIO())
        archive = ExternalFileArchive.objects.get(archive_id=archive_id)
        archive.expires_at = timezone.now()
        archive.save(update_fields=["expires_at"])
        output_path = self.archive_root / archive.output_relative_path
        expired_status = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/", **self.auth()
        )
        self.assertEqual(expired_status.json()["status"], "expired")
        self.assertIsNone(expired_status.json()["download_url"])

        processed, removed = cleanup_expired_archives()
        archive.refresh_from_db()

        self.assertEqual((processed, removed), (1, 1))
        self.assertEqual(archive.status, ExternalFileArchive.STATUS_EXPIRED)
        self.assertFalse(output_path.exists())
        expired = self.client.get(
            f"/gd/api/v1/file-archives/{archive_id}/content/", **self.auth()
        )
        self.assertEqual(expired.status_code, 410)

    def test_cleanup_command_is_dry_run_without_apply(self):
        archive = ExternalFileArchive.objects.create(
            archive_id="ARCH-EXPIRED",
            batch=self.batch,
            created_by_token=self.token,
            token_prefix_snapshot=self.token.token_prefix,
            archive_format=ExternalFileArchive.FORMAT_ZIP,
            request_fingerprint="a" * 64,
            archive_name="expired.zip",
            file_count=self.batch.file_count,
            total_input_size=self.batch.total_size,
            expires_at=timezone.now(),
        )
        output = StringIO()
        call_command("cleanup_external_archives", stdout=output)
        archive.refresh_from_db()
        self.assertEqual(archive.status, ExternalFileArchive.STATUS_QUEUED)
        self.assertIn("mode\tDRY_RUN", output.getvalue())
