import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genedata_cli.cli import build_parser, run
from genedata_cli.errors import SnapshotMismatchError
from genedata_cli.manifests import SELECTION_HEADERS


class FakeResponse(io.BytesIO):
    status = 200

    def getcode(self):
        return self.status


class FakeApiClient:
    origin = "https://example.test"

    def __init__(self, content, snapshot):
        self.content = content
        self.snapshot = snapshot
        self.posts = []
        self.opens = []

    def require_same_origin(self, value):
        if not value.startswith(self.origin + "/"):
            raise AssertionError("unexpected cross-origin URL")
        return value

    def post_json(self, path, payload, *, authenticated=True, headers=None):
        self.posts.append((path, payload, authenticated, headers))
        if path.endswith("/resolve/"):
            return {
                "summary": {"resolved": 1, "ambiguous": 0, "missing": 0, "blocked": 0},
                "resolved": self.snapshot["files"],
            }
        return {
            "batch_id": "batch_test",
            "snapshot_sha256": "b" * 64,
            "manifest_url": "/gd/api/v1/file-batches/batch_test/manifest/",
            "manifest_tsv_url": "/gd/api/v1/file-batches/batch_test/manifest.tsv",
        }

    def get_json(self, path, *, query=None, authenticated=False):
        return self.snapshot

    def get_bytes(self, path, *, authenticated=False):
        return b"position\tfile_code\n1\tFILE000013\n"

    def open(self, path, *, authenticated=False, range_start=None):
        self.opens.append((path, authenticated, range_start))
        return FakeResponse(self.content)


class CliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.selection = self.root / "selected-files.tsv"
        self.content = b">chr1\nACGT\n"
        digest = hashlib.sha256(self.content).hexdigest()
        self.selected_row = {
            "file_code": "FILE000013",
            "file_name": "genome.IR64.fasta",
            "accession": "IR64",
            "assembly": "ASM_IR64",
            "dataset": "DS_IR64",
            "role": "genome_fasta",
            "format": "FASTA",
            "size": str(len(self.content)),
            "sha256": digest,
            "content_url": "https://example.test/gd/api/v1/files/FILE000013/content/",
        }
        with self.selection.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SELECTION_HEADERS, dialect="excel-tab", lineterminator="\n")
            writer.writeheader()
            writer.writerow(self.selected_row)
        self.snapshot = {
            "batch_id": "batch_test",
            "snapshot_sha256": "b" * 64,
            "files": [{
                "position": 1,
                "file_code": "FILE000013",
                "file_name": "genome.IR64.fasta",
                "accession": "IR64",
                "assembly": "ASM_IR64",
                "size": len(self.content),
                "sha256": digest,
                "content_url": "/gd/api/v1/files/FILE000013/content/",
            }],
        }

    def test_manifest_workflow_submits_only_codes_and_writes_authoritative_evidence(self):
        fake = FakeApiClient(self.content, self.snapshot)
        output_dir = self.root / "cache"
        args = build_parser().parse_args([
            "--base-url", "https://example.test",
            "download", "manifest", str(self.selection),
            "--jobs", "1", "--output", str(output_dir),
        ])
        stdout = io.StringIO()

        with patch("genedata_cli.cli.ApiClient", return_value=fake):
            code = run(args, stdout=stdout)

        self.assertEqual(code, 0)
        self.assertEqual(fake.posts[0][0], "/gd/api/v1/file-batches/")
        self.assertEqual(fake.posts[0][1]["file_codes"], ["FILE000013"])
        self.assertNotIn("content_url", json.dumps(fake.posts[0][1]))
        self.assertTrue((output_dir / "batch-batch_test.json").is_file())
        self.assertTrue((output_dir / "batch_test.manifest.json").is_file())
        self.assertTrue((output_dir / "batch_test.manifest.tsv").is_file())
        self.assertTrue((output_dir / "download-report.tsv").is_file())
        self.assertTrue((output_dir / "IR64" / "ASM_IR64" / "genome.IR64.fasta").is_file())

    def test_preview_resolves_codes_without_creating_or_downloading_a_batch(self):
        fake = FakeApiClient(self.content, self.snapshot)
        args = build_parser().parse_args([
            "--base-url", "https://example.test",
            "download", "manifest", str(self.selection), "--preview",
        ])

        with patch("genedata_cli.cli.ApiClient", return_value=fake):
            code = run(args, stdout=io.StringIO())

        self.assertEqual(code, 0)
        self.assertEqual(fake.posts[0][0], "/gd/api/v1/file-batches/resolve/")
        self.assertEqual(fake.posts[0][1]["file_codes"], ["FILE000013"])
        self.assertEqual(fake.opens, [])

    def test_snapshot_change_stops_before_downloading_content(self):
        changed = json.loads(json.dumps(self.snapshot))
        changed["files"][0]["size"] += 1
        fake = FakeApiClient(self.content, changed)
        args = build_parser().parse_args([
            "--base-url", "https://example.test",
            "download", "manifest", str(self.selection),
            "--output", str(self.root / "cache"),
        ])

        with patch("genedata_cli.cli.ApiClient", return_value=fake):
            with self.assertRaisesRegex(SnapshotMismatchError, "authoritative snapshot"):
                run(args, stdout=io.StringIO())

        self.assertEqual(fake.opens, [])


if __name__ == "__main__":
    unittest.main()
