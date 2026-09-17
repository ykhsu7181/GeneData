from django.test import TestCase

from files.models import Accession, Assembly, Species


class AssemblyListApiTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
            common_name="rice",
            taxonomy_id="4530",
        )
        self.other_species = Species.objects.create(
            species_code="ORYZA_GLUMAEPATULA",
            scientific_name="Oryza glumaepatula",
            taxonomy_id="40149",
        )
        self.ir64 = Accession.objects.create(
            accession="IR64",
            species=self.species,
            sub_population="XI",
        )
        self.o2428 = Accession.objects.create(
            accession="02428",
            species=self.species,
            sub_population="GJ",
        )
        self.other_accession = Accession.objects.create(
            accession="OG-001",
            species=self.other_species,
        )
        self.ir64_assembly = Assembly.objects.create(
            accession=self.ir64,
            name="v2-polish",
            display_name="IR64 polished assembly",
            assembly_code="ASM_IR64_V2",
            assembly_name="IR64 v2 polished",
            assembly_accession="GCA_013265735.1",
            standard_id="ASM-IR64-STANDARD",
            assembly_level="Chromosome",
            is_default=True,
        )
        self.o2428_assembly = Assembly.objects.create(
            accession=self.o2428,
            name="default",
            assembly_code="ASM_02428_DEFAULT",
            assembly_name="02428 default",
            assembly_accession=None,
            assembly_level=None,
            is_default=True,
        )
        self.other_assembly = Assembly.objects.create(
            accession=self.other_accession,
            name="wild-default",
            assembly_code="ASM_OG_DEFAULT",
            assembly_name="wild rice assembly",
            assembly_accession="GCA_WILD_001",
            species_code="OG_MANIFEST",
            assembly_level="Scaffold",
        )

    def test_list_returns_lightweight_paginated_payload(self):
        response = self.client.get("/gd/api/files/assemblies/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 20)
        self.assertIn("results", payload)

        first = payload["results"][0]
        self.assertEqual(
            set(first.keys()),
            {
                "id",
                "accession",
                "accession_id",
                "assembly",
                "assembly_accession",
                "assembly_level",
                "species",
                "taxon_id",
                "is_default",
            },
        )
        self.assertNotIn("annotations", first)
        self.assertNotIn("files", first)

    def test_search_matches_accession_assembly_accession_and_species(self):
        by_accession = self.client.get("/gd/api/files/assemblies/", {"search": "IR64"}).json()
        self.assertEqual(by_accession["count"], 1)
        self.assertEqual(by_accession["results"][0]["id"], self.ir64_assembly.id)

        by_assembly_accession = self.client.get(
            "/gd/api/files/assemblies/",
            {"search": "GCA_013265735"},
        ).json()
        self.assertEqual(by_assembly_accession["count"], 1)
        self.assertEqual(by_assembly_accession["results"][0]["accession"], "IR64")

        by_species = self.client.get("/gd/api/files/assemblies/", {"search": "glumaepatula"}).json()
        self.assertEqual(by_species["count"], 1)
        self.assertEqual(by_species["results"][0]["id"], self.other_assembly.id)

    def test_search_matches_name_code_standard_id_and_level(self):
        by_name = self.client.get("/gd/api/files/assemblies/", {"search": "polished"}).json()
        self.assertEqual(by_name["count"], 1)
        self.assertEqual(by_name["results"][0]["assembly"], "IR64 polished assembly")

        by_code = self.client.get("/gd/api/files/assemblies/", {"search": "ASM_02428"}).json()
        self.assertEqual(by_code["count"], 1)
        self.assertEqual(by_code["results"][0]["accession"], "02428")

        by_standard_id = self.client.get(
            "/gd/api/files/assemblies/",
            {"search": "ASM-IR64-STANDARD"},
        ).json()
        self.assertEqual(by_standard_id["count"], 1)
        self.assertEqual(by_standard_id["results"][0]["id"], self.ir64_assembly.id)

        by_level = self.client.get("/gd/api/files/assemblies/", {"search": "Scaffold"}).json()
        self.assertEqual(by_level["count"], 1)
        self.assertEqual(by_level["results"][0]["id"], self.other_assembly.id)

    def test_q_alias_is_supported_for_search(self):
        response = self.client.get("/gd/api/files/assemblies/", {"q": "02428"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["accession"], "02428")

    def test_pagination_clamps_page_size_and_preserves_summary_endpoint(self):
        for index in range(21):
            accession = Accession.objects.create(
                accession=f"PAGE-{index:02d}",
                species=self.species,
            )
            Assembly.objects.create(
                accession=accession,
                name="default",
                assembly_code=f"ASM_PAGE_{index:02d}",
            )

        response = self.client.get(
            "/gd/api/files/assemblies/",
            {"page": 2, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 24)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["page_size"], 10)
        self.assertEqual(len(payload["results"]), 10)
        self.assertEqual(payload["previous"], 1)
        self.assertEqual(payload["next"], 3)

        summary = self.client.get(f"/gd/api/files/assemblies/{self.ir64_assembly.id}/summary/")
        self.assertEqual(summary.status_code, 200)
        self.assertTrue(summary.json()["success"])
