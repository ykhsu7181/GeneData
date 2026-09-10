import uuid

from django.test import TestCase

from files.models import Accession, Annotation, Assembly


class QueryContextAmbiguityTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8].upper()
        self.accession = Accession.objects.create(accession=f"AMB_{suffix}")
        Assembly.objects.create(accession=self.accession, name="one")
        Assembly.objects.create(accession=self.accession, name="two")

    def assert_ambiguous(self, response):
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["code"], "ambiguous_context")
        self.assertEqual(payload["related_type"], "assembly")
        self.assertEqual(payload["parent"], self.accession.accession)

    def test_chromosome_query_does_not_guess_first_assembly(self):
        response = self.client.get(
            "/gd/api/files/query/chromosomes/",
            {"accession": self.accession.accession},
        )

        self.assert_ambiguous(response)

    def test_transcriptome_download_does_not_guess_first_assembly(self):
        response = self.client.get(
            "/gd/api/files/query/download-transcriptome/",
            {"accession": self.accession.accession, "type": "root"},
        )

        self.assert_ambiguous(response)

    def test_paginated_overview_reports_ambiguous_context(self):
        response = self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": self.accession.accession},
        )

        self.assert_ambiguous(response)

    def test_data_overview_reports_ambiguous_context(self):
        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"search": self.accession.accession},
        )

        self.assert_ambiguous(response)

    def test_accession_detail_exposes_ambiguity_without_guessing(self):
        response = self.client.get(
            f"/gd/api/files/accessions/{self.accession.accession}/"
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["data"]["summary"]
        self.assertEqual(summary["context_status"], "ambiguous")
        self.assertEqual(summary["context_error"]["related_type"], "assembly")
        self.assertIsNone(summary["default_assembly_id"])

    def test_annotation_query_reports_ambiguous_annotation_context(self):
        resolved_accession = Accession.objects.create(
            accession=f"ANN_{uuid.uuid4().hex[:8].upper()}"
        )
        assembly = Assembly.objects.create(
            accession=resolved_accession,
            name="only",
        )
        Annotation.objects.create(
            assembly=assembly,
            accession=resolved_accession,
            name="one",
        )
        Annotation.objects.create(
            assembly=assembly,
            accession=resolved_accession,
            name="two",
        )

        response = self.client.get(
            "/gd/api/files/query/annotation-data/",
            {"assembly_id": assembly.id},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["related_type"], "annotation")
