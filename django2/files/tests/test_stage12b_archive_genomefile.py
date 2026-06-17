import inspect
import os
import tempfile
import uuid
from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from files.admin import GenomeFileAdmin
import files.views as file_views
from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services.file_relation_service import get_files_for_accession
from files.views import GenomeFileViewSet


class Stage12BArchiveGenomeFileTestCase(TransactionTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.accession_code = f"IR64_{self.suffix}"
        self.file_type = FileType.objects.create(
            name=f"FASTA_STAGE12B_{self.suffix}",
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
            file_code=f"ST12B{self.suffix}{code_suffix}",
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

    def create_genome_file(self, filename="legacy.fasta", file_path=None):
        file_path = file_path or self.create_disk_file(filename)
        return GenomeFile.objects.create(
            name=filename,
            organism=self.accession_code,
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="genome",
            file_path=file_path,
            file_type=self.file_type,
            size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        )

    def assert_archived_response(self, response):
        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertTrue(payload["archived"])
        self.assertIn("GenomeFile", payload["message"])
        self.assertIn("DataFile", payload["message"])

    def test_genomefile_table_still_exists_as_archive(self):
        genome_file = self.create_genome_file("archive.exists.fasta")

        self.assertEqual(GenomeFile.objects.filter(id=genome_file.id).count(), 1)

    def test_file_relation_service_does_not_return_legacy_sources(self):
        self.create_genome_file("legacy.only.fasta")

        self.assertEqual(get_files_for_accession(self.accession.id), [])

        data_file = self.create_data_file("A", f"genome.{self.accession_code}.fasta")
        self.add_relation(data_file, "accession", self.accession.id, "genome")
        files = get_files_for_accession(self.accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertNotIn("legacy_genomefile", str(files))
        self.assertNotIn("organism_fallback", str(files))

    def test_business_interfaces_do_not_return_genomefile_download(self):
        genome_data_file = self.create_data_file("B", f"genome.{self.accession_code}.fasta")
        self.add_relation(genome_data_file, "accession", self.accession.id, "genome")
        annotation_content = (
            b"##gff-version 3\n"
            b"chr1\tsource\tgene\t1\t10\t.\t+\t.\tID=gene1\n"
        )
        annotation_data_file = self.create_data_file(
            "C",
            f"annotation.{self.accession_code}.gff3",
            content=annotation_content,
        )
        self.add_relation(annotation_data_file, "annotation", self.annotation.id, "annotation")

        accession_response = self.client.get(f"/gd/api/files/accessions/{self.accession_code}/")
        annotation_response = self.client.get(
            f"/gd/api/files/genome-files/get_annotation_data/?annotation_id={self.annotation.id}"
        )
        overview_response = self.client.get(
            "/gd/api/files/genome-files/paginated_overview/",
            {"search": self.accession_code},
        )

        self.assertEqual(accession_response.status_code, 200)
        self.assertEqual(annotation_response.status_code, 200)
        self.assertEqual(overview_response.status_code, 200)
        combined_payload = f"{accession_response.json()} {annotation_response.json()} {overview_response.json()}"
        self.assertIn("/data-files/", combined_payload)
        self.assertNotIn("/genome-files/", combined_payload)
        self.assertNotIn("legacy_genomefile", combined_payload)
        self.assertNotIn("organism_fallback", combined_payload)

    def test_scan_files_does_not_create_genomefile_or_support_legacy_dual(self):
        scan_dir = tempfile.TemporaryDirectory()
        self.addCleanup(scan_dir.cleanup)
        file_path = os.path.join(scan_dir.name, f"genome.{self.accession_code}.fasta")
        with open(file_path, "wb") as handle:
            handle.write(b">chr1\nATGC\n")
        normalized_path = os.path.abspath(os.path.normpath(file_path))

        call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name)

        self.assertTrue(DataFile.objects.filter(file_path=normalized_path).exists())
        self.assertTrue(
            FileRelation.objects.filter(
                related_type="accession",
                related_id=str(self.accession.id),
            ).exists()
        )
        self.assertFalse(GenomeFile.objects.filter(file_path=normalized_path).exists())
        with self.assertRaises(CommandError):
            call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name, write_mode="legacy")
        with self.assertRaises(CommandError):
            call_command("scan_files", path=scan_dir.name, output_dir=self.output_dir.name, write_mode="dual")

    def test_genomefile_viewset_crud_and_download_are_archived(self):
        genome_file = self.create_genome_file("archived.download.fasta")

        responses = [
            self.client.get("/gd/api/files/genome-files/"),
            self.client.get(f"/gd/api/files/genome-files/{genome_file.id}/"),
            self.client.post("/gd/api/files/genome-files/", {"name": "blocked"}),
            self.client.patch(
                f"/gd/api/files/genome-files/{genome_file.id}/",
                {"name": "blocked"},
                content_type="application/json",
            ),
            self.client.delete(f"/gd/api/files/genome-files/{genome_file.id}/"),
            self.client.get(f"/gd/api/files/genome-files/{genome_file.id}/download/"),
        ]

        for response in responses:
            self.assert_archived_response(response)
        self.assertTrue(GenomeFile.objects.filter(id=genome_file.id, name="archived.download.fasta").exists())

    def test_legacy_genomefile_custom_actions_are_archived(self):
        archived_urls = [
            "/gd/api/files/download-transcriptome/",
            "/gd/api/files/transcriptome-types/",
            "/gd/api/files/genome-files/get_tes/",
            "/gd/api/files/genome-files/get_centromere/",
            "/gd/api/files/genome-files/get_coreblocks/",
            "/gd/api/files/genome-files/get_variableblocks/",
            "/gd/api/files/genome-files/get_rna_data/",
            "/gd/api/files/genome-files/organisms/",
            "/gd/api/files/genome-files/organisms_with_annotation/",
            "/gd/api/files/genome-files/all_files/",
            "/gd/api/files/genome-files/paginated_transcriptome_overview/",
            "/gd/api/files/genome-files/get_codon_data/",
            "/gd/api/files/genome-files/categories/",
            "/gd/api/files/genome-files/sub_populations/",
        ]

        for url in archived_urls:
            with self.subTest(url=url):
                self.assert_archived_response(self.client.get(url))

    def test_legacy_genomefile_admin_apis_are_archived(self):
        genome_file = self.create_genome_file("admin.api.archive.fasta")
        archived_responses = [
            self.client.get("/gd/api/files/files/"),
            self.client.delete(f"/gd/api/files/files/{genome_file.id}/delete/"),
            self.client.post(
                "/gd/api/files/files/batch-delete/",
                {"file_ids": [genome_file.id]},
                content_type="application/json",
            ),
            self.client.post(
                "/gd/api/files/files/batch-download/",
                {"file_ids": [genome_file.id]},
                content_type="application/json",
            ),
            self.client.post("/gd/api/files/files/upload/"),
            self.client.get("/gd/api/files/statistics/"),
            self.client.post("/gd/api/files/rescan/"),
            self.client.get(
                f"/gd/api/files/data-management/download-file/{self.accession_code}/genome/"
            ),
        ]

        for response in archived_responses:
            self.assert_archived_response(response)
        self.assertTrue(GenomeFile.objects.filter(id=genome_file.id).exists())

    def test_active_archived_views_no_longer_query_genomefile_objects(self):
        checked_callables = {
            "download": GenomeFileViewSet.download,
            "download_transcriptome": GenomeFileViewSet.download_transcriptome,
            "get_tes": GenomeFileViewSet.get_tes,
            "get_centromere": GenomeFileViewSet.get_centromere,
            "get_coreblocks": GenomeFileViewSet.get_coreblocks,
            "get_variableblocks": GenomeFileViewSet.get_variableblocks,
            "get_rna_data": GenomeFileViewSet.get_rna_data,
            "organisms": GenomeFileViewSet.organisms,
            "organisms_with_annotation": GenomeFileViewSet.organisms_with_annotation,
            "all_files": GenomeFileViewSet.all_files,
            "transcriptome_types": GenomeFileViewSet.transcriptome_types,
            "paginated_transcriptome_overview": GenomeFileViewSet.paginated_transcriptome_overview,
            "categories": GenomeFileViewSet.categories,
            "scan_directory": GenomeFileViewSet.scan_directory,
            "admin_files_list": file_views.admin_files_list.__wrapped__,
            "admin_delete_file": file_views.admin_delete_file.__wrapped__,
            "admin_batch_delete": file_views.admin_batch_delete.__wrapped__,
            "admin_batch_download": file_views.admin_batch_download.__wrapped__,
            "admin_upload_file": file_views.admin_upload_file.__wrapped__,
            "admin_statistics": file_views.admin_statistics.__wrapped__,
            "admin_rescan_files": file_views.admin_rescan_files.__wrapped__,
            "admin_download_data_file": file_views.admin_download_data_file.__wrapped__,
        }

        for name, func in checked_callables.items():
            source = inspect.getsource(func)
            self.assertNotIn("GenomeFile.objects", source, name)
            self.assertNotIn("legacy_genomefile", source, name)
            self.assertNotIn("organism_fallback", source, name)

    def test_genomefile_admin_is_readonly_archive(self):
        admin_obj = GenomeFileAdmin(GenomeFile, AdminSite())
        genome_file = self.create_genome_file("admin.archive.fasta")

        self.assertFalse(admin_obj.has_add_permission(None))
        self.assertFalse(admin_obj.has_change_permission(None, genome_file))
        self.assertFalse(admin_obj.has_delete_permission(None, genome_file))
        readonly_fields = set(admin_obj.get_readonly_fields(None, genome_file))
        model_field_names = {field.name for field in GenomeFile._meta.fields}
        self.assertTrue(model_field_names.issubset(readonly_fields))
        self.assertEqual(admin_obj.archive_status(genome_file), "archived")

    def test_report_genomefile_archive_status_generates_readonly_report(self):
        genome_file = self.create_genome_file("archive.report.fasta")
        data_file = DataFile.objects.create(
            file_code=f"ST12B{self.suffix}R",
            file_name=genome_file.name,
            file_path=genome_file.file_path,
            file_size=genome_file.size,
        )
        self.add_relation(data_file, "accession", self.accession.id, "genome")
        before_counts = {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }
        stdout = StringIO()

        call_command("report_genomefile_archive_status", output_dir=self.output_dir.name, stdout=stdout)

        after_counts = {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }
        self.assertEqual(before_counts, after_counts)
        output = stdout.getvalue()
        self.assertIn("result\tPASS", output)
        self.assertIn("genomefile_total_count\t1", output)
        self.assertIn("genomefile_mapped_datafile_count\t1", output)
        self.assertIn("business_genomefile_download_return_count\t0", output)
        txt_reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("genomefile_archive_status_") and name.endswith(".txt")
        ]
        tsv_reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("genomefile_archive_status_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(txt_reports), 1)
        self.assertEqual(len(tsv_reports), 1)
        with open(os.path.join(self.output_dir.name, tsv_reports[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("genomefile_mapping", report)
        self.assertIn("archive.report.fasta", report)

    def test_validate_new_file_structure_still_passes(self):
        stdout = StringIO()

        call_command("validate_new_file_structure", output_dir=self.output_dir.name, stdout=stdout)

        self.assertIn("result\tPASS", stdout.getvalue())
