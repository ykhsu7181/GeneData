from django.core.cache import cache
from django.test import TestCase

from files.dashboard_views import DASHBOARD_CACHE_KEY
from files.models import Accession, Assembly, Species


class AccessionPopularityApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA_POPULAR",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            accession="IR64-POPULAR",
            species=self.species,
            country="Philippines",
        )
        Assembly.objects.create(
            accession=self.accession,
            name="IR64 assembly",
            is_default=True,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_record_view_increments_count_and_invalidates_dashboard_cache(self):
        cache.set(DASHBOARD_CACHE_KEY, {"stale": True}, 60)

        first = self.client.post("/gd/api/files/accessions/IR64-POPULAR/views/")
        second = self.client.post("/gd/api/files/accessions/IR64-POPULAR/views/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["view_count"], 1)
        self.assertEqual(second.json()["view_count"], 2)
        self.accession.refresh_from_db()
        self.assertEqual(self.accession.view_count, 2)
        self.assertIsNotNone(self.accession.last_viewed_at)
        self.assertIsNone(cache.get(DASHBOARD_CACHE_KEY))

    def test_record_view_returns_404_for_unknown_accession(self):
        response = self.client.post("/gd/api/files/accessions/UNKNOWN/views/")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_popular_endpoint_orders_by_views_and_honors_bounded_limit(self):
        self.accession.view_count = 3
        self.accession.save(update_fields=["view_count"])
        more_popular = Accession.objects.create(accession="MOST-POPULAR", view_count=9)
        Accession.objects.create(accession="NEVER-VIEWED", view_count=0)

        response = self.client.get("/gd/api/files/accessions/popular/?limit=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["count"], 1)
        self.assertEqual([item["accession"] for item in payload["results"]], [more_popular.accession])
        self.assertEqual(payload["results"][0]["view_count"], 9)

    def test_popular_endpoint_uses_ten_as_the_maximum_limit(self):
        for index in range(12):
            Accession.objects.create(accession=f"POPULAR-{index:02d}", view_count=index + 1)

        response = self.client.get("/gd/api/files/accessions/popular/?limit=999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["limit"], 10)
        self.assertEqual(len(response.json()["results"]), 10)
