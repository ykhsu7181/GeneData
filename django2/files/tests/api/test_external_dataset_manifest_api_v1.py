import csv
import hashlib
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import (
    Accession,
    Assembly,
    DataAccessToken,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
)


class ExternalDatasetManifestApiV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "protected"
        self.root.mkdir()
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 v1",
            assembly_code="IR64_V1",
            is_default=True,
        )
        self.dataset = Dataset.objects.create(
            dataset_code="DS_IR64",
            bioproject_accession="PRJEB73710",
            visibility="public",
            status="released",
        )
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
        )
        _token, self.raw_token = DataAccessToken.issue(
            name="manifest-test",
            scopes=[DataAccessToken.SCOPE_DATASET_MANIFEST],
        )

    def make_file(
        self,
        code,
        *,
        dataset=None,
        content=b"ACGT\n",
        access_level=DataFile.ACCESS_LEVEL_INHERITED,
        publication_status=DataFile.PUBLICATION_RELEASED,
        is_current=True,
    ):
        path = self.root / f"{code}.fasta"
        path.write_bytes(content)
        return DataFile.objects.create(
            file_code=code,
            dataset=dataset,
            file_name=path.name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            access_level=access_level,
            publication_status=publication_status,
            published_at=timezone.now(),
            is_current=is_current,
        )

    def add_relation(self, data_file, related_type, related_id, role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=True,
        )

    def bearer(self, raw_token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token or self.raw_token}"}

    def test_json_manifest_includes_direct_and_relation_owned_public_files(self):
        genome = self.make_file("GENOME", dataset=self.dataset)
        self.add_relation(genome, "accession", self.accession.id, "genome_fasta")
        index = self.make_file("INDEX")
        self.add_relation(index, "dataset", self.dataset.id, "genome_index")
        self.add_relation(index, "assembly", self.assembly.id, "genome_index")

        response = self.client.get(
            "/gd/api/v1/datasets/PRJEB73710/manifest/",
            **self.bearer(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dataset"], "PRJEB73710")
        self.assertEqual(payload["dataset_codes"], ["DS_IR64"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            {item["id"] for item in payload["files"]},
            {genome.id, index.id},
        )
        for item in payload["files"]:
            self.assertEqual(item["accession"], "IR64")
            self.assertEqual(item["accessions"], ["IR64"])
            self.assertTrue(item["content_url"].endswith("/content/"))
        self.assertNotIn("file_path", str(payload))
        self.assertNotIn(str(self.root), str(payload))

    def test_manifest_requires_bearer_token_with_dataset_scope(self):
        _token, wrong_scope = DataAccessToken.issue(
            name="metadata-only",
            scopes=[DataAccessToken.SCOPE_METADATA_READ],
        )

        anonymous = self.client.get(
            "/gd/api/v1/datasets/DS_IR64/manifest/"
        )
        forbidden = self.client.get(
            "/gd/api/v1/datasets/DS_IR64/manifest/",
            **self.bearer(wrong_scope),
        )

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous["WWW-Authenticate"], "Bearer")
        self.assertEqual(anonymous.json()["code"], "authentication_required")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["code"], "insufficient_scope")

    def test_manifest_excludes_unreleased_noncurrent_missing_and_nonpublic_files(self):
        released = self.make_file("RELEASED", dataset=self.dataset)
        self.add_relation(released, "accession", self.accession.id, "genome")
        draft = self.make_file(
            "DRAFT",
            dataset=self.dataset,
            publication_status=DataFile.PUBLICATION_DRAFT,
        )
        old = self.make_file("OLD", dataset=self.dataset, is_current=False)
        missing = self.make_file("MISSING", dataset=self.dataset)
        Path(missing.file_path).unlink()
        internal = self.make_file(
            "INTERNAL",
            dataset=self.dataset,
            access_level=DataFile.ACCESS_LEVEL_INTERNAL,
        )

        response = self.client.get(
            "/gd/api/v1/datasets/DS_IR64/manifest/",
            **self.bearer(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["files"][0]["id"], released.id)
        self.assertNotIn(draft.id, [item["id"] for item in response.json()["files"]])
        self.assertNotIn(old.id, [item["id"] for item in response.json()["files"]])
        self.assertNotIn(internal.id, [item["id"] for item in response.json()["files"]])

    def test_bioproject_aggregates_datasets_without_guessing_ambiguous_accession(self):
        second_accession = Accession.objects.create(accession="IR64-ALT")
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=second_accession,
        )
        other_dataset = Dataset.objects.create(
            dataset_code="DS_IR64_RNA",
            bioproject_accession="PRJEB73710",
            visibility="public",
            status="released",
        )
        DatasetAccession.objects.create(
            dataset=other_dataset,
            accession=second_accession,
        )
        ambiguous = self.make_file("AMBIGUOUS", dataset=self.dataset)
        rna = self.make_file("RNA", dataset=other_dataset)

        response = self.client.get(
            "/gd/api/v1/datasets/PRJEB73710/manifest/",
            **self.bearer(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dataset_codes"], ["DS_IR64", "DS_IR64_RNA"])
        ambiguous_row = next(item for item in payload["files"] if item["id"] == ambiguous.id)
        rna_row = next(item for item in payload["files"] if item["id"] == rna.id)
        self.assertIsNone(ambiguous_row["accession"])
        self.assertEqual(ambiguous_row["accessions"], ["IR64", "IR64-ALT"])
        self.assertEqual(rna_row["accession"], "IR64-ALT")

    def test_tsv_manifest_is_downloadable_and_uses_absolute_content_url(self):
        data_file = self.make_file("GENOME", dataset=self.dataset)
        self.add_relation(data_file, "accession", self.accession.id, "genome_fasta")

        response = self.client.get(
            "/gd/api/v1/datasets/DS_IR64/manifest.tsv",
            **self.bearer(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/tab-separated-values"))
        self.assertIn("DS_IR64.manifest.tsv", response["Content-Disposition"])
        rows = list(csv.DictReader(StringIO(response.content.decode()), dialect="excel-tab"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["accession"], "IR64")
        self.assertEqual(rows[0]["file_role"], "genome_fasta")
        self.assertEqual(
            rows[0]["url"],
            "http://testserver/gd/api/v1/files/GENOME/content/",
        )
        self.assertNotIn(str(self.root), response.content.decode())

    def test_private_draft_and_unknown_datasets_are_not_discoverable(self):
        Dataset.objects.create(
            dataset_code="PRIVATE",
            visibility="private",
            status="released",
        )
        Dataset.objects.create(
            dataset_code="DRAFT_DATASET",
            visibility="public",
            status="draft",
        )

        for identifier in ("PRIVATE", "DRAFT_DATASET", "UNKNOWN"):
            with self.subTest(identifier=identifier):
                response = self.client.get(
                    f"/gd/api/v1/datasets/{identifier}/manifest/",
                    **self.bearer(),
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["code"], "not_found")

    def test_manifest_requests_are_rate_limited_per_token(self):
        with patch(
            "files.api_v1.throttles.ExternalManifestThrottle.get_rate",
            return_value="2/minute",
        ):
            responses = [
                self.client.get(
                    "/gd/api/v1/datasets/DS_IR64/manifest/",
                    **self.bearer(),
                )
                for _index in range(3)
            ]

        self.assertEqual(
            [response.status_code for response in responses],
            [200, 200, 429],
        )
        self.assertIn("Retry-After", responses[-1])
        self.assertNotIn(self.raw_token, responses[-1].content.decode("utf-8"))
        self.assertNotIn(str(self.root), responses[-1].content.decode("utf-8"))
