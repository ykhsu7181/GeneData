import inspect

from django.test import SimpleTestCase

from files import archive_views, download_views, query_views
from files.management.commands import report_genomefile_archive_status
from files.services import accession_context, data_overview_service, transcriptome_list_service


class StageBQueryBoundaryTests(SimpleTestCase):
    def test_query_view_has_no_embedded_format_or_archive_parser(self):
        source = inspect.getsource(query_views)

        for forbidden in (
            "def _parse_gff_lines",
            "def _parse_bed_lines",
            "def _parse_fasta_sequence_id",
            "def _parse_feature_file",
            "import tarfile",
            "import gzip",
            "from files.views import",
        ):
            self.assertNotIn(forbidden, source)

    def test_active_query_modules_do_not_use_genomefile_objects(self):
        modules = (
            query_views,
            archive_views,
            download_views,
            accession_context,
            data_overview_service,
            transcriptome_list_service,
        )

        for module in modules:
            self.assertNotIn("GenomeFile.objects", inspect.getsource(module), module.__name__)

    def test_context_services_do_not_guess_related_first(self):
        source = inspect.getsource(accession_context)

        self.assertNotIn("assemblies.first()", source)
        self.assertNotIn("annotations.first()", source)
        self.assertIn("AmbiguousContextError", source)

    def test_legacy_adapter_is_always_gone(self):
        source = inspect.getsource(archive_views.ArchivedGenomeFileViewSet)

        self.assertIn("HTTP_410_GONE", source)
        self.assertNotIn("GenomeFile.objects", source)

    def test_archive_report_audits_active_query_modules(self):
        source = inspect.getsource(report_genomefile_archive_status.Command)

        self.assertIn("inspect.getsource(query_views)", source)
        self.assertIn("inspect.getsource(query_view_helpers)", source)
        self.assertNotIn("inspect.getsource(ArchivedGenomeFileViewSet.get_annotation_data)", source)
