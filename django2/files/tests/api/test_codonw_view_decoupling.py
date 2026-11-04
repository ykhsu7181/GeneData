import inspect
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework import viewsets
from rest_framework.test import APIClient

from files import codonw_views, views as file_views
from files.codonw_views import CodonWViewSet


class CodonWRouteCompatibilityTests(SimpleTestCase):
    routes = {
        "/gd/api/files/codonw/analysis/": {"post": "codonw_analysis"},
        "/gd/api/files/codonw/status/task-1/": {"get": "codonw_status"},
        "/gd/api/files/codonw/history/": {"get": "codonw_history"},
        "/gd/api/files/codonw/download/task-1/": {"get": "codonw_download"},
        "/gd/api/files/codonw/delete/task-1/": {"delete": "codonw_delete"},
        "/gd/api/files/codonw/results/task-1/": {"get": "codonw_results"},
        "/gd/api/files/codonw/result-upload/": {"post": "codonw_result_upload"},
    }

    def test_urls_and_http_method_mappings_are_unchanged(self):
        for path, actions in self.routes.items():
            with self.subTest(path=path):
                match = resolve(path)
                self.assertIs(match.func.cls, CodonWViewSet)
                self.assertEqual(
                    {
                        method: action
                        for method, action in match.func.actions.items()
                        if method != "head"
                    },
                    actions,
                )

    def test_permissions_keep_framework_defaults(self):
        self.assertEqual(
            CodonWViewSet.authentication_classes,
            viewsets.ViewSet.authentication_classes,
        )
        self.assertEqual(
            CodonWViewSet.permission_classes,
            viewsets.ViewSet.permission_classes,
        )


class CodonWResponseCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.scheduler_patch = patch.object(
            CodonWViewSet,
            "_start_cleanup_scheduler",
            autospec=True,
        )
        self.scheduler_patch.start()
        self.addCleanup(self.scheduler_patch.stop)
        CodonWViewSet._cleanup_scheduler_started = False
        self.addCleanup(setattr, CodonWViewSet, "_cleanup_scheduler_started", False)
        self.client = APIClient()

    def test_active_methods_keep_status_codes_and_key_response_shapes(self):
        checks = (
            ("post", "/gd/api/files/codonw/analysis/", 400, {"error"}),
            ("get", "/gd/api/files/codonw/status/missing/", 404, {"error"}),
            ("get", "/gd/api/files/codonw/history/", 400, {"error"}),
            ("get", "/gd/api/files/codonw/download/missing/", 404, {"error"}),
            ("delete", "/gd/api/files/codonw/delete/missing/", 400, {"error"}),
            ("get", "/gd/api/files/codonw/results/missing/", 404, {"error"}),
            (
                "post",
                "/gd/api/files/codonw/result-upload/",
                400,
                {"success", "message"},
            ),
        )
        for method, path, expected_status, expected_keys in checks:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(set(response.json()), expected_keys)

    def test_disallowed_methods_still_return_method_not_allowed(self):
        checks = (
            ("get", "/gd/api/files/codonw/analysis/"),
            ("post", "/gd/api/files/codonw/status/task-1/"),
            ("post", "/gd/api/files/codonw/history/"),
            ("post", "/gd/api/files/codonw/download/task-1/"),
            ("get", "/gd/api/files/codonw/delete/task-1/"),
            ("post", "/gd/api/files/codonw/results/task-1/"),
            ("get", "/gd/api/files/codonw/result-upload/"),
        )
        for method, path in checks:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 405)

    def test_history_response_structure_is_unchanged(self):
        tasks = [
            {
                "id": "task-1",
                "client_id": "client-1",
                "created_at": "2026-11-04T12:00:00",
                "status": "completed",
            }
        ]
        tasks_path = Path(self.temp_dir.name) / "codonw_tasks.json"
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        response = self.client.get(
            "/gd/api/files/codonw/history/",
            {"client_id": "client-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.json()["results"], tasks)

    def test_result_zip_upload_flow_and_response_are_unchanged(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
            handle.writestr("IR64_codon_usage.blk", "UUU10 1.0\nAUG5 0.5\n")
        upload = SimpleUploadedFile(
            "codonw-results.zip",
            archive.getvalue(),
            content_type="application/zip",
        )

        response = self.client.post(
            "/gd/api/files/codonw/result-upload/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {"success", "message", "data", "organism"},
        )
        self.assertTrue(payload["success"])
        self.assertEqual(payload["organism"], "IR64")
        self.assertEqual(
            set(payload["data"]),
            {
                "organism",
                "codon_usage",
                "amino_acids",
                "total_codons",
                "nucleotide_composition",
            },
        )


class CodonWDecouplingTests(SimpleTestCase):
    def test_new_view_has_no_genomefile_dependency(self):
        source = inspect.getsource(codonw_views)

        self.assertNotIn("GenomeFile", source)
        self.assertNotIn(
            "GenomeFileViewSet",
            {base.__name__ for base in CodonWViewSet.__mro__},
        )

    def test_retired_genomefile_viewset_is_not_present(self):
        self.assertFalse(hasattr(file_views, "GenomeFileViewSet"))
