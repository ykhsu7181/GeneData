from django.test import TestCase

from files.models import Accession, Assembly


class PlaceholderAssemblyVisibilityApiTestCase(TestCase):
    def setUp(self):
        self.accession = Accession.objects.create(accession="IR64")
        self.placeholder = Assembly.objects.create(
            accession=self.accession,
            name="default",
            display_name="IR64 migration placeholder",
            assembly_code=None,
            is_default=False,
        )
        self.real_assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 genome assembly",
            display_name="IR64 genome assembly",
            assembly_code="ASM_IR64",
            is_default=True,
        )

    def test_accession_summary_and_versions_hide_replaced_placeholder(self):
        summary = self.client.get("/gd/api/files/accessions/IR64/summary/")
        versions = self.client.get("/gd/api/files/accessions/IR64/assemblies/")
        legacy_detail = self.client.get("/gd/api/files/accessions/IR64/")

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(versions.status_code, 200)
        self.assertEqual(legacy_detail.status_code, 200)
        overview = summary.json()["data"]["relationship_overview"]["assemblies"]
        version_rows = versions.json()["data"]["results"]
        legacy_rows = legacy_detail.json()["data"]["assemblies"]
        self.assertEqual([item["id"] for item in overview], [self.real_assembly.id])
        self.assertEqual([item["id"] for item in version_rows], [self.real_assembly.id])
        self.assertEqual([item["id"] for item in legacy_rows], [self.real_assembly.id])

    def test_homepage_overview_counts_only_visible_assemblies(self):
        response = self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": "IR64"},
        )

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["assembly_count"], 1)
        self.assertEqual(row["default_assembly_id"], self.real_assembly.id)

    def test_real_assembly_detail_hides_placeholder_and_placeholder_url_is_404(self):
        real_response = self.client.get(
            f"/gd/api/files/assemblies/{self.real_assembly.id}/summary/"
        )
        placeholder_response = self.client.get(
            f"/gd/api/files/assemblies/{self.placeholder.id}/summary/"
        )

        self.assertEqual(real_response.status_code, 200)
        related = real_response.json()["data"]["related_assemblies"]
        self.assertEqual([item["id"] for item in related], [self.real_assembly.id])
        self.assertEqual(placeholder_response.status_code, 404)

    def test_coded_default_name_is_not_treated_as_placeholder(self):
        coded_accession = Accession.objects.create(accession="CODED-DEFAULT")
        coded_default = Assembly.objects.create(
            accession=coded_accession,
            name="default",
            assembly_code="ASM_IR64_LEGACY_NAMED",
            is_default=False,
        )

        response = self.client.get(
            "/gd/api/files/assemblies/",
            {"search": "ASM_IR64_LEGACY_NAMED"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], coded_default.id)
