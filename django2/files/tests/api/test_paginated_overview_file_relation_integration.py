import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

from files.models import Accession, Assembly, DataFile, FileRelation, FileType, GenomeFile


class PaginatedOverviewFileRelationIntegrationTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.code_suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.code_suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_{self._testMethodName}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(accession=self.accession_code, sub_population="XI")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )

    def get_overview(self):
        return self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": self.accession_code},
        )

    def test_paginated_overview_uses_file_relation_files(self):
        genome_file = DataFile.objects.create(
            file_code=f"FILEOV{self.code_suffix}A",
            file_name=f"genome.{self.accession_code}.fasta",
            file_path=f"/tmp/new/genome.{self.accession_code}.fasta",
            file_size=1234,
        )
        FileRelation.objects.create(
            file=genome_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="genome",
        )
        transcriptome_file = DataFile.objects.create(
            file_code=f"FILEOV{self.code_suffix}B",
            file_name=f"transcriptome.root.{self.accession_code}.tar.gz",
            file_path=f"/tmp/new/transcriptome.root.{self.accession_code}.tar.gz",
            file_size=4567,
        )
        FileRelation.objects.create(
            file=transcriptome_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="transcriptome.root",
        )
        GenomeFile.objects.create(
            name=f"genome.{self.accession_code}.fasta",
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=f"/tmp/old/genome.{self.accession_code}.fasta",
            file_type=self.file_type,
            size=1234,
        )

        response = self.get_overview()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        row = payload["results"][0]
        self.assertEqual(row["genome"]["id"], genome_file.id)
        self.assertEqual(row["genome"]["name"], f"genome.{self.accession_code}.fasta")
        self.assertEqual(row["genome"]["file_path"], f"/tmp/new/genome.{self.accession_code}.fasta")
        self.assertEqual(row["genome"]["category"], "genome")
        self.assertEqual(row["genome"]["file_size"], 1234)
        self.assertEqual(row["genome"]["source"], "new_relation")
        self.assertEqual(
            row["genome"]["datafile_download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )
        self.assertEqual(row["genome"]["download_url"], row["genome"]["datafile_download_url"])
        self.assertNotIn("/genome-files/", row["genome"]["download_url"])
        self.assertTrue(row["hasTranscriptome"])

    def test_paginated_overview_does_not_fallback_to_genomefile(self):
        GenomeFile.objects.create(
            name=f"genome.{self.accession_code}.fasta",
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=f"/tmp/legacy/genome.{self.accession_code}.fasta",
            file_type=self.file_type,
            size=2345,
        )

        response = self.get_overview()

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertIsNone(row["genome"])

    def test_paginated_overview_does_not_fallback_to_organism_legacy_file(self):
        GenomeFile.objects.create(
            name=f"annotation.{self.accession_code}.gff",
            organism=self.accession_code,
            category="annotation",
            file_path=f"/tmp/legacy/annotation.{self.accession_code}.gff",
            file_type=self.file_type,
            size=3456,
        )

        response = self.get_overview()

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertIsNone(row["annotation"])

    def test_compare_overview_files_command_writes_report(self):
        GenomeFile.objects.create(
            name=f"genome.{self.accession_code}.fasta",
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=f"/tmp/genome.{self.accession_code}.fasta",
            file_type=self.file_type,
            size=1234,
        )
        data_file = DataFile.objects.create(
            file_code=f"FILEOV{self.code_suffix}C",
            file_name=f"genome.{self.accession_code}.fasta",
            file_path=f"/tmp/genome.{self.accession_code}.fasta",
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
            "compare_overview_files",
            accession=self.accession_code,
            output_dir=self.temp_dir.name,
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("old_count\t1", output)
        self.assertIn("new_count\t1", output)
        self.assertIn("matched_files\t1", output)

        report_path = os.path.join(self.temp_dir.name, "compare_overview_files.tsv")
        with open(report_path, "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("matched", report)
        self.assertIn(f"/tmp/genome.{self.accession_code}.fasta", report)


class PaginatedOverviewDownloadUnaffectedTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.code_suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.code_suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_DOWNLOAD_{self.code_suffix}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(accession=self.accession_code, sub_population="XI")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )

    def create_disk_file(self, filename, content=b">chr1\nATGC\n"):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def test_genomefile_download_endpoint_is_archived(self):
        file_path = self.create_disk_file(f"genome.{self.accession_code}.fasta")
        genome_file = GenomeFile.objects.create(
            name=f"genome.{self.accession_code}.fasta",
            organism=self.accession_code,
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
