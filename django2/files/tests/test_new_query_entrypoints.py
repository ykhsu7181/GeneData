import os
import tempfile
import uuid

from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, Species


class NewQueryEntrypointsTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.suffix}"
        self.file_type = FileType.objects.create(
            name=f"QUERY_{self.suffix}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(
            accession=self.accession_code,
            sub_population="XI",
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="default-annotation",
            standard_id=f"ANN_{self.suffix}",
            is_default=True,
        )

    def create_data_file(self, code_suffix, filename, content=b">chr1\nATGC\n"):
        file_path = os.path.join(self.temp_dir.name, filename)
        with open(file_path, "wb") as handle:
            handle.write(content)
        return DataFile.objects.create(
            file_code=f"QRY{self.suffix}{code_suffix}",
            file_type=self.file_type,
            file_name=filename,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )

    def add_relation(self, data_file, related_type, related_id, file_role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=self.accession_code,
            file_role=file_role,
        )

    def test_query_organisms_endpoint_returns_accession_codes(self):
        response = self.client.get("/gd/api/files/query/organisms/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.accession_code, response.json())

    def test_query_sub_populations_endpoint_returns_distinct_values(self):
        response = self.client.get("/gd/api/files/query/sub-populations/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("XI", response.json())

    def test_query_paginated_overview_endpoint_returns_new_relation_rows(self):
        genome_file = self.create_data_file("A", f"genome.{self.accession_code}.fasta")
        self.add_relation(genome_file, "accession", self.accession.id, "genome")

        response = self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": self.accession_code},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["genome"]["id"], genome_file.id)
        self.assertEqual(payload["results"][0]["genome"]["source"], "new_relation")

    def test_query_paginated_overview_supports_species_search(self):
        self.accession.species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession.save(update_fields=["species"])

        response = self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": "水稻"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["accession"], self.accession_code)

    def test_query_supplementary_data_includes_region_and_country(self):
        self.accession.country = "China"
        self.accession.region = "Yunnan"
        self.accession.longitude = 102.71
        self.accession.latitude = 25.04
        self.accession.save(update_fields=["country", "region", "longitude", "latitude"])

        response = self.client.get("/gd/api/files/query/supplementary-data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[self.accession_code]["country"], "China")
        self.assertEqual(payload[self.accession_code]["region"], "Yunnan")


class FrontendUsesNewQueryEntrypointsTestCase(TestCase):
    def test_business_views_no_longer_reference_legacy_genomefile_query_urls(self):
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        views_dir = os.path.join(repo_root, "vue_project", "src", "views")
        legacy_hits = []

        for filename in os.listdir(views_dir):
            if not filename.endswith(".vue"):
                continue
            if filename.startswith("Admin"):
                continue

            path = os.path.join(views_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

            if "/files/genome-files/" in content:
                legacy_hits.append(filename)

        self.assertEqual(legacy_hits, [])
