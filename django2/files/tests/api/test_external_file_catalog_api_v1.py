import hashlib
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
    DatasetAccession,
    FileRelation,
)


class ExternalFileCatalogApiV1Tests(TestCase):
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

        self.ir64 = Accession.objects.create(accession="IR64")
        self.nipponbare = Accession.objects.create(accession="Nipponbare")
        self.ir64_assembly = Assembly.objects.create(
            accession=self.ir64,
            name="IR64 reference",
            assembly_code="ASM_IR64",
            assembly_accession="GCA_IR64",
        )
        self.nipponbare_assembly = Assembly.objects.create(
            accession=self.nipponbare,
            name="Nipponbare reference",
            assembly_code="ASM_NIPPONBARE",
        )
        self.ir64_dataset = Dataset.objects.create(
            dataset_code="DS_IR64",
            bioproject_accession="PRJ_IR64",
            visibility="public",
            status="released",
        )
        DatasetAccession.objects.create(
            dataset=self.ir64_dataset,
            accession=self.ir64,
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
        publication_status=DataFile.PUBLICATION_RELEASED,
        exists=True,
    ):
        path = self.root / code / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f">{code}\nACGT\n".encode()
        if exists:
            path.write_bytes(content)
        data_file = DataFile.objects.create(
            file_code=code,
            dataset=dataset,
            file_name=file_name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            access_level=access_level,
            publication_status=publication_status,
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
        return data_file

    def test_duplicate_file_name_returns_all_authorized_candidates(self):
        first = self.make_file(
            "FILE000101",
            "genome.fasta",
            accession=self.ir64,
            assembly=self.ir64_assembly,
            dataset=self.ir64_dataset,
        )
        second = self.make_file(
            "FILE000205",
            "genome.fasta",
            accession=self.nipponbare,
            assembly=self.nipponbare_assembly,
        )
        self.make_file(
            "FILE_INTERNAL",
            "genome.fasta",
            accession=self.ir64,
            access_level=DataFile.ACCESS_LEVEL_INTERNAL,
        )

        response = self.client.get(
            "/gd/api/v1/files/",
            {"file_name": "  GENOME.FASTA  "},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            {item["file_code"] for item in payload["results"]},
            {first.file_code, second.file_code},
        )
        self.assertEqual(
            {item["accession"] for item in payload["results"]},
            {"IR64", "Nipponbare"},
        )
        self.assertNotIn("FILE_INTERNAL", str(payload))
        self.assertNotIn(str(self.root), str(payload))
        for item in payload["results"]:
            self.assertEqual(
                item["content_url"],
                f'/gd/api/v1/files/{item["file_code"]}/content/',
            )

    def test_combined_context_filters_select_one_duplicate_candidate(self):
        selected = self.make_file(
            "FILE000301",
            "genome.fasta",
            accession=self.ir64,
            assembly=self.ir64_assembly,
            dataset=self.ir64_dataset,
            role="genome_fasta",
        )
        self.make_file(
            "FILE000302",
            "genome.fasta",
            accession=self.nipponbare,
            assembly=self.nipponbare_assembly,
        )

        response = self.client.get(
            "/gd/api/v1/files/",
            {
                "file_name": "genome.fasta",
                "accession": "IR64",
                "assembly": "GCA_IR64",
                "dataset": "PRJ_IR64",
                "role": "genome_fasta",
                "format": "FASTA",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["file_code"], selected.file_code)
        self.assertEqual(payload["results"][0]["assemblies"], ["ASM_IR64"])
        self.assertEqual(payload["results"][0]["datasets"], ["DS_IR64"])

    def test_special_file_name_and_name_contains_are_safe(self):
        expected = self.make_file(
            "FILE000401",
            "annotation.2037(Rajahamsal).gff",
            accession=self.ir64,
            role="annotation_gff3",
        )

        exact = self.client.get(
            "/gd/api/v1/files/",
            {"file_name": "annotation.2037(Rajahamsal).gff"},
        )
        partial = self.client.get(
            "/gd/api/v1/files/",
            {"name_contains": "2037(rajahamsal)"},
        )
        traversal = self.client.get(
            "/gd/api/v1/files/",
            {"file_name": "../../settings.py"},
        )

        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.json()["results"][0]["file_code"], expected.file_code)
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial.json()["count"], 1)
        self.assertEqual(traversal.status_code, 200)
        self.assertEqual(traversal.json()["count"], 0)

    def test_catalog_excludes_draft_and_missing_files_and_validates_pagination(self):
        ready = self.make_file("FILE_READY", "ready.fasta")
        self.make_file(
            "FILE_DRAFT",
            "draft.fasta",
            publication_status=DataFile.PUBLICATION_DRAFT,
        )
        self.make_file("FILE_MISSING", "missing.fasta", exists=False)

        response = self.client.get("/gd/api/v1/files/", {"page_size": 1})
        invalid = self.client.get("/gd/api/v1/files/", {"page": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["file_code"], ready.file_code)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], "invalid_query")

    def test_internal_candidate_requires_internal_metadata_token(self):
        internal = self.make_file(
            "FILE_INTERNAL_ONLY",
            "internal.fasta",
            access_level=DataFile.ACCESS_LEVEL_INTERNAL,
        )
        _token, raw_token = DataAccessToken.issue(
            name="internal-catalog",
            scopes=[DataAccessToken.SCOPE_METADATA_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        anonymous = self.client.get(
            "/gd/api/v1/files/", {"file_name": "internal.fasta"}
        )
        authorized = self.client.get(
            "/gd/api/v1/files/",
            {"file_name": "internal.fasta"},
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )

        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous.json()["count"], 0)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json()["count"], 1)
        self.assertEqual(
            authorized.json()["results"][0]["file_code"],
            internal.file_code,
        )

    def test_public_catalog_manifest_is_excel_friendly_and_fail_closed(self):
        visible = self.make_file(
            "FILE_MANIFEST",
            "annotation.IR64.gff",
            accession=self.ir64,
            assembly=self.ir64_assembly,
            role="annotation",
        )
        self.make_file(
            "FILE_MANIFEST_DRAFT",
            "draft.gff",
            publication_status=DataFile.PUBLICATION_DRAFT,
            role="annotation",
        )

        response = self.client.get("/gd/api/v1/files/manifest.tsv")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-File-Count"], "1")
        self.assertIn("genedata_public_files.tsv", response["Content-Disposition"])
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("file_code\tfile_name\taccession\tassembly"))
        self.assertIn(visible.file_code, text)
        self.assertIn("annotation.IR64.gff", text)
        self.assertIn("/gd/api/v1/files/FILE_MANIFEST/content/", text)
        self.assertNotIn("FILE_MANIFEST_DRAFT", text)
        self.assertNotIn(str(self.root), text)
