import inspect

from django.apps import apps
from django.test import TestCase

import files.views as file_views
from files.archive_views import ArchivedGenomeFileViewSet
from files.models import Accession, DataFile, FileRelation
from files.services.file_relation_service import get_files_for_accession


class FinalGenomeFileRetirementTests(TestCase):
    def assert_archived_response(self, response):
        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertTrue(payload["archived"])
        self.assertIn("GenomeFile", payload["message"])
        self.assertIn("DataFile", payload["message"])

    def test_genomefile_model_is_removed(self):
        with self.assertRaises(LookupError):
            apps.get_model("files", "GenomeFile")

    def test_datafile_filerelation_main_chain_remains_active(self):
        accession = Accession.objects.create(accession="FINAL_RETIREMENT")
        data_file = DataFile.objects.create(
            file_code="FINAL_RETIREMENT_FASTA",
            file_name="genome.final.fasta",
            file_path="/tmp/genome.final.fasta",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(accession.id),
            related_code=accession.accession,
            file_role="genome",
        )

        files = get_files_for_accession(accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_code"], data_file.file_code)
        self.assertEqual(files[0]["source"], "new_relation")

    def test_genomefile_crud_and_download_urls_remain_410(self):
        responses = [
            self.client.get("/gd/api/files/genome-files/"),
            self.client.get("/gd/api/files/genome-files/987654/"),
            self.client.post("/gd/api/files/genome-files/", {"name": "blocked"}),
            self.client.patch(
                "/gd/api/files/genome-files/987654/",
                {"name": "blocked"},
                content_type="application/json",
            ),
            self.client.delete("/gd/api/files/genome-files/987654/"),
            self.client.get("/gd/api/files/genome-files/987654/download/"),
        ]

        for response in responses:
            self.assert_archived_response(response)

    def test_custom_and_admin_legacy_urls_remain_410(self):
        urls = [
            "/gd/api/files/download-transcriptome/",
            "/gd/api/files/transcriptome-types/",
            "/gd/api/files/genome-files/get_tes/",
            "/gd/api/files/genome-files/get_annotation_data/",
            "/gd/api/files/genome-files/paginated_overview/",
            "/gd/api/files/genome-files/categories/",
            "/gd/api/files/files/",
            "/gd/api/files/statistics/",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assert_archived_response(self.client.get(url))
        self.assert_archived_response(self.client.post("/gd/api/files/rescan/"))

    def test_410_adapters_do_not_depend_on_genomefile_model(self):
        checked_callables = {
            "archive_viewset": ArchivedGenomeFileViewSet,
            "admin_files_list": file_views.admin_files_list.__wrapped__,
            "admin_statistics": file_views.admin_statistics.__wrapped__,
            "admin_rescan_files": file_views.admin_rescan_files.__wrapped__,
        }

        for name, obj in checked_callables.items():
            source = inspect.getsource(obj)
            self.assertNotIn("GenomeFile.objects", source, name)
            self.assertNotIn("from files.models import GenomeFile", source, name)
