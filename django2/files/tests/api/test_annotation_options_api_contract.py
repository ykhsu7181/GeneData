import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from files.query_views import query_annotation_data, query_annotation_options


class AnnotationOptionsApiContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".gff3", delete=False)
        self.temp_file.close()
        self.addCleanup(lambda: os.path.exists(self.temp_file.name) and os.unlink(self.temp_file.name))
        self.context = (
            "IR64",
            SimpleNamespace(accession="IR64"),
            SimpleNamespace(id=3),
            SimpleNamespace(id=7),
        )
        self.service_file = {"id": 11, "file_path": self.temp_file.name}
        self.rows = [
            {"seqid": "chr1", "feature": "gene"},
            {"seqid": "chr1", "feature": "mRNA"},
            {"seqid": "chr2", "feature": "gene"},
        ]

    @patch("files.query_views._build_context_chromosome_aliases", return_value={})
    @patch("files.query_views._parse_feature_file")
    @patch("files.query_views.get_files_for_annotation")
    @patch("files.query_views.get_context_organism")
    def test_options_return_full_filter_metadata(
        self,
        get_context_organism,
        get_files_for_annotation,
        parse_feature_file,
        _build_aliases,
    ):
        get_context_organism.return_value = self.context
        get_files_for_annotation.return_value = [self.service_file]
        parse_feature_file.return_value = self.rows

        response = query_annotation_options(
            self.factory.get("/query/annotation-options/", {"annotation_id": 7})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["annotation_id"], 7)
        self.assertEqual(response.data["chromosomes"], ["chr1", "chr2"])
        self.assertEqual(response.data["feature_types"], ["gene", "mRNA"])
        self.assertEqual(response.data["summary"], {
            "total_features": 3,
            "chromosome_count": 2,
            "feature_type_count": 2,
        })

    @patch("files.query_views._adapt_annotation_file_service_result", return_value={"id": 11})
    @patch("files.query_views._build_context_chromosome_aliases", return_value={})
    @patch("files.query_views._parse_feature_file")
    @patch("files.query_views.get_files_for_annotation")
    @patch("files.query_views.get_context_organism")
    def test_data_marks_statistics_as_filtered(
        self,
        get_context_organism,
        get_files_for_annotation,
        parse_feature_file,
        _build_aliases,
        _adapt_file,
    ):
        get_context_organism.return_value = self.context
        get_files_for_annotation.return_value = [self.service_file]
        parse_feature_file.return_value = [self.rows[1]]

        response = query_annotation_data(
            self.factory.get(
                "/query/annotation-data/",
                {"annotation_id": 7, "chromosome": "chr1", "feature_type": "mRNA"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["filtered_count"], 1)
        self.assertEqual(response.data["filtered_statistics"], {
            "chromosomes": ["chr1"],
            "feature_types": ["mRNA"],
            "total_features": 1,
        })
        self.assertEqual(response.data["statistics"], response.data["filtered_statistics"])
