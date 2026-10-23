import hashlib
import json
import tempfile
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import (
    Accession,
    Assembly,
    DataAccessToken,
    DataFile,
    Dataset,
    ExternalFileBatch,
    FileRelation,
)


class ExternalFileBatchApiV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "protected"
        self.root.mkdir()
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            },
            GENEDATA_BATCH_MAX_SELECTORS=1000,
            GENEDATA_BATCH_MAX_FILES=1000,
            GENEDATA_BATCH_MAX_BYTES=500 * 1024 ** 3,
            GENEDATA_BATCH_TTL_HOURS=24,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.accession = Accession.objects.create(accession="IR64")
        self.other_accession = Accession.objects.create(accession="Nipponbare")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 reference",
            assembly_code="ASM_IR64",
            assembly_accession="GCA_IR64",
        )
        self.dataset = Dataset.objects.create(
            dataset_code="DS_IR64",
            bioproject_accession="PRJ_IR64",
            visibility="public",
            status="released",
        )
        self.token, self.raw_token = DataAccessToken.issue(
            name="batch-client",
            scopes=[DataAccessToken.SCOPE_BATCH_CREATE, DataAccessToken.SCOPE_BATCH_READ],
        )

    def make_file(
        self,
        code,
        file_name,
        *,
        accession=None,
        assembly=None,
        dataset=None,
        role="genome_fasta",
        access_level=DataFile.ACCESS_LEVEL_PUBLIC,
    ):
        content = f">{code}\nACGT\n".encode()
        path = self.root / code / file_name
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        data_file = DataFile.objects.create(
            file_code=code,
            dataset=dataset,
            file_name=file_name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            access_level=access_level,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
            is_current=True,
        )
        if accession:
            FileRelation.objects.create(
                file=data_file,
                related_type="accession",
                related_id=str(accession.id),
                file_role=role,
            )
        if assembly:
            FileRelation.objects.create(
                file=data_file,
                related_type="assembly",
                related_id=str(assembly.id),
                file_role=role,
                is_primary=True,
            )
        if dataset:
            FileRelation.objects.create(
                file=data_file,
                related_type="dataset",
                related_id=str(dataset.id),
                file_role=role,
            )
        if not any((accession, assembly, dataset)):
            FileRelation.objects.create(
                file=data_file,
                related_type="other",
                related_id="test",
                file_role=role,
            )
        return data_file

    def auth(self, raw_token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token or self.raw_token}"}

    def test_resolve_reports_duplicate_name_and_qualifier_selects_one(self):
        selected = self.make_file(
            "FILE_IR64", "genome.fasta", accession=self.accession, assembly=self.assembly,
            dataset=self.dataset,
        )
        self.make_file("FILE_OTHER", "genome.fasta", accession=self.other_accession)

        ambiguous = self.client.post(
            "/gd/api/v1/file-batches/resolve/",
            {"selectors": [{"file_name": "genome.fasta"}]},
            content_type="application/json",
            **self.auth(),
        )
        resolved = self.client.post(
            "/gd/api/v1/file-batches/resolve/",
            {"selectors": [{"file_name": "genome.fasta", "accession": "IR64"}]},
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(ambiguous.status_code, 200)
        self.assertEqual(ambiguous.json()["summary"]["ambiguous"], 1)
        self.assertEqual(len(ambiguous.json()["ambiguous"][0]["candidates"]), 2)
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["resolved"][0]["file_code"], selected.file_code)
        self.assertNotIn(str(self.root), str(ambiguous.json()))

    def test_business_selector_resolves_all_matching_roles_and_deduplicates(self):
        fasta = self.make_file(
            "FILE_FASTA", "genome.fasta", accession=self.accession, role="genome_fasta"
        )
        self.make_file("FILE_GFF", "genes.gff3", accession=self.accession, role="annotation_gff3")

        response = self.client.post(
            "/gd/api/v1/file-batches/resolve/",
            {"accessions": ["IR64"], "roles": ["genome_fasta"], "file_codes": [fasta.file_code]},
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["resolved"], 1)
        self.assertEqual(response.json()["resolved"][0]["file_code"], fasta.file_code)

    def test_strict_failure_creates_nothing_and_non_strict_persists_snapshot(self):
        data_file = self.make_file("FILE_READY", "ready.fasta", accession=self.accession)
        request = {"file_codes": [data_file.file_code, "FILE_MISSING"], "strict": True}

        strict = self.client.post(
            "/gd/api/v1/file-batches/",
            request,
            content_type="application/json",
            **self.auth(),
        )
        request["strict"] = False
        partial = self.client.post(
            "/gd/api/v1/file-batches/",
            request,
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(strict.status_code, 409)
        self.assertEqual(strict.json()["code"], "strict_resolution_failed")
        self.assertEqual(partial.status_code, 201)
        payload = partial.json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["files"][0]["file_code"], data_file.file_code)
        self.assertEqual(ExternalFileBatch.objects.count(), 1)

    def test_idempotency_replays_same_request_and_rejects_changed_request(self):
        first = self.make_file("FILE_ONE", "one.fasta")
        second = self.make_file("FILE_TWO", "two.fasta")
        headers = {**self.auth(), "HTTP_IDEMPOTENCY_KEY": "gene-screen-job-1"}

        created = self.client.post(
            "/gd/api/v1/file-batches/", {"file_codes": [first.file_code]},
            content_type="application/json", **headers,
        )
        replay = self.client.post(
            "/gd/api/v1/file-batches/", {"file_codes": [first.file_code]},
            content_type="application/json", **headers,
        )
        conflict = self.client.post(
            "/gd/api/v1/file-batches/", {"file_codes": [second.file_code]},
            content_type="application/json", **headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["batch_id"], created.json()["batch_id"])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "idempotency_conflict")
        self.assertEqual(ExternalFileBatch.objects.count(), 1)

    def test_json_and_tsv_manifest_use_snapshot_and_detect_source_change(self):
        data_file = self.make_file("FILE_MANIFEST", "manifest.fasta", accession=self.accession)
        created = self.client.post(
            "/gd/api/v1/file-batches/", {"file_codes": [data_file.file_code]},
            content_type="application/json", **self.auth(),
        ).json()
        json_response = self.client.get(created["manifest_url"], **self.auth())
        tsv_response = self.client.get(created["manifest_tsv_url"], **self.auth())

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()["snapshot_sha256"], created["snapshot_sha256"])
        canonical_files = json.dumps(
            json_response.json()["files"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.assertEqual(hashlib.sha256(canonical_files).hexdigest(), created["snapshot_sha256"])
        self.assertContains(tsv_response, "FILE_MANIFEST")
        self.assertEqual(tsv_response["X-Snapshot-SHA256"], created["snapshot_sha256"])
        self.assertNotIn(str(self.root), tsv_response.content.decode())

        data_file.sha256 = "f" * 64
        data_file.save(update_fields=["sha256"])
        stale = self.client.get(created["manifest_url"], **self.auth())
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["code"], "snapshot_stale")

    def test_batch_scope_owner_and_quota_are_enforced_without_leaking_internal_file(self):
        public = self.make_file("FILE_PUBLIC", "public.fasta")
        self.make_file(
            "FILE_INTERNAL", "internal.fasta", access_level=DataFile.ACCESS_LEVEL_INTERNAL
        )
        _wrong_token, wrong_raw = DataAccessToken.issue(
            name="metadata-only", scopes=[DataAccessToken.SCOPE_METADATA_READ]
        )
        denied = self.client.post(
            "/gd/api/v1/file-batches/resolve/", {"file_codes": [public.file_code]},
            content_type="application/json", **self.auth(wrong_raw),
        )
        hidden = self.client.post(
            "/gd/api/v1/file-batches/resolve/", {"file_codes": ["FILE_INTERNAL"]},
            content_type="application/json", **self.auth(),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["code"], "insufficient_scope")
        self.assertEqual(hidden.json()["missing"][0]["code"], "not_found")
        self.assertNotIn("internal.fasta", str(hidden.json()))

        with override_settings(GENEDATA_BATCH_MAX_FILES=0):
            quota = self.client.post(
                "/gd/api/v1/file-batches/", {"file_codes": [public.file_code]},
                content_type="application/json", **self.auth(),
            )
        self.assertEqual(quota.status_code, 413)
        self.assertEqual(quota.json()["code"], "batch_limit_exceeded")

        created = self.client.post(
            "/gd/api/v1/file-batches/", {"file_codes": [public.file_code]},
            content_type="application/json", **self.auth(),
        ).json()
        _other, other_raw = DataAccessToken.issue(
            name="other-client",
            scopes=[DataAccessToken.SCOPE_BATCH_CREATE, DataAccessToken.SCOPE_BATCH_READ],
        )
        isolated = self.client.get(created["manifest_url"], **self.auth(other_raw))
        self.assertEqual(isolated.status_code, 404)

    def test_new_batch_scopes_can_be_issued(self):
        self.assertEqual(
            set(self.token.scopes),
            {DataAccessToken.SCOPE_BATCH_CREATE, DataAccessToken.SCOPE_BATCH_READ},
        )
