from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from files.dashboard_views import DASHBOARD_CACHE_KEY
from files.models import Accession, Annotation, Assembly, Species


class DashboardApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
            common_name="Rice",
        )
        self.rice = Accession.objects.create(species=self.species, accession="IR64")
        self.maize = Accession.objects.create(accession="B73")
        self.rice_assembly = Assembly.objects.create(
            accession=self.rice,
            name="rice-default",
            display_name="IRGSP-1.0",
            is_default=True,
        )
        Annotation.objects.create(
            assembly=self.rice_assembly,
            name="rice-annotation",
            annotation_version="v1.0",
            is_default=True,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @override_settings(DASHBOARD_FEATURED_ACCESSIONS=())
    def test_dashboard_returns_only_portal_fields(self):
        response = self.client.get("/gd/api/warehouse/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload), {"summary", "featured_accessions"})
        self.assertEqual(
            payload["summary"],
            {
                "assembly_count": 1,
                "species_count": 1,
                "annotation_count": 1,
                "accession_count": 2,
            },
        )
        self.assertEqual(payload["featured_accessions"], [])

    def test_dashboard_returns_configured_featured_accessions_in_order(self):
        configured_codes = ("B73", "MISSING", "IR64", "IR64")

        with override_settings(DASHBOARD_FEATURED_ACCESSIONS=configured_codes):
            response = self.client.get("/gd/api/warehouse/dashboard/")

        featured = response.json()["featured_accessions"]
        self.assertEqual([item["accession"] for item in featured], ["B73", "IR64"])
        self.assertEqual(featured[0]["assembly"], "-")
        self.assertEqual(featured[0]["annotation"], "-")
        self.assertEqual(featured[1]["species_scientific_name"], "Oryza sativa")
        self.assertEqual(featured[1]["species_common_name"], "Rice")
        self.assertEqual(featured[1]["assembly"], "IRGSP-1.0")
        self.assertEqual(featured[1]["annotation"], "v1.0")

    def test_featured_accessions_fall_back_to_first_related_records(self):
        assembly = Assembly.objects.create(
            accession=self.maize,
            name="B73 RefGen_v4",
            is_default=False,
        )
        Annotation.objects.create(
            assembly=assembly,
            name="maize-annotation",
            release_version="v4.1",
            is_default=False,
        )

        with override_settings(DASHBOARD_FEATURED_ACCESSIONS=("B73",)):
            response = self.client.get("/gd/api/warehouse/dashboard/")

        featured = response.json()["featured_accessions"]
        self.assertEqual(featured[0]["assembly"], "B73 RefGen_v4")
        self.assertEqual(featured[0]["annotation"], "v4.1")

    def test_refresh_dashboard_cache_command_uses_v2_payload(self):
        self.assertEqual(DASHBOARD_CACHE_KEY, "warehouse_dashboard_payload_v2")

        call_command("refresh_dashboard_cache")
        payload = cache.get(DASHBOARD_CACHE_KEY)

        self.assertEqual(set(payload), {"summary", "featured_accessions"})
        self.assertEqual(payload["summary"]["accession_count"], 2)
