import os
import tempfile
import uuid

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from files.models import (
    Accession,
    AccessionExternalMapping,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    FileType,
    Species,
)
from files.services.data_overview_v2_service import build_data_overview_payload


class DataOverviewApiTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            species=self.species,
            accession=f"02428_{self.suffix}",
            sub_population="GJ",
            country="中国",
            region="云南",
            longitude=102.71,
            latitude=25.04,
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="ASM_Rice_02428_v1",
            source_database="GenBank",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="ANN_Rice_02428_v1",
            source_name="Rice Annotation Project",
            is_default=True,
        )
        self.file_type = FileType.objects.create(
            code=f"FASTA_{self.suffix}",
            name="FASTA",
            extension="fa",
            format="FASTA",
        )
        self.dataset = Dataset.objects.create(
            dataset_code=f"DS_{self.suffix}",
            dataset_name="02428 Genome v1.0",
            dataset_type="genome",
            species=self.species,
        )
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
            source="Figshare",
        )

    def create_data_file(self, code_suffix, file_name, size, dataset=None):
        file_path = os.path.join(self.temp_dir.name, f"{self.suffix}-{file_name}")
        with open(file_path, "wb") as handle:
            handle.write(b"A" * size)
        return DataFile.objects.create(
            file_code=f"DF{self.suffix}{code_suffix}",
            dataset=dataset or self.dataset,
            file_type=self.file_type,
            file_name=file_name,
            original_name=f"original-{file_name}",
            file_path=file_path,
            file_size=size,
            md5="a" * 32,
            description="公开文件说明",
        )

    def add_relation(self, data_file, related_type, related_id, file_role, is_primary=False):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=self.accession.accession,
            file_role=file_role,
            is_primary=is_primary,
        )

    def seed_files(self):
        genome_file = self.create_data_file("GENOME", "02428.genome.fa", 380)
        annotation_file = self.create_data_file("GFF3", "02428.annotation.gff3", 120)
        transcriptome_file = self.create_data_file("RNA", "02428.expression.tsv", 68)
        self.add_relation(genome_file, "assembly", self.assembly.id, "genome_fasta", True)
        self.add_relation(annotation_file, "annotation", self.annotation.id, "annotation_gff3", True)
        self.add_relation(transcriptome_file, "accession", self.accession.id, "transcriptome_matrix", True)
        return genome_file, annotation_file, transcriptome_file

    def test_data_overview_returns_one_public_row_per_file(self):
        files = self.seed_files()

        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"accession": self.accession.accession, "page_size": 20},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["count"], 3)
        self.assertEqual({row["file_id"] for row in payload["results"]}, {item.id for item in files})
        genome_row = next(row for row in payload["results"] if row["file_id"] == files[0].id)
        self.assertEqual(genome_row["category"], "genome")
        self.assertEqual(genome_row["accession"], self.accession.accession)
        self.assertEqual(genome_row["species_name"], "水稻")
        self.assertEqual(genome_row["dataset_code"], self.dataset.dataset_code)
        self.assertEqual(genome_row["data_source"], "GenBank")
        self.assertEqual(genome_row["file_type"], "FASTA")
        self.assertEqual(genome_row["download_url"], f"/gd/api/files/data-files/{files[0].id}/download/")
        self.assertNotIn("file_path", genome_row)
        self.assertNotIn(self.temp_dir.name, str(payload))

    def test_duplicate_relations_do_not_duplicate_file_rows(self):
        genome_file, _, _ = self.seed_files()
        self.add_relation(genome_file, "accession", self.accession.id, "genome", False)

        payload = build_data_overview_payload({"search": "02428.genome.fa"})

        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["file_id"], genome_file.id)

    def test_filters_and_search_cover_file_and_context_fields(self):
        _, annotation_file, _ = self.seed_files()
        cases = (
            ({"search": "annotation.gff3"}, annotation_file.id),
            ({"search": self.accession.accession}, annotation_file.id),
            ({"search": "Oryza sativa", "category": "annotation"}, annotation_file.id),
            ({"species": self.species.species_code, "category": "annotation"}, annotation_file.id),
            ({"accession": self.accession.accession, "category": "annotation"}, annotation_file.id),
            ({"dataset": self.dataset.dataset_code, "category": "annotation"}, annotation_file.id),
        )
        for params, expected_id in cases:
            with self.subTest(params=params):
                payload = build_data_overview_payload(params)
                self.assertIn(expected_id, {row["file_id"] for row in payload["results"]})

    def test_summary_is_global_and_not_changed_by_result_filters(self):
        self.seed_files()
        payload = build_data_overview_payload({"category": "annotation"})

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["summary"]["accession_count"], 1)
        self.assertEqual(payload["summary"]["assembly_count"], 1)
        self.assertEqual(payload["summary"]["datafile_count"], 3)
        self.assertEqual(payload["summary"]["total_size"], 568)
        self.assertEqual(payload["summary"]["geo_location_count"], 1)

    def test_data_source_uses_metadata_priority_and_external_fallback(self):
        _, annotation_file, _ = self.seed_files()
        AccessionExternalMapping.objects.create(
            accession=self.accession,
            external_database="ENA",
            external_study_accession=f"ERP_{self.suffix}",
        )
        external_file = self.create_data_file("EXTERNAL", "external.fastq.gz", 20, dataset=None)
        external_file.dataset = None
        external_file.save(update_fields=["dataset"])
        self.add_relation(external_file, "accession", self.accession.id, "raw_reads", True)

        payload = build_data_overview_payload({"page_size": 20})
        rows = {row["file_id"]: row for row in payload["results"]}

        self.assertEqual(rows[annotation_file.id]["data_source"], "Rice Annotation Project")
        self.assertEqual(rows[external_file.id]["data_source"], "ENA")

    def test_pagination_and_filter_metadata_contract(self):
        self.seed_files()
        payload = build_data_overview_payload({"page": 1, "page_size": 2})

        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["next"], "?page=2&page_size=2")
        self.assertIsNone(payload["previous"])
        self.assertIn("data_categories", payload["filters"])
        self.assertIn(
            {"key": self.accession.accession, "label": self.accession.accession},
            payload["filters"]["accessions"],
        )
        self.assertIn(
            {
                "key": self.dataset.dataset_code,
                "label": f"{self.dataset.dataset_code} · {self.dataset.dataset_name}",
            },
            payload["filters"]["datasets"],
        )

    def test_pagination_rejects_invalid_values_and_caps_large_pages(self):
        self.seed_files()

        invalid = build_data_overview_payload({"page": "invalid", "page_size": "invalid"})
        capped = build_data_overview_payload({"page": -4, "page_size": 1000})

        self.assertEqual(invalid["page"], 1)
        self.assertEqual(invalid["page_size"], 20)
        self.assertEqual(capped["page"], 1)
        self.assertEqual(capped["page_size"], 100)

    def test_query_count_does_not_grow_with_page_rows(self):
        self.seed_files()
        for index in range(8):
            data_file = self.create_data_file(f"BULK{index}", f"bulk-{index}.fa", 10)
            self.add_relation(data_file, "accession", self.accession.id, "genome_fasta")

        with CaptureQueriesContext(connection) as queries:
            payload = build_data_overview_payload({"page": 1, "page_size": 20})

        self.assertEqual(payload["count"], 11)
        self.assertLessEqual(len(queries), 22)

    def test_data_overview_files_drawer_remains_compatible(self):
        genome_file, _, _ = self.seed_files()
        response = self.client.get(
            "/gd/api/files/query/data-overview-files/",
            {"accession": self.accession.accession, "category": "genome"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["files"]), 1)
        self.assertEqual(payload["files"][0]["file_id"], genome_file.id)
        self.assertEqual(payload["files"][0]["download_url"], f"/gd/api/files/data-files/{genome_file.id}/download/")

    def test_datafile_detail_is_public_and_does_not_expose_storage_path(self):
        genome_file, _, _ = self.seed_files()

        response = self.client.get(f"/gd/api/files/data-files/{genome_file.id}/detail/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["file_id"], genome_file.id)
        self.assertEqual(payload["dataset"]["dataset_code"], self.dataset.dataset_code)
        self.assertEqual(payload["accessions"], [self.accession.accession])
        self.assertEqual(payload["species"], ["Oryza sativa"])
        self.assertEqual(payload["relations"][0]["related_type"], "assembly")
        self.assertEqual(payload["download_url"], f"/gd/api/files/data-files/{genome_file.id}/download/")
        self.assertNotIn("file_path", payload)
        self.assertNotIn(self.temp_dir.name, str(payload))

    def test_datafile_detail_normalizes_json_description(self):
        data_file = self.create_data_file("JSON", "reads.fastq.gz", 10)
        data_file.description = '{"raw_data": {"remark": "paired-end reads", "internal_path": "D:/secret"}}'
        data_file.save(update_fields=["description"])
        self.add_relation(data_file, "accession", self.accession.id, "raw_reads", True)

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/detail/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "paired-end reads")
        self.assertNotIn("secret", str(response.json()))

    def test_datafile_detail_returns_404_for_missing_or_inactive_file(self):
        data_file = self.create_data_file("OLD", "old.fa", 10)
        data_file.is_current = False
        data_file.save(update_fields=["is_current"])

        self.assertEqual(
            self.client.get(f"/gd/api/files/data-files/{data_file.id}/detail/").status_code,
            404,
        )
        self.assertEqual(self.client.get("/gd/api/files/data-files/999999/detail/").status_code, 404)
