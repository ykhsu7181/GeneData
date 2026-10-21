import hashlib
import tempfile
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataAccessToken,
    DataFile,
    Dataset,
    FileRelation,
)


class ExternalAccessionFilesApiV1Tests(TestCase):
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
        self.other_accession = Accession.objects.create(accession="OTHER")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64-v1",
            assembly_code="IR64_V1",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            accession=self.accession,
            assembly=self.assembly,
            name="IR64 annotation",
            annotation_code="IR64_ANN",
            is_default=True,
        )
        self.public_dataset = Dataset.objects.create(
            dataset_code="DS_IR64",
            bioproject_accession="PRJEB73710",
            visibility="public",
            status="released",
        )

        self.genome = self.make_file(
            "GENOME", "genome.IR64.fasta", "accession", self.accession.id,
            "genome", dataset=self.public_dataset,
        )
        self.index = self.make_file(
            "INDEX", "genome.IR64.fasta.fai", "assembly", self.assembly.id,
            "genome_index",
        )
        self.gff = self.make_file(
            "GFF", "annotation.IR64.gff", "annotation", self.annotation.id,
            "annotation",
        )

    def make_file(
        self,
        code,
        file_name,
        related_type,
        related_id,
        role,
        *,
        dataset=None,
        access_level=DataFile.ACCESS_LEVEL_PUBLIC,
        publication_status=DataFile.PUBLICATION_RELEASED,
    ):
        content = f"content:{code}".encode("ascii")
        path = self.root / file_name
        path.write_bytes(content)
        data_file = DataFile.objects.create(
            file_code=code,
            file_name=file_name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            dataset=dataset,
            access_level=access_level,
            publication_status=publication_status,
            published_at=timezone.now(),
            is_current=True,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=True,
        )
        return data_file

    @staticmethod
    def bearer(raw_token):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token}"}

    def test_anonymous_discovery_includes_accession_assembly_and_annotation_files(self):
        response = self.client.get("/gd/api/v1/accessions/IR64/files/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accession"], "IR64")
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            {item["file_code"] for item in payload["results"]},
            {"GENOME", "INDEX", "GFF"},
        )
        self.assertNotIn("file_path", str(payload))
        genome = next(item for item in payload["results"] if item["file_code"] == "GENOME")
        self.assertEqual(genome["dataset"], "DS_IR64")
        self.assertEqual(genome["content_url"], f"/gd/api/v1/files/{self.genome.id}/content/")

    def test_filters_match_role_category_dataset_and_format(self):
        cases = (
            ("role=genome", {"GENOME"}),
            ("category=annotation", {"GFF"}),
            ("dataset=DS_IR64", {"GENOME"}),
            ("dataset=prjeb73710", {"GENOME"}),
            ("format=fasta", {"GENOME"}),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                response = self.client.get(f"/gd/api/v1/accessions/IR64/files/?{query}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {item["file_code"] for item in response.json()["results"]},
                    expected,
                )

    def test_unreleased_missing_and_other_accession_files_are_excluded(self):
        self.make_file(
            "DRAFT", "draft.bed", "accession", self.accession.id, "other",
            publication_status=DataFile.PUBLICATION_DRAFT,
        )
        missing = self.make_file(
            "MISSING", "missing.bed", "accession", self.accession.id, "other"
        )
        Path(missing.file_path).unlink()
        self.make_file(
            "OTHER", "other.fasta", "accession", self.other_accession.id, "genome"
        )

        response = self.client.get("/gd/api/v1/accessions/IR64/files/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_internal_file_is_visible_only_to_internal_metadata_token(self):
        internal_dataset = Dataset.objects.create(
            dataset_code="DS_INTERNAL",
            visibility="lab_internal",
            status="released",
        )
        self.make_file(
            "INTERNAL", "internal.bed", "accession", self.accession.id, "other",
            dataset=internal_dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
        )
        _public, public_raw = DataAccessToken.issue(
            name="public-metadata",
            scopes=[DataAccessToken.SCOPE_METADATA_READ],
        )
        _internal, internal_raw = DataAccessToken.issue(
            name="internal-metadata",
            scopes=[DataAccessToken.SCOPE_METADATA_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        anonymous = self.client.get("/gd/api/v1/accessions/IR64/files/")
        public = self.client.get(
            "/gd/api/v1/accessions/IR64/files/", **self.bearer(public_raw)
        )
        internal = self.client.get(
            "/gd/api/v1/accessions/IR64/files/", **self.bearer(internal_raw)
        )

        self.assertEqual(anonymous.json()["count"], 3)
        self.assertEqual(public.json()["count"], 3)
        self.assertEqual(internal.json()["count"], 4)

    def test_pagination_and_invalid_query_contract(self):
        page = self.client.get(
            "/gd/api/v1/accessions/IR64/files/?page=2&page_size=2"
        )
        invalid = self.client.get(
            "/gd/api/v1/accessions/IR64/files/?page=zero"
        )
        missing = self.client.get(
            "/gd/api/v1/accessions/UNKNOWN/files/"
        )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["count"], 3)
        self.assertEqual(len(page.json()["results"]), 1)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], "invalid_query")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["code"], "not_found")
