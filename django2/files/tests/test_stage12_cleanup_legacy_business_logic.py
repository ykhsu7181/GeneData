import inspect
import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from files.management.commands import scan_files
from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services import accession_context, file_relation_service
from files.services.file_relation_service import get_files_for_accession
from files.views import GenomeFileViewSet


class Stage12CleanupLegacyBusinessLogicTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_STAGE12_{self.suffix}",
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
            file_code=f"ST12{self.suffix}{code_suffix}",
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

    def assert_new_relation_file(self, payload, data_file):
        expected_url = f"/gd/api/files/data-files/{data_file.id}/download/"
        self.assertEqual(payload["id"], data_file.id)
        self.assertEqual(payload["source"], "new_relation")
        self.assertEqual(payload["datafile_download_url"], expected_url)
        self.assertEqual(payload["download_url"], expected_url)
        self.assertNotIn("legacy_genomefile", str(payload))
        self.assertNotIn("organism_fallback", str(payload))
        self.assertNotIn("/genome-files/", str(payload))

    def test_file_relation_service_returns_no_legacy_sources(self):
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=self.accession_code,
            accession=self.accession,
            category="genome",
            file_path="/tmp/stage12/legacy.fasta",
            file_type=self.file_type,
            size=123,
        )

        self.assertEqual(get_files_for_accession(self.accession.id), [])

        data_file = self.create_data_file("A", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")
        files = get_files_for_accession(self.accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertNotIn("legacy_genomefile", str(files))
        self.assertNotIn("organism_fallback", str(files))

    def test_accession_detail_does_not_return_genomefile_download(self):
        data_file = self.create_data_file("B", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")

        response = self.client.get(f"/gd/api/files/accessions/{self.accession_code}/")

        self.assertEqual(response.status_code, 200)
        self.assert_new_relation_file(response.json()["data"]["files"][0], data_file)

    def test_annotation_does_not_return_genomefile_download(self):
        content = (
            b"##gff-version 3\n"
            b"chr1\tsource\tgene\t1\t10\t.\t+\t.\tID=gene1\n"
        )
        data_file = self.create_data_file("C", f"annotation.{self.accession_code}.gff3", content=content)
        self.add_relation(data_file, "annotation", self.annotation.id, "annotation")

        response = self.client.get(
            f"/gd/api/files/genome-files/get_annotation_data/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assert_new_relation_file(response.json()["annotation_file"], data_file)

    def test_paginated_overview_does_not_return_genomefile_download(self):
        data_file = self.create_data_file("D", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")

        response = self.client.get(
            "/gd/api/files/genome-files/paginated_overview/",
            {"search": self.accession_code},
        )

        self.assertEqual(response.status_code, 200)
        self.assert_new_relation_file(response.json()["results"][0]["genome"], data_file)

    def test_scan_files_creates_no_genomefile_and_rejects_legacy_dual_modes(self):
        scan_dir = tempfile.TemporaryDirectory()
        self.addCleanup(scan_dir.cleanup)
        file_path = os.path.join(scan_dir.name, f"genome.{self.accession_code}.fasta")
        with open(file_path, "wb") as handle:
            handle.write(b">chr1\nATGC\n")

        call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name)

        self.assertTrue(DataFile.objects.filter(file_path=os.path.abspath(os.path.normpath(file_path))).exists())
        self.assertTrue(FileRelation.objects.filter(related_type="accession", related_id=str(self.accession.id)).exists())
        self.assertFalse(GenomeFile.objects.filter(file_path=os.path.abspath(os.path.normpath(file_path))).exists())

        with self.assertRaises(CommandError):
            call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name, write_mode="legacy")
        with self.assertRaises(CommandError):
            call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name, write_mode="dual")

    def test_business_code_no_longer_queries_genomefile_or_organism_fallback(self):
        checked_sources = {
            "file_relation_service": inspect.getsource(file_relation_service),
            "scan_files": inspect.getsource(scan_files),
            "accession_context": inspect.getsource(accession_context),
            "active_get_annotation_data": inspect.getsource(GenomeFileViewSet.get_annotation_data),
            "active_paginated_overview": inspect.getsource(GenomeFileViewSet.paginated_overview),
        }

        for name, source in checked_sources.items():
            self.assertNotIn("GenomeFile.objects", source, name)
            self.assertNotIn("organism_fallback", source, name)
            self.assertNotIn("legacy_organism", source, name)

    def test_validate_new_file_structure_still_passes(self):
        stdout = StringIO()

        call_command("validate_new_file_structure", output_dir=self.output_dir.name, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("result\tPASS", output)
        self.assertIn("legacy_fallback_count\t0", output)
        self.assertIn("organism_fallback_count\t0", output)
