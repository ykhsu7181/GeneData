import os
import tempfile
import uuid

from django.test import TransactionTestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile


class DownloadNewOnlyTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_DOWNLOAD_NEW_ONLY_{self.suffix}",
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
            file_code=f"DLNEW{self.suffix}{code_suffix}",
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

    def test_accession_detail_returns_datafile_download_url(self):
        data_file = self.create_data_file("A", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")
        legacy_path = self.create_disk_file(f"legacy.{self.accession_code}.fasta")
        GenomeFile.objects.create(
            name=f"legacy.{self.accession_code}.fasta",
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=legacy_path,
            file_type=self.file_type,
            size=os.path.getsize(legacy_path),
        )

        response = self.client.get(f"/gd/api/files/accessions/{self.accession_code}/")

        self.assertEqual(response.status_code, 200)
        files = response.json()["data"]["files"]
        self.assertEqual(len(files), 1)
        self.assert_datafile_download_links(files[0], data_file)

    def test_annotation_endpoint_returns_datafile_download_url(self):
        content = (
            b"##gff-version 3\n"
            b"chr1\tsource\tgene\t1\t10\t.\t+\t.\tID=gene1\n"
        )
        data_file = self.create_data_file("B", f"annotation.{self.accession_code}.gff3", content=content)
        self.add_relation(data_file, "annotation", self.annotation.id, "annotation")

        response = self.client.get(
            f"/gd/api/files/genome-files/get_annotation_data/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assert_datafile_download_links(payload["annotation_file"], data_file)

    def test_paginated_overview_returns_datafile_download_url(self):
        data_file = self.create_data_file("C", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")

        response = self.client.get(
            "/gd/api/files/genome-files/paginated_overview/",
            {"search": self.accession_code},
        )

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assert_datafile_download_links(row["genome"], data_file)

    def test_datafile_download_can_download_file(self):
        data_file = self.create_data_file("D", f"download.{self.accession_code}.fasta")

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(data_file.file_name, response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b">chr1\nATGC\n")
        response.close()

    def test_datafile_download_missing_file_returns_404(self):
        missing_path = os.path.join(self.temp_dir.name, "missing.fasta")
        data_file = DataFile.objects.create(
            file_code=f"DLNEW{self.suffix}E",
            file_name="missing.fasta",
            file_path=missing_path,
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_datafile_download_path_traversal_returns_404(self):
        data_file = DataFile.objects.create(
            file_code=f"DLNEW{self.suffix}F",
            file_name="unsafe.fasta",
            file_path=os.path.join(self.temp_dir.name, "..", "unsafe.fasta"),
        )

        response = self.client.get(f"/gd/api/files/data-files/{data_file.id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_legacy_genomefile_download_is_not_used_by_business_interfaces(self):
        data_file = self.create_data_file("G", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")
        legacy_path = self.create_disk_file(f"legacy-download.{self.accession_code}.fasta")
        genome_file = GenomeFile.objects.create(
            name=f"legacy-download.{self.accession_code}.fasta",
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            category="genome",
            file_path=legacy_path,
            file_type=self.file_type,
            size=os.path.getsize(legacy_path),
        )

        response = self.client.get(f"/gd/api/files/accessions/{self.accession_code}/")

        self.assertEqual(response.status_code, 200)
        file_payload = response.json()["data"]["files"][0]
        self.assert_datafile_download_links(file_payload, data_file)
        self.assertNotEqual(file_payload["id"], genome_file.id)
