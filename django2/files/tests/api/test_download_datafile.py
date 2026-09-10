import os
import tempfile
import uuid

from django.test import TransactionTestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile


class DataFileDownloadTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_DOWNLOAD_{self.suffix}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(accession=self.accession_code, sub_population="XI")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="default-annotation",
            standard_id=f"ANN_{self.suffix}",
            is_default=True,
        )

    def create_disk_file(self, filename, content=b">chr1\nATGC\n"):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def create_data_file(self, code_suffix, filename, content=b">chr1\nATGC\n"):
        file_path = self.create_disk_file(filename, content=content)
        return DataFile.objects.create(
            file_code=f"DFDL{self.suffix}{code_suffix}",
            file_type=self.file_type,
            file_name=filename,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )

    def add_relation(self, data_file, related_type, related_id, file_role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            related_code=self.accession_code,
            file_role=file_role,
        )

    def assert_datafile_download_links(self, file_payload, data_file):
        expected_url = f"/gd/api/files/data-files/{data_file.id}/download/"
        self.assertEqual(file_payload["id"], data_file.id)
        self.assertEqual(file_payload["source"], "new_relation")
        self.assertEqual(file_payload["datafile_download_url"], expected_url)
        self.assertEqual(file_payload["download_url"], expected_url)
        self.assertNotIn("/genome-files/", file_payload["datafile_download_url"])
        self.assertNotIn("/genome-files/", file_payload["download_url"])

    def test_datafile_valid_file_can_be_downloaded(self):
        data_file = self.create_data_file("A", "datafile-download.fasta")

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(data_file.file_name, response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b">chr1\nATGC\n")
        response.close()

    def test_datafile_missing_file_returns_404(self):
        data_file = DataFile.objects.create(
            file_code=f"DFDL{self.suffix}B",
            file_name="missing.fasta",
            file_path=os.path.join(self.temp_dir.name, "missing.fasta"),
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_datafile_path_traversal_is_rejected(self):
        data_file = DataFile.objects.create(
            file_code=f"DFDL{self.suffix}C",
            file_name="unsafe.fasta",
            file_path=os.path.join(self.temp_dir.name, "..", "unsafe.fasta"),
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_business_interfaces_return_datafile_download_urls(self):
        accession_file = self.create_data_file("D", f"genome.{self.accession_code}.fasta")
        annotation_file = self.create_data_file("E", f"annotation.{self.accession_code}.gff3")
        self.add_relation(accession_file, "accession", self.accession.id, "genome")
        self.add_relation(annotation_file, "annotation", self.annotation.id, "annotation")

        accession_response = self.client.get(f"/gd/api/files/accessions/{self.accession_code}/")
        annotation_response = self.client.get(
            f"/gd/api/files/query/annotation-data/?annotation_id={self.annotation.id}"
        )
        overview_response = self.client.get(
            "/gd/api/files/query/paginated-overview/",
            {"search": self.accession_code},
        )

        self.assertEqual(accession_response.status_code, 200)
        self.assert_datafile_download_links(accession_response.json()["data"]["files"][0], accession_file)
        self.assertEqual(annotation_response.status_code, 200)
        self.assert_datafile_download_links(annotation_response.json()["annotation_file"], annotation_file)
        self.assertEqual(overview_response.status_code, 200)
        self.assert_datafile_download_links(overview_response.json()["results"][0]["genome"], accession_file)

    def test_legacy_genomefile_download_is_archived(self):
        file_path = self.create_disk_file("legacy-genomefile-download.fasta")
        genome_file = GenomeFile.objects.create(
            name="legacy-genomefile-download.fasta",
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
