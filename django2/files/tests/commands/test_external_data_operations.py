import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from files.models import DataAccessToken, DataFile, Dataset, FileRelation


class ExternalDataOperationsCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "protected"
        self.root.mkdir()
        self.report_dir = Path(self.temp_dir.name) / "reports"
        self.report_dir.mkdir()
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username="publisher", password="unused")

    def make_file(self, code, content=b"data", **overrides):
        path = self.root / f"{code}.txt"
        path.write_bytes(content)
        values = {
            "file_code": code,
            "file_name": path.name,
            "file_path": str(path),
            "file_size": len(content),
        }
        values.update(overrides)
        return DataFile.objects.create(**values)

    def write_manifest(self, rows):
        path = Path(self.temp_dir.name) / "publish.tsv"
        lines = ["file_code\taccess_level\tsha256"]
        lines.extend("\t".join(row) for row in rows)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def report_content(self, prefix):
        matches = list(self.report_dir.glob(f"{prefix}_*.tsv"))
        self.assertEqual(len(matches), 1)
        return matches[0].read_text(encoding="utf-8")

    def test_audit_is_read_only_and_reports_policy_conflict(self):
        dataset = Dataset.objects.create(
            dataset_code="DS_INTERNAL",
            visibility="lab_internal",
            status="released",
        )
        data_file = self.make_file(
            "AUDIT",
            dataset=dataset,
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
            sha256=hashlib.sha256(b"data").hexdigest(),
        )
        before = (data_file.access_level, data_file.publication_status, data_file.sha256)
        stdout = StringIO()

        call_command("audit_datafile_access", output_dir=self.report_dir, stdout=stdout)

        data_file.refresh_from_db()
        self.assertEqual(before, (data_file.access_level, data_file.publication_status, data_file.sha256))
        self.assertIn("policy_conflict\t1", stdout.getvalue())
        self.assertIn("ready\t1", stdout.getvalue())
        self.assertIn("policy_conflict", self.report_content("datafile_access_audit"))

    def test_sha256_backfill_defaults_to_dry_run_then_applies_and_resumes(self):
        data_file = self.make_file("HASH", b"hash me")
        dry_output = StringIO()
        call_command(
            "backfill_datafile_sha256",
            output_dir=self.report_dir,
            data_file_ids=[data_file.id],
            stdout=dry_output,
        )
        data_file.refresh_from_db()
        self.assertIsNone(data_file.sha256)
        self.assertIn("mode\tDRY_RUN", dry_output.getvalue())

        apply_output = StringIO()
        call_command(
            "backfill_datafile_sha256",
            apply=True,
            output_dir=self.report_dir,
            data_file_ids=[data_file.id],
            stdout=apply_output,
        )
        data_file.refresh_from_db()
        self.assertEqual(data_file.sha256, hashlib.sha256(b"hash me").hexdigest())
        self.assertIn("applied\t1", apply_output.getvalue())

        resume_output = StringIO()
        call_command(
            "backfill_datafile_sha256",
            apply=True,
            output_dir=self.report_dir,
            data_file_ids=[data_file.id],
            stdout=resume_output,
        )
        self.assertIn("skipped\t1", resume_output.getvalue())

    def test_sha256_backfill_refuses_file_outside_protected_roots(self):
        outside = Path(self.temp_dir.name) / "outside.txt"
        outside.write_bytes(b"secret")
        data_file = DataFile.objects.create(
            file_code="OUTSIDE", file_name=outside.name, file_path=str(outside)
        )
        stdout = StringIO()

        call_command(
            "backfill_datafile_sha256", apply=True, output_dir=self.report_dir,
            data_file_ids=[data_file.id], stdout=stdout,
        )

        data_file.refresh_from_db()
        self.assertIsNone(data_file.sha256)
        self.assertIn("failed\t1", stdout.getvalue())

    def test_publish_dry_run_then_apply_sets_release_audit_fields(self):
        digest = hashlib.sha256(b"publish").hexdigest()
        data_file = self.make_file("PUB", b"publish", sha256=digest)
        manifest = self.write_manifest([("PUB", "public", digest)])

        call_command("publish_datafiles", manifest=manifest, output_dir=self.report_dir)
        data_file.refresh_from_db()
        self.assertEqual(data_file.publication_status, DataFile.PUBLICATION_DRAFT)

        stdout = StringIO()
        call_command(
            "publish_datafiles", manifest=manifest, apply=True,
            published_by=self.user.username, output_dir=self.report_dir, stdout=stdout,
        )
        data_file.refresh_from_db()
        self.assertEqual(data_file.access_level, DataFile.ACCESS_LEVEL_PUBLIC)
        self.assertEqual(data_file.publication_status, DataFile.PUBLICATION_RELEASED)
        self.assertIsNotNone(data_file.published_at)
        self.assertEqual(data_file.published_by, self.user)
        self.assertIn("applied\t1", stdout.getvalue())

    def test_publish_is_all_or_nothing_when_any_manifest_row_is_blocked(self):
        digest = hashlib.sha256(b"valid").hexdigest()
        valid = self.make_file("VALID", b"valid", sha256=digest)
        manifest = self.write_manifest([
            ("VALID", "public", digest),
            ("MISSING", "public", ""),
        ])

        with self.assertRaises(CommandError):
            call_command(
                "publish_datafiles", manifest=manifest, apply=True,
                published_by=self.user.username, output_dir=self.report_dir,
            )

        valid.refresh_from_db()
        self.assertEqual(valid.publication_status, DataFile.PUBLICATION_DRAFT)
        report = self.report_content("datafile_publication")
        self.assertIn("datafile_not_found", report)

    def test_publish_rejects_manifest_checksum_mismatch(self):
        data_file = self.make_file("MISMATCH", sha256=hashlib.sha256(b"data").hexdigest())
        manifest = self.write_manifest([("MISMATCH", "public", "0" * 64)])

        with self.assertRaises(CommandError):
            call_command("publish_datafiles", manifest=manifest, output_dir=self.report_dir)

        data_file.refresh_from_db()
        self.assertEqual(data_file.publication_status, DataFile.PUBLICATION_DRAFT)

    def test_publish_blocks_genome_fasta_without_registered_fresh_index(self):
        digest = hashlib.sha256(b">chr1\nACGT\n").hexdigest()
        data_file = self.make_file(
            "GENOME", b">chr1\nACGT\n", sha256=digest,
            file_name="genome.fasta",
        )
        FileRelation.objects.create(
            file=data_file, related_type="assembly", related_id="123",
            related_code="test", file_role="genome_fasta",
        )
        manifest = self.write_manifest([("GENOME", "public", digest)])

        with self.assertRaises(CommandError):
            call_command("publish_datafiles", manifest=manifest, output_dir=self.report_dir)

        self.assertIn("fasta_index_missing", self.report_content("datafile_publication"))

    def test_token_issue_dry_run_does_not_create_token(self):
        stdout = StringIO()
        call_command(
            "issue_data_access_token", name="GeneScreen", scope=["file:read"], stdout=stdout,
        )
        self.assertEqual(DataAccessToken.objects.count(), 0)
        self.assertIn("ready_no_token_issued", stdout.getvalue())

    def test_token_issue_list_and_revoke_lifecycle(self):
        issue_output = StringIO()
        call_command(
            "issue_data_access_token", "--name", "GeneScreen",
            "--scope", "file:read", "--scope", "metadata:read", expires_in_hours=24,
            created_by=self.user.username, apply=True, stdout=issue_output,
        )
        token = DataAccessToken.objects.get()
        raw_token = next(
            line.split("\t", 1)[1]
            for line in issue_output.getvalue().splitlines()
            if line.startswith("token\t")
        )
        self.assertTrue(raw_token.startswith(f"gdt_{token.token_prefix}_"))
        self.assertNotEqual(token.token_hash, raw_token)
        self.assertIsNotNone(DataAccessToken.authenticate(raw_token))

        list_output = StringIO()
        call_command("list_data_access_tokens", stdout=list_output)
        listing = list_output.getvalue()
        self.assertIn("GeneScreen", listing)
        self.assertNotIn(raw_token, listing)
        self.assertNotIn(token.token_hash, listing)

        dry_revoke = StringIO()
        call_command("revoke_data_access_token", token_prefix=token.token_prefix, stdout=dry_revoke)
        token.refresh_from_db()
        self.assertIsNone(token.revoked_at)
        self.assertIn("ready_to_revoke", dry_revoke.getvalue())

        call_command("revoke_data_access_token", token_prefix=token.token_prefix, apply=True)
        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)
        self.assertIsNone(DataAccessToken.authenticate(raw_token))

        active_only = StringIO()
        call_command("list_data_access_tokens", stdout=active_only)
        self.assertNotIn("GeneScreen", active_only.getvalue())
        all_tokens = StringIO()
        call_command("list_data_access_tokens", include_inactive=True, stdout=all_tokens)
        self.assertIn("revoked", all_tokens.getvalue())
