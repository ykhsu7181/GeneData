import json
import uuid

from django.test import TestCase

from files.models import Accession, DataFile, FileRelation, Sample, Species


class RawDataApiTestCase(TestCase):
    def setUp(self):
        self.suffix = uuid.uuid4().hex[:8]
        self.species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            species=self.species,
            accession=f"IR64_{self.suffix}",
            sub_population="XI",
        )
        self.sample = Sample.objects.create(
            sample_code=f"IR64_leaf_01_{self.suffix}",
            species=self.species,
            accession=self.accession,
            tissue="leaf",
        )
        self.data_file = DataFile.objects.create(
            file_code=f"RAW{self.suffix}",
            file_name="IR64_leaf_01_R1.fastq.gz",
            file_path="/data/project/rice/raw/IR64_leaf_01_R1.fastq.gz",
            file_size=1024,
            md5="a83f21cc91de42b88a0e8e3d17d91de42",
            description=json.dumps(
                {
                    "raw_data": {
                        "sample_code": self.sample.sample_code,
                        "raw_data_type": "RNA-seq",
                        "sequencing_platform": "Illumina",
                        "cluster_name": "cluster01",
                        "check_status": "verified",
                        "remark": "leaf paired-end reads",
                    }
                },
                ensure_ascii=False,
            ),
        )
        FileRelation.objects.create(
            file=self.data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="raw_reads_R1",
        )
        FileRelation.objects.create(
            file=self.data_file,
            related_type="sample",
            related_id=str(self.sample.id),
            related_code=self.sample.sample_code,
            file_role="raw_reads_R1",
        )

    def test_raw_data_api_returns_summary_and_deduped_rows(self):
        response = self.client.get("/gd/api/files/query/raw-data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["accession_count"], 1)
        self.assertEqual(payload["summary"]["sample_count"], 1)
        self.assertEqual(payload["summary"]["datafile_count"], 1)
        self.assertEqual(payload["summary"]["total_size"], 1024)
        self.assertEqual(payload["summary"]["cluster_count"], 1)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(len(payload["results"]), 1)

        row = payload["results"][0]
        self.assertEqual(row["file_id"], self.data_file.id)
        self.assertEqual(row["accession"], self.accession.accession)
        self.assertEqual(row["sample_id"], self.sample.sample_code)
        self.assertEqual(row["species_name"], "水稻")
        self.assertEqual(row["latin_name"], "Oryza sativa")
        self.assertEqual(row["raw_data_type"], "RNA-seq")
        self.assertEqual(row["sequencing_platform"], "Illumina")
        self.assertEqual(row["cluster_name"], "cluster01")
        self.assertEqual(row["check_status"], "verified")
        self.assertEqual(row["file_path"], self.data_file.file_path)
        self.assertNotIn("genome-files", json.dumps(payload))
        self.assertNotIn("legacy_genomefile", json.dumps(payload))

    def test_raw_data_api_filters_keyword_and_status(self):
        response = self.client.get(
            "/gd/api/files/query/raw-data/",
            {
                "keyword": self.sample.sample_code,
                "check_status": "verified",
                "species_id": self.species.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["total"], 1)

        empty_response = self.client.get(
            "/gd/api/files/query/raw-data/",
            {"keyword": "not-exists"},
        )
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json()["pagination"]["total"], 0)

        wrong_species_response = self.client.get(
            "/gd/api/files/query/raw-data/",
            {"species_id": self.species.id + 999999},
        )
        self.assertEqual(wrong_species_response.status_code, 200)
        self.assertEqual(wrong_species_response.json()["pagination"]["total"], 0)
