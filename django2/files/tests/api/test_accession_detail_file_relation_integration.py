import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    GenomeFile,
    Project,
    Sample,
    Species,
)


class AccessionDetailFileRelationIntegrationTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.file_type = FileType.objects.create(name="FASTA", extension="fasta")
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )

    def test_accession_detail_uses_file_relation_flat_files(self):
        data_file = DataFile.objects.create(
            file_code="FILE000001",
            file_type=self.file_type,
            file_name="genome.IR64.fasta",
            file_path="/tmp/new/genome.IR64.fasta",
            file_size=1234,
            md5="abc123",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="genome",
        )
        GenomeFile.objects.create(
            name="genome.IR64.fasta",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path="/tmp/old/genome.IR64.fasta",
            file_type=self.file_type,
            size=1234,
        )

        response = self.client.get("/gd/api/files/accessions/IR64/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        files = payload["data"]["files"]
        self.assertEqual(payload["data"]["file_count"], 1)
        self.assertEqual(files[0]["id"], data_file.id)
        self.assertEqual(files[0]["name"], "genome.IR64.fasta")
        self.assertEqual(files[0]["file_path"], "/tmp/new/genome.IR64.fasta")
        self.assertEqual(files[0]["category"], "genome")
        self.assertEqual(files[0]["file_size"], 1234)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertEqual(
            files[0]["datafile_download_url"],
            f"/gd/api/files/data-files/{data_file.id}/download/",
        )
        self.assertEqual(files[0]["download_url"], files[0]["datafile_download_url"])
        self.assertNotIn("/genome-files/", files[0]["download_url"])

    def test_accession_detail_does_not_fallback_to_legacy_genomefile_files(self):
        GenomeFile.objects.create(
            name="annotation.IR64.gff",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            category="annotation",
            file_path="/tmp/legacy/annotation.IR64.gff",
            file_type=self.file_type,
            size=5678,
        )

        response = self.client.get("/gd/api/files/accessions/IR64/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        files = payload["data"]["files"]
        self.assertEqual(payload["data"]["file_count"], 0)
        self.assertEqual(files, [])

    def test_accession_detail_aggregates_new_structure_dashboard_data(self):
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
            chinese_name="水稻",
        )
        self.accession.species = species
        self.accession.sub_population = "CA"
        self.accession.description = "地方品种材料"
        self.accession.save()
        Sample.objects.create(
            sample_code="SAMPLE-C7-01",
            accession=self.accession,
            species=species,
        )
        project = Project.objects.create(
            project_code="PRJ-C7",
            project_name="Rice Diversity Project",
            owner="admin",
        )
        dataset = Dataset.objects.create(
            dataset_code="DS-C7-001",
            dataset_name="水稻数据集",
            dataset_type="genome",
            species=species,
            project=project,
            status="released",
        )
        annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="C7 annotation",
            is_default=True,
        )
        shared_file = DataFile.objects.create(
            file_code="FILE-C7-001",
            dataset=dataset,
            file_type=self.file_type,
            file_name="genome.C7.fasta",
            file_path="/tmp/new/genome.C7.fasta",
            file_size=1024,
        )
        annotation_file = DataFile.objects.create(
            file_code="FILE-C7-002",
            dataset=dataset,
            file_type=self.file_type,
            file_name="annotation.C7.gff3",
            file_path="/tmp/new/annotation.C7.gff3",
            file_size=2048,
        )
        FileRelation.objects.create(
            file=shared_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )
        FileRelation.objects.create(
            file=shared_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            related_code=self.assembly.name,
            file_role="genome",
        )
        FileRelation.objects.create(
            file=annotation_file,
            related_type="annotation",
            related_id=str(annotation.id),
            related_code=annotation.name,
            file_role="annotation",
        )

        response = self.client.get("/gd/api/files/accessions/IR64/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["summary"]["sample_count"], 1)
        self.assertEqual(data["summary"]["dataset_count"], 1)
        self.assertEqual(data["summary"]["file_count"], 2)
        self.assertEqual(data["summary"]["total_size"], 3072)
        self.assertEqual(data["accession"]["species"]["scientific_name"], "Oryza sativa")
        self.assertEqual(data["projects"][0]["project_code"], "PRJ-C7")
        self.assertEqual(data["datasets"][0]["dataset_code"], "DS-C7-001")
        self.assertEqual(len(data["files"]), 2)
        genome_file = next(item for item in data["files"] if item["file_role"] == "genome")
        self.assertEqual(genome_file["related_type"], "accession")
        self.assertEqual(
            {relation["related_type"] for relation in genome_file["relations"]},
            {"accession", "assembly"},
        )
        self.assertEqual(genome_file["dataset_code"], "DS-C7-001")
        self.assertEqual(genome_file["file_type"], "FASTA")
        self.assertIn("/data-files/", genome_file["download_url"])
        self.assertNotIn("/genome-files/", genome_file["download_url"])
        self.assertEqual(data["data_status"]["genome"], "ready")
        self.assertEqual(data["audit"]["created_by"], "admin")

    @override_settings(MANUAL_FILES_DIR="")
    def test_genomefile_download_endpoint_is_archived(self):
        file_path = os.path.join(self.temp_dir.name, "genome.IR64.fasta")
        with open(file_path, "wb") as handle:
            handle.write(b">chr1\nATGC\n")
        genome_file = GenomeFile.objects.create(
            name="genome.IR64.fasta",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=file_path,
            file_type=self.file_type,
            size=os.path.getsize(file_path),
        )

        response = self.client.get(f"/gd/api/files/genome-files/{genome_file.id}/download/")

        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertTrue(payload["archived"])
        self.assertIn("GenomeFile download is archived", payload["message"])

    def test_compare_accession_files_command_writes_report(self):
        GenomeFile.objects.create(
            name="genome.IR64.fasta",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path="/tmp/genome.IR64.fasta",
            file_type=self.file_type,
            size=1234,
        )
        data_file = DataFile.objects.create(
            file_code="FILE000010",
            file_name="genome.IR64.fasta",
            file_path="/tmp/genome.IR64.fasta",
            file_size=1234,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="genome",
        )
        stdout = StringIO()

        call_command(
            "compare_accession_files",
            accession="IR64",
            output_dir=self.temp_dir.name,
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("old_count\t1", output)
        self.assertIn("new_count\t1", output)
        self.assertIn("matched_files\t1", output)

        report_path = os.path.join(self.temp_dir.name, "compare_accession_files.tsv")
        with open(report_path, "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("matched", report)
        self.assertIn("/tmp/genome.IR64.fasta", report)
