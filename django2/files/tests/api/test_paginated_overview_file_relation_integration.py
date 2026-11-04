import uuid

from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation


class PaginatedOverviewFileRelationIntegrationTestCase(TestCase):
    def setUp(self):
        self.code_suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.code_suffix}"
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
