import os
import tempfile
import uuid

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    Species,
)
from files.services.data_overview_service import build_data_overview_payload


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
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="ANN_Rice_02428_v1",
            is_default=True,
        )
        self.file_type = FileType.objects.create(
            code=f"FASTA_{self.suffix}",
            name="FASTA",
            extension="fa",
        )
        self.dataset = Dataset.objects.create(
            dataset_code=f"DS_{self.suffix}",
            dataset_name="02428 Genome v1.0",
            dataset_type="genome",
            species=self.species,
        )

    def create_data_file(self, code_suffix, file_name, size):
        file_path = os.path.join(self.temp_dir.name, file_name)
        with open(file_path, "wb") as handle:
            handle.write(b"A" * size)
        return DataFile.objects.create(
            file_code=f"DF{self.suffix}{code_suffix}",
            dataset=self.dataset,
            file_type=self.file_type,
            file_name=file_name,
            file_path=file_path,
            file_size=size,
        )

    def add_relation(self, data_file, related_type, related_id, file_role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=self.accession.accession,
            file_role=file_role,
        )

    def seed_files(self):
        genome_file = self.create_data_file("GENOME", "02428.genome.fa", 380)
        annotation_file = self.create_data_file("GFF3", "02428.annotation.gff3", 120)
        transcriptome_file = self.create_data_file("RNA", "02428.expression.tsv", 68)
        self.add_relation(genome_file, "assembly", self.assembly.id, "genome_fasta")
        self.add_relation(annotation_file, "annotation", self.annotation.id, "annotation_gff3")
        self.add_relation(transcriptome_file, "accession", self.accession.id, "transcriptome_matrix")
        return genome_file, annotation_file, transcriptome_file

    def test_data_overview_returns_summary_matrix_and_detail_rows(self):
        genome_file, annotation_file, transcriptome_file = self.seed_files()

        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"search": self.accession.accession, "page_size": 20},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["accession_count"], 1)
        self.assertEqual(payload["summary"]["datafile_count"], 3)
        self.assertEqual(payload["summary"]["total_size"], 568)
        self.assertEqual(payload["summary"]["geo_location_count"], 1)
        self.assertEqual(payload["count"], 1)

        row = payload["matrix_rows"][0]
        self.assertEqual(row["accession"], self.accession.accession)
        self.assertEqual(row["species_name"], "水稻")
        self.assertEqual(row["cells"]["genome"]["file_count"], 1)
        self.assertEqual(row["cells"]["genome"]["total_size"], genome_file.file_size)
        self.assertEqual(row["cells"]["annotation"]["file_count"], 1)
        self.assertEqual(row["cells"]["annotation"]["total_size"], annotation_file.file_size)
        self.assertEqual(row["cells"]["transcriptome"]["file_count"], 1)
        self.assertEqual(row["cells"]["transcriptome"]["total_size"], transcriptome_file.file_size)
        self.assertEqual(row["cells"]["population"]["status"], "coming_soon")

        detail_types = {item["category"] for item in payload["detail_rows"]}
        self.assertIn("genome", detail_types)
        self.assertIn("annotation", detail_types)
        self.assertIn("transcriptome", detail_types)
        self.assertNotIn("population", detail_types)

    def test_data_overview_summary_follows_filters(self):
        self.seed_files()
        other = Accession.objects.create(accession=f"OTHER_{self.suffix}", sub_population="XI")
        other_file = self.create_data_file("OTHER", "other.genome.fa", 99)
        self.add_relation(other_file, "accession", other.id, "genome_fasta")

        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"sub_populations": "GJ"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["accession_count"], 1)
        self.assertEqual(payload["summary"]["datafile_count"], 3)
        self.assertEqual(payload["matrix_rows"][0]["accession"], self.accession.accession)

    def test_data_overview_exposes_species_filter_options(self):
        self.seed_files()

        response = self.client.get("/gd/api/files/query/data-overview/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        species_options = payload["filters"]["species"]
        self.assertIn(
            {
                "key": self.species.species_code,
                "label": "水稻",
                "latin_name": "Oryza sativa",
            },
            species_options,
        )

    def test_data_overview_query_count_does_not_grow_per_accession(self):
        self.seed_files()
        for index in range(6):
            Accession.objects.create(
                species=self.species,
                accession=f"BULK_{self.suffix}_{index}",
            )

        with CaptureQueriesContext(connection) as queries:
            payload = build_data_overview_payload({"page": 1, "page_size": 20})

        self.assertEqual(payload["count"], 7)
        self.assertLessEqual(len(queries), 10)

    def test_data_overview_summary_follows_category_filter(self):
        self.seed_files()

        response = self.client.get(
            "/gd/api/files/query/data-overview/",
            {"search": self.accession.accession, "category": "annotation"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["accession_count"], 1)
        self.assertEqual(payload["summary"]["datafile_count"], 1)
        self.assertEqual(payload["summary"]["total_size"], 120)
        self.assertEqual(payload["matrix_rows"][0]["cells"]["annotation"]["file_count"], 1)

    def test_data_overview_files_drawer_returns_datafile_downloads_and_chinese_roles(self):
        genome_file, _, _ = self.seed_files()

        response = self.client.get(
            "/gd/api/files/query/data-overview-files/",
            {"accession": self.accession.accession, "category": "genome"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], f"{self.accession.accession} / 基因组 文件列表")
        self.assertEqual(payload["relation_overview"]["accession"], self.accession.accession)
        self.assertEqual(payload["relation_overview"]["assembly"], self.assembly.name)
        self.assertEqual(len(payload["files"]), 1)
        self.assertEqual(payload["files"][0]["file_id"], genome_file.id)
        self.assertEqual(payload["files"][0]["file_role_display"], "参考基因组序列")
        self.assertEqual(
            payload["files"][0]["download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )
        self.assertNotIn("genome-files", payload["files"][0]["download_url"])
