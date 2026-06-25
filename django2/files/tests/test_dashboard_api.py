import os
import tempfile
import uuid

from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    Sample,
    Species,
)


class DashboardApiTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.file_type = FileType.objects.create(
            name=f"DASH_{self.suffix}",
            extension="fasta",
        )

        self.species_rice = Species.objects.create(
            species_code=f"SP_RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.species_maize = Species.objects.create(
            species_code=f"SP_MAIZE_{self.suffix}",
            chinese_name="玉米",
            scientific_name="Zea mays",
        )

        self.accession_rice_1 = Accession.objects.create(
            species=self.species_rice,
            accession=f"IR64_{self.suffix}",
            sub_population="XI",
            country="China",
            region="Yunnan",
            longitude=102.71,
            latitude=25.04,
        )
        self.accession_rice_2 = Accession.objects.create(
            species=self.species_rice,
            accession=f"MH63_{self.suffix}",
            sub_population="XI",
            country="China",
            region="Yunnan",
            longitude=102.71,
            latitude=25.04,
        )
        self.accession_maize = Accession.objects.create(
            species=self.species_maize,
            accession=f"B73_{self.suffix}",
            sub_population="Temperate",
            country="USA",
            region="Iowa",
            longitude=-93.5,
            latitude=42.0,
        )
        self.accession_unknown = Accession.objects.create(
            accession=f"UNK_{self.suffix}",
            sub_population="",
        )

        self.sample_rice_1 = Sample.objects.create(
            sample_code=f"SAMPLE_R1_{self.suffix}",
            species=self.species_rice,
            accession=self.accession_rice_1,
        )
        self.sample_rice_2 = Sample.objects.create(
            sample_code=f"SAMPLE_R2_{self.suffix}",
            species=self.species_rice,
            accession=self.accession_rice_2,
        )
        self.sample_maize = Sample.objects.create(
            sample_code=f"SAMPLE_M1_{self.suffix}",
            species=self.species_maize,
            accession=self.accession_maize,
        )

        self.dataset_genome = Dataset.objects.create(
            dataset_code=f"DS_GENOME_{self.suffix}",
            dataset_name="Genome collection",
            dataset_type="genome",
            species=self.species_rice,
        )
        self.dataset_annotation = Dataset.objects.create(
            dataset_code=f"DS_ANN_{self.suffix}",
            dataset_name="Annotation set",
            dataset_type="annotation",
            species=self.species_maize,
        )

        self.assembly_rice = Assembly.objects.create(
            accession=self.accession_rice_1,
            name="default",
            is_default=True,
        )
        self.annotation_rice = Annotation.objects.create(
            assembly=self.assembly_rice,
            name="default-annotation",
            is_default=True,
        )

    def create_data_file(self, code_suffix, filename, *, dataset=None, size=128):
        file_path = os.path.join(self.temp_dir.name, filename)
        with open(file_path, "wb") as handle:
            handle.write(b"A" * size)
        return DataFile.objects.create(
            file_code=f"DF{self.suffix}{code_suffix}",
            dataset=dataset,
            file_type=self.file_type,
            file_name=filename,
            file_path=file_path,
            file_size=size,
        )

    def add_relation(self, data_file, related_type, related_id, file_role, related_code=None):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=related_code,
            file_role=file_role,
        )

    def test_dashboard_endpoint_returns_unified_summary_and_cards(self):
        genome_file = self.create_data_file(
            "A",
            f"genome.{self.accession_rice_1.accession}.fasta",
            dataset=self.dataset_genome,
            size=120,
        )
        annotation_file = self.create_data_file(
            "B",
            f"annotation.{self.accession_rice_1.accession}.gff3",
            dataset=self.dataset_annotation,
            size=80,
        )
        orphan_file = self.create_data_file(
            "C",
            f"orphan.{self.suffix}.txt",
            size=999,
        )
        self.add_relation(genome_file, "accession", self.accession_rice_1.id, "genome", self.accession_rice_1.accession)
        self.add_relation(annotation_file, "annotation", self.annotation_rice.id, "annotation", self.annotation_rice.name)

        response = self.client.get("/gd/api/warehouse/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["summary"]["species_count"], 2)
        self.assertEqual(payload["summary"]["accession_count"], 4)
        self.assertEqual(payload["summary"]["sample_count"], 3)
        self.assertEqual(payload["summary"]["dataset_count"], 2)
        self.assertEqual(payload["summary"]["datafile_count"], 2)
        self.assertEqual(payload["summary"]["total_size"], 200)
        self.assertNotIn(orphan_file.id, [item["file_id"] for item in payload["file_role_summary"] if "file_id" in item])

        rice_card = next(card for card in payload["species_cards"] if card["species_id"] == self.species_rice.id)
        self.assertEqual(rice_card["name_cn"], "水稻")
        self.assertEqual(rice_card["latin_name"], "Oryza sativa")
        self.assertEqual(rice_card["accession_count"], 2)
        self.assertEqual(rice_card["sample_count"], 2)
        self.assertEqual(rice_card["dataset_count"], 1)
        self.assertEqual(rice_card["datafile_count"], 2)
        self.assertEqual(rice_card["total_size"], 200)

    def test_dashboard_endpoint_returns_distribution_sections(self):
        genome_file = self.create_data_file(
            "D",
            f"genome.{self.accession_rice_1.accession}.fasta",
            dataset=self.dataset_genome,
            size=100,
        )
        maize_file = self.create_data_file(
            "E",
            f"genome.{self.accession_maize.accession}.fasta",
            dataset=self.dataset_annotation,
            size=50,
        )
        self.add_relation(genome_file, "accession", self.accession_rice_1.id, "genome")
        self.add_relation(genome_file, "accession", self.accession_rice_2.id, "genome")
        self.add_relation(maize_file, "accession", self.accession_maize.id, "genome")

        response = self.client.get("/gd/api/warehouse/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        sub_population_names = [item["name"] for item in payload["sub_population_distribution"]]
        self.assertIn("XI", sub_population_names)
        self.assertIn("Temperate", sub_population_names)
        self.assertIn("Unknown", sub_population_names)

        genome_dataset = next(
            item for item in payload["dataset_type_summary"] if item["dataset_type"] == "genome"
        )
        self.assertEqual(genome_dataset["dataset_count"], 1)

        genome_role = next(
            item for item in payload["file_role_summary"] if item["file_role"] == "genome"
        )
        self.assertEqual(genome_role["datafile_count"], 2)
        self.assertEqual(genome_role["total_size"], 150)

        geo_yunnan = next(
            item for item in payload["geo_distribution"]
            if item["region"] == "Yunnan"
        )
        self.assertEqual(geo_yunnan["accession_count"], 2)
        self.assertEqual(geo_yunnan["sample_count"], 2)
        self.assertEqual(geo_yunnan["latitude"], 25.04)
        self.assertEqual(geo_yunnan["longitude"], 102.71)
        self.assertEqual(
            geo_yunnan["accession_names"],
            sorted([self.accession_rice_1.accession, self.accession_rice_2.accession])
        )
        self.assertEqual(geo_yunnan["species_names"], [self.species_rice.chinese_name])

        self.assertIn("hot_keywords", payload)
        self.assertGreaterEqual(len(payload["hot_keywords"]), 1)

    def test_dashboard_endpoint_returns_resource_summary_and_recent_updates(self):
        genome_file = self.create_data_file(
            "G",
            f"genome.resource.{self.accession_rice_1.accession}.fasta",
            dataset=self.dataset_genome,
            size=256,
        )
        annotation_file = self.create_data_file(
            "H",
            f"annotation.resource.{self.accession_rice_1.accession}.gff3",
            dataset=self.dataset_annotation,
            size=128,
        )
        self.add_relation(genome_file, "assembly", self.assembly_rice.id, "genome", self.assembly_rice.name)
        self.add_relation(annotation_file, "annotation", self.annotation_rice.id, "annotation", self.annotation_rice.name)

        response = self.client.get("/gd/api/warehouse/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        resource_summary = payload["resource_summary"]
        resource_keys = [item["key"] for item in resource_summary]
        self.assertEqual(
            resource_keys,
            ["raw_data", "genome", "annotation", "transcriptome", "population_genetics", "download"],
        )

        genome_resource = next(item for item in resource_summary if item["key"] == "genome")
        self.assertEqual(genome_resource["count"], 1)
        self.assertEqual(genome_resource["route"], "/genome-card")

        annotation_resource = next(item for item in resource_summary if item["key"] == "annotation")
        self.assertEqual(annotation_resource["count"], 1)
        self.assertEqual(annotation_resource["route"], "/annotation")

        download_resource = next(item for item in resource_summary if item["key"] == "download")
        self.assertEqual(download_resource["count"], 384)
        self.assertEqual(download_resource["count_display"], "384 B")
        self.assertEqual(download_resource["route"], "/data-overview")

        self.assertIn("recent_updates", payload)
        self.assertGreaterEqual(len(payload["recent_updates"]), 1)
        self.assertTrue(
            any(item["title"].startswith("新增文件") for item in payload["recent_updates"])
        )

    def test_dashboard_endpoint_returns_fallback_card_when_species_table_is_empty(self):
        Sample.objects.all().delete()
        Dataset.objects.all().delete()
        Accession.objects.update(species=None)
        Species.objects.all().delete()
        accession = Accession.objects.create(
            accession=f"NO_SPECIES_{self.suffix}",
            sub_population="XI",
        )
        data_file = self.create_data_file(
            "F",
            f"genome.{accession.accession}.fasta",
            size=64,
        )
        self.add_relation(data_file, "accession", accession.id, "genome", accession.accession)

        response = self.client.get("/gd/api/warehouse/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["species_count"], 0)
        self.assertGreaterEqual(len(payload["species_cards"]), 1)

        fallback_card = payload["species_cards"][0]
        self.assertEqual(fallback_card["species_id"], "unassigned")
        self.assertEqual(fallback_card["species_code"], "UNASSIGNED")
        self.assertEqual(fallback_card["name_cn"], "未归属物种")
        self.assertEqual(fallback_card["latin_name"], "Unassigned accessions")
        self.assertEqual(fallback_card["accession_count"], 5)
        self.assertEqual(fallback_card["datafile_count"], 1)
        self.assertEqual(fallback_card["total_size"], 64)
