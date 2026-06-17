import os
import tempfile
import uuid

from django.test import TransactionTestCase

from files.models import Accession, Assembly, DataFile, FileType, GenomeFile


class DataFileDownloadTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.code_suffix = uuid.uuid4().hex[:8].upper()

    def create_disk_file(self, filename, content=b">chr1\nATGC\n"):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def test_datafile_valid_file_can_be_downloaded(self):
        file_path = self.create_disk_file("datafile-download.fasta")
        data_file = DataFile.objects.create(
            file_code=f"DFDL{self.code_suffix}A",
            file_name="datafile-download.fasta",
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("datafile-download.fasta", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b">chr1\nATGC\n")
        response.close()

    def test_datafile_missing_file_returns_404(self):
        missing_path = os.path.join(self.temp_dir.name, "missing.fasta")
        data_file = DataFile.objects.create(
            file_code=f"DFDL{self.code_suffix}B",
            file_name="missing.fasta",
            file_path=missing_path,
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_datafile_path_traversal_is_rejected(self):
        data_file = DataFile.objects.create(
            file_code=f"DFDL{self.code_suffix}C",
            file_name="unsafe.fasta",
            file_path=os.path.join(self.temp_dir.name, "..", "unsafe.fasta"),
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_legacy_genomefile_download_is_archived(self):
        accession_code = f"IR64_{self.code_suffix}"
        file_type = FileType.objects.create(
            name=f"FASTA_DOWNLOAD_{self.code_suffix}",
            extension="fasta",
        )
        accession = Accession.objects.create(accession=accession_code, sub_population="XI")
        assembly = Assembly.objects.create(
            accession=accession,
            name="default",
            is_default=True,
        )
        file_path = self.create_disk_file("legacy-genomefile-download.fasta")
        genome_file = GenomeFile.objects.create(
            name="legacy-genomefile-download.fasta",
            organism=accession_code,
            accession=accession,
            assembly=assembly,
            category="genome",
            file_path=file_path,
            file_type=file_type,
            size=os.path.getsize(file_path),
        )

        response = self.client.get(f"/gd/api/files/genome-files/{genome_file.id}/download/")

        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertTrue(payload["archived"])
        self.assertIn("GenomeFile download is archived", payload["message"])
