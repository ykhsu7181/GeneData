import json
import os
import tempfile
import uuid

from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation, FileType, Species


class GenomeListApiTestCase(TestCase):
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
            name="default",
            display_name="IR64 default assembly",
            description=json.dumps(
                {
                    "assembly_level": "Chromosome",
                    "chromosome_count": 12,
                    "genome_size_display": "373.1 Mb",
                }
            ),
            is_default=True,
        )
        self.file_type = FileType.objects.create(
            code=f"FASTA_{self.suffix}",
            name="FASTA",
            extension="fa",
        )

    def create_data_file(self, code_suffix, file_name, size=1024):
        file_path = os.path.join(self.temp_dir.name, file_name)
        with open(file_path, "wb") as handle:
            handle.write(b"A" * size)
        return DataFile.objects.create(
            file_code=f"GF{self.suffix}{code_suffix}",
            file_type=self.file_type,
            file_name=file_name,
            file_path=file_path,
            file_size=size,
            md5="a83f21cc91de42b88a0e8e3d17d91de42",
        )

    def add_assembly_file(self, data_file, file_role="genome_fasta", is_primary=True):
        return FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            related_code=self.assembly.name,
            file_role=file_role,
            is_primary=is_primary,
        )

    def test_genome_list_returns_new_relation_assembly_rows(self):
        genome_file = self.create_data_file("GENOME", "genome.IR64.fasta", 2048)
        self.add_assembly_file(genome_file)

        response = self.client.get(
            "/gd/api/files/query/genome-list/",
            {"species_id": self.species.id, "page_size": 20},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["page_size"], 20)
        self.assertEqual(payload["pagination"]["total"], 1)
        row = payload["results"][0]
        self.assertEqual(row["species_name"], "水稻")
        self.assertEqual(row["latin_name"], "Oryza sativa")
        self.assertEqual(row["accession"], self.accession.accession)
        self.assertEqual(row["assembly_id"], self.assembly.id)
        self.assertEqual(row["assembly_level"], "Chromosome")
        self.assertEqual(row["chromosome_count"], 12)
        self.assertEqual(row["genome_size_display"], "373.1 Mb")
        self.assertEqual(row["file_count"], 1)
        self.assertEqual(row["primary_file_id"], genome_file.id)
        self.assertEqual(
            row["download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )
        self.assertNotIn("genome-files", json.dumps(payload))
        self.assertNotIn("legacy_genomefile", json.dumps(payload))
        self.assertNotIn("organism_fallback", json.dumps(payload))

    def test_genome_files_drawer_returns_datafile_downloads(self):
        genome_file = self.create_data_file("GENOME", "genome.IR64.fasta", 2048)
        index_file = self.create_data_file("INDEX", "genome.IR64.fasta.fai", 12)
        self.add_assembly_file(genome_file, "genome_fasta", is_primary=True)
        self.add_assembly_file(index_file, "genome_index", is_primary=False)

        response = self.client.get(
            "/gd/api/files/query/genome-files/",
            {"assembly_id": self.assembly.id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assembly_id"], self.assembly.id)
        self.assertEqual(len(payload["files"]), 2)
        self.assertEqual(payload["files"][0]["file_id"], genome_file.id)
        self.assertEqual(payload["files"][0]["file_role_display"], "参考基因组序列")
        self.assertEqual(
            payload["files"][0]["download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )
        self.assertEqual(payload["files"][1]["file_role_display"], "基因组索引")
        self.assertNotIn("genome-files", json.dumps(payload))

    def test_genome_list_filters_assembly_level(self):
        genome_file = self.create_data_file("GENOME", "genome.IR64.fasta", 2048)
        self.add_assembly_file(genome_file)

        matched = self.client.get(
            "/gd/api/files/query/genome-list/",
            {"assembly_level": "Chromosome"},
        )
        unmatched = self.client.get(
            "/gd/api/files/query/genome-list/",
            {"assembly_level": "Scaffold"},
        )

        self.assertEqual(matched.status_code, 200)
        self.assertEqual(unmatched.status_code, 200)
        self.assertEqual(matched.json()["pagination"]["total"], 1)
        self.assertEqual(unmatched.json()["pagination"]["total"], 0)
