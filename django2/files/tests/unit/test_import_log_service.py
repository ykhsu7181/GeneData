import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from files.services.import_log_service import build_import_stats


class ImportLogServiceTestCase(SimpleTestCase):
    def test_build_stats_includes_manifest_and_code_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.tsv"
            content = b"code\tvalue\nA\t1\n"
            manifest.write_bytes(content)

            with patch(
                "files.services.import_log_service.current_code_commit",
                return_value="abc123",
            ):
                stats = build_import_stats(
                    command="test_import",
                    input_path=str(manifest),
                    dry_run=True,
                    started_at="2026-01-01T00:00:00",
                    finished_at="2026-01-01T00:00:01",
                    scanned_count=1,
                    batch_id="batch-1",
                    source="lab",
                    source_version="v2",
                )

        self.assertEqual(stats["batch_id"], "batch-1")
        self.assertEqual(stats["source"], "lab")
        self.assertEqual(stats["source_version"], "v2")
        self.assertEqual(stats["manifest_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(stats["code_commit"], "abc123")
        self.assertTrue(stats["dry_run"])
