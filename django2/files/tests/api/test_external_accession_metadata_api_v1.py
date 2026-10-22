from django.core.cache import cache
from django.test import TestCase

from files.models import Accession, Assembly, Species


class ExternalAccessionMetadataApiV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
            common_name="rice",
        )
        self.accession = Accession.objects.create(
            accession="IR64",
            species=self.species,
            sub_population="indica",
            country="Philippines",
            region="Asia",
        )

    def test_accession_metadata_has_stable_external_contract(self):
        response = self.client.get("/gd/api/v1/accessions/IR64/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "accession": "IR64",
                "species": "Oryza sativa",
                "sub_population": "indica",
                "country": "Philippines",
                "region": "Asia",
            },
        )

    def test_accession_metadata_supports_missing_species(self):
        Accession.objects.create(accession="NO-SPECIES")

        response = self.client.get("/gd/api/v1/accessions/NO-SPECIES/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["species"])

    def test_assembly_list_excludes_placeholder_and_returns_all_real_versions(self):
        Assembly.objects.create(
            accession=self.accession,
            name="default",
            display_name="migration placeholder",
            assembly_code=None,
        )
        older = Assembly.objects.create(
            accession=self.accession,
            name="IR64 v1",
            assembly_code="IR64_V1",
            assembly_accession="GCA_000001",
            assembly_level="Chromosome",
        )
        current = Assembly.objects.create(
            accession=self.accession,
            name="IR64 v2",
            assembly_code="IR64_V2",
            assembly_name="IR64 curated v2",
            assembly_accession="GCA_000002",
            assembly_level="Chromosome",
            is_default=True,
        )

        response = self.client.get("/gd/api/v1/accessions/IR64/assemblies/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accession"], "IR64")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            [item["assembly_id"] for item in payload["assemblies"]],
            [current.id, older.id],
        )
        self.assertEqual(payload["assemblies"][0]["assembly_code"], "IR64_V2")
        self.assertEqual(
            payload["assemblies"][0]["assembly_name"], "IR64 curated v2"
        )

    def test_assembly_list_does_not_guess_a_selection_when_defaults_are_ambiguous(self):
        Assembly.objects.create(
            accession=self.accession,
            name="IR64 v1",
            assembly_code="IR64_V1",
            is_default=True,
        )
        Assembly.objects.create(
            accession=self.accession,
            name="IR64 v2",
            assembly_code="IR64_V2",
            is_default=True,
        )

        response = self.client.get("/gd/api/v1/accessions/IR64/assemblies/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertNotIn("selected_assembly_id", payload)

    def test_unknown_accession_uses_stable_not_found_contract(self):
        metadata = self.client.get("/gd/api/v1/accessions/UNKNOWN/")
        assemblies = self.client.get(
            "/gd/api/v1/accessions/UNKNOWN/assemblies/"
        )

        for response in (metadata, assemblies):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["code"], "not_found")
