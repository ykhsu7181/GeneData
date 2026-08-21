import json
import os
import tempfile
import uuid

from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation, FileType, Sample, Species


class TranscriptomeListApiTestCase(TestCase):
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
            accession=f"IR64_{self.suffix}",
            sub_population="XI",
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IRGSP-1.0",
            display_name="IRGSP-1.0",
            is_default=True,
        )
        self.sample = Sample.objects.create(
            sample_code=f"IR64_leaf_01_{self.suffix}",
            sample_name="IR64 leaf sample",
            species=self.species,
            accession=self.accession,
            tissue="leaf",
            data_type="transcriptome",
        )
        self.file_type = FileType.objects.create(
            code=f"TSV_{self.suffix}",
            name="TSV",
            extension="tsv",
        )

    def create_data_file(self, code_suffix, file_name, size=1024):
        file_path = os.path.join(self.temp_dir.name, file_name)
        with open(file_path, "wb") as handle:
            handle.write(b"A" * size)
        return DataFile.objects.create(
            file_code=f"TR{self.suffix}{code_suffix}",
            file_type=self.file_type,
            file_name=file_name,
            file_path=file_path,
            file_size=size,
            md5="a83f21cc91de42b88a0e8e3d17d91de42",
        )

    def add_relation(self, data_file, related_type, related_id, file_role, related_code=""):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=related_code,
            file_role=file_role,
        )

    def seed_transcriptome_files(self):
        r1 = self.create_data_file("R1", "IR64_leaf_R1.fastq.gz", 1024)
        r2 = self.create_data_file("R2", "IR64_leaf_R2.fastq.gz", 2048)
        for data_file, role in ((r1, "rnaseq_raw_R1"), (r2, "rnaseq_raw_R2")):
            self.add_relation(data_file, "sample", self.sample.id, role, self.sample.sample_code)
            self.add_relation(data_file, "assembly", self.assembly.id, role, self.assembly.name)
        return r1, r2

    def test_transcriptome_list_returns_new_relation_rows(self):
        r1, r2 = self.seed_transcriptome_files()

        response = self.client.get(
            "/gd/api/files/query/transcriptome-list/",
            {"species_id": self.species.id, "sample_type": "leaf", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["page_size"], 20)
        self.assertEqual(payload["pagination"]["total"], 1)
        row = payload["results"][0]
        self.assertEqual(row["species_name"], "水稻")
        self.assertEqual(row["latin_name"], "Oryza sativa")
        self.assertEqual(row["accession"], self.accession.accession)
        self.assertEqual(row["accession_id"], self.accession.id)
        self.assertEqual(row["assembly_id"], self.assembly.id)
        self.assertEqual(row["assembly_name"], "IRGSP-1.0")
        self.assertEqual(row["sample_type"], "leaf")
        self.assertEqual(row["file_count"], 2)
        self.assertEqual(row["total_size"], r1.file_size + r2.file_size)
        self.assertEqual(row["total_size_display"], "3 KB")
        self.assertNotIn("genome-files", json.dumps(payload))
        self.assertNotIn("legacy_genomefile", json.dumps(payload))
        self.assertNotIn("organism_fallback", json.dumps(payload))

    def test_transcriptome_files_drawer_returns_datafile_downloads(self):
        r1, r2 = self.seed_transcriptome_files()

        response = self.client.get(
            "/gd/api/files/query/transcriptome-files/",
            {
                "accession_id": self.accession.id,
                "assembly_id": self.assembly.id,
                "sample_type": "leaf",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accession"], self.accession.accession)
        self.assertEqual(payload["sample_type"], "leaf")
        self.assertEqual(len(payload["files"]), 2)
        self.assertEqual(payload["files"][0]["file_id"], r1.id)
        self.assertEqual(payload["files"][0]["file_role_display"], "RNA-seq 原始数据 R1")
        self.assertEqual(
            payload["files"][0]["download_url"],
            f"/gd/api/files/data-files/{r1.id}/download/",
        )
        self.assertEqual(payload["files"][1]["file_id"], r2.id)
        self.assertEqual(payload["files"][1]["file_role_display"], "RNA-seq 原始数据 R2")
        self.assertNotIn("genome-files", json.dumps(payload))

    def test_transcriptome_list_filters_keyword_and_sample_type(self):
        self.seed_transcriptome_files()

        matched = self.client.get(
            "/gd/api/files/query/transcriptome-list/",
            {"keyword": self.accession.accession, "sample_type": "leaf"},
        )
        unmatched = self.client.get(
            "/gd/api/files/query/transcriptome-list/",
            {"keyword": "not-matched", "sample_type": "leaf"},
        )
        wrong_sample_type = self.client.get(
            "/gd/api/files/query/transcriptome-list/",
            {"keyword": self.accession.accession, "sample_type": "root"},
        )

        self.assertEqual(matched.status_code, 200)
        self.assertEqual(unmatched.status_code, 200)
        self.assertEqual(wrong_sample_type.status_code, 200)
        self.assertEqual(matched.json()["pagination"]["total"], 1)
        self.assertEqual(unmatched.json()["pagination"]["total"], 0)
        self.assertEqual(wrong_sample_type.json()["pagination"]["total"], 0)
