import uuid

from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation


class QueryContextAmbiguityTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8].upper()
        self.suffix = suffix
        self.accession = Accession.objects.create(accession=f"AMB_{suffix}")
        self.first_assembly = Assembly.objects.create(accession=self.accession, name="one")
        self.second_assembly = Assembly.objects.create(accession=self.accession, name="two")

    def add_file_relation(self, *, related_type, related_id, file_role):
        data_file = DataFile.objects.create(
            file_code=f"{self.suffix}_{file_role}_{related_type}_{related_id}",
            file_name=f"{file_role}.{self.accession.accession}.txt",
            file_path=f"C:/stage-b-tests/{self.suffix}/{file_role}/{related_type}/{related_id}",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=self.accession.accession,
            file_role=file_role,
            is_primary=True,
        )
        return data_file

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

    def test_explicit_assembly_does_not_use_accession_genome_relation(self):
        self.add_file_relation(
            related_type="accession",
            related_id=self.accession.id,
            file_role="genome",
        )

        response = self.client.get(
            "/gd/api/files/query/chromosomes/",
            {"assembly_id": self.first_assembly.id},
        )

        self.assertEqual(response.status_code, 404)

    def test_explicit_assembly_does_not_use_accession_interval_relation(self):
        self.add_file_relation(
            related_type="accession",
            related_id=self.accession.id,
            file_role="centromere",
        )

        response = self.client.get(
            "/gd/api/files/query/centromere/",
            {"assembly_id": self.first_assembly.id},
        )

        self.assertEqual(response.status_code, 404)

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

    def test_data_overview_does_not_require_a_default_assembly(self):
        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"search": self.accession.accession},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

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

    def test_accession_detail_keeps_assembly_when_only_annotation_is_ambiguous(self):
        resolved_accession = Accession.objects.create(
            accession=f"DETAIL_{uuid.uuid4().hex[:8].upper()}"
        )
        assembly = Assembly.objects.create(
            accession=resolved_accession,
            name="only",
        )
        for name in ("one", "two"):
            Annotation.objects.create(
                assembly=assembly,
                accession=resolved_accession,
                name=name,
            )
        genome_file = DataFile.objects.create(
            file_code=f"{self.suffix}_detail_genome",
            file_name=f"genome.{resolved_accession.accession}.fasta",
            file_path=f"C:/stage-b-tests/{self.suffix}/detail/genome.fasta",
        )
        FileRelation.objects.create(
            file=genome_file,
            related_type="assembly",
            related_id=str(assembly.id),
            related_code=resolved_accession.accession,
            file_role="genome",
            is_primary=True,
        )

        response = self.client.get(
            f"/gd/api/files/accessions/{resolved_accession.accession}/"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["summary"]["context_status"], "ambiguous")
        self.assertEqual(payload["summary"]["context_error"]["related_type"], "annotation")
        self.assertEqual(payload["summary"]["default_assembly_id"], assembly.id)
        self.assertIsNone(payload["summary"]["default_annotation_id"])
        self.assertTrue(payload["file_status"]["genome"])
