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

    def test_query_organisms_supports_species_and_subpopulation_search(self):
        species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            scientific_name=f"Oryza sativa {self.suffix}",
            chinese_name=f"水稻{self.suffix}",
            common_name=f"Rice {self.suffix}",
        )
        self.accession.species = species
        self.accession.save(update_fields=["species"])

        for term in (
            species.species_code,
            species.scientific_name,
            species.chinese_name,
            species.common_name,
            "XI",
        ):
            with self.subTest(term=term):
                response = self.client.get(
                    "/gd/api/files/query/organisms/",
                    {"search": term},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(self.accession_code, response.json())

    def test_query_organisms_ranks_exact_prefix_contains_then_metadata(self):
        search = f"RANK{self.suffix}"
        exact = Accession.objects.create(accession=search)
        prefix = Accession.objects.create(accession=f"{search}_PREFIX")
        contains = Accession.objects.create(accession=f"X_{search}_CONTAINS")
        species = Species.objects.create(
            species_code=f"SPECIES_{self.suffix}",
            common_name=search,
        )
        metadata = Accession.objects.create(
            accession=f"ZZ_METADATA_{self.suffix}",
            species=species,
        )

        response = self.client.get(
            "/gd/api/files/query/organisms/",
            {"search": search},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [exact.accession, prefix.accession, contains.accession, metadata.accession],
        )

    def test_query_organisms_applies_default_and_maximum_limits(self):
        search = f"LIMIT{self.suffix}"
        Accession.objects.bulk_create(
            [Accession(accession=f"{search}_{index:02d}") for index in range(55)]
        )

        default_response = self.client.get(
            "/gd/api/files/query/organisms/",
            {"search": search},
        )
        capped_response = self.client.get(
            "/gd/api/files/query/organisms/",
            {"search": search, "limit": 500},
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(len(default_response.json()), 20)
        self.assertEqual(capped_response.status_code, 200)
        self.assertEqual(len(capped_response.json()), 50)

    def test_query_organisms_rejects_invalid_search_and_limit(self):
        too_long = self.client.get(
            "/gd/api/files/query/organisms/",
            {"search": "x" * 101},
        )
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(too_long.json()["code"], "invalid_search")

        for limit in ("invalid", "0", "-1"):
            with self.subTest(limit=limit):
                response = self.client.get(
                    "/gd/api/files/query/organisms/",
                    {"search": self.accession_code, "limit": limit},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["code"], "invalid_limit")

    def test_query_organisms_trims_search_and_keeps_no_search_compatibility(self):
        searched = self.client.get(
            "/gd/api/files/query/organisms/",
            {"search": f"  {self.accession_code}  "},
        )
        unfiltered = self.client.get(
            "/gd/api/files/query/organisms/",
            {"limit": 1},
        )

        self.assertEqual(searched.status_code, 200)
        self.assertEqual(searched.json(), [self.accession_code])
        self.assertEqual(unfiltered.status_code, 200)
        self.assertIn(self.accession_code, unfiltered.json())

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
        species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            scientific_name="Oryza sativa",
            chinese_name="水稻",
            common_name="Rice",
        )
        self.accession.species = species
        self.accession.country = "China"
        self.accession.region = "Yunnan"
        self.accession.longitude = 102.71
        self.accession.latitude = 25.04
        self.accession.save(update_fields=["species", "country", "region", "longitude", "latitude"])

        response = self.client.get("/gd/api/files/query/supplementary-data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[self.accession_code]["country"], "China")
        self.assertEqual(payload[self.accession_code]["region"], "Yunnan")
        self.assertEqual(payload[self.accession_code]["species_code"], species.species_code)
        self.assertEqual(payload[self.accession_code]["scientific_name"], "Oryza sativa")
        self.assertEqual(payload[self.accession_code]["chinese_name"], "水稻")
        self.assertEqual(payload[self.accession_code]["common_name"], "Rice")

    def test_query_supplementary_data_handles_missing_species(self):
        response = self.client.get("/gd/api/files/query/supplementary-data/")

        self.assertEqual(response.status_code, 200)
        item = response.json()[self.accession_code]
        self.assertIsNone(item["species_code"])
        self.assertIsNone(item["scientific_name"])
        self.assertIsNone(item["chinese_name"])
        self.assertIsNone(item["common_name"])

    def test_query_supplementary_data_fetches_species_in_one_query(self):
        species = Species.objects.create(
            species_code=f"QUERY_COUNT_{self.suffix}",
            scientific_name="Query count species",
        )
        Accession.objects.bulk_create(
            [
                Accession(accession=f"QUERY_COUNT_{self.suffix}_{index}", species=species)
                for index in range(3)
            ]
        )

        with self.assertNumQueries(1):
            response = self.client.get("/gd/api/files/query/supplementary-data/")

        self.assertEqual(response.status_code, 200)


class FrontendUsesNewQueryEntrypointsTestCase(TestCase):
    def test_business_views_no_longer_reference_legacy_genomefile_query_urls(self):
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
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
