import csv
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from genedata_cli.manifests import SELECTION_HEADERS


FILES = {
    "FILE_FASTA": {
        "file_name": "genome.IR64.fasta",
        "accession": "IR64",
        "assembly": "ASM_IR64",
        "role": "genome_fasta",
        "format": "FASTA",
        "content": b">Chr01\nAACCTTGG\n",
    },
    "FILE_FAI": {
        "file_name": "genome.IR64.fasta.fai",
        "accession": "IR64",
        "assembly": "ASM_IR64",
        "role": "genome_index",
        "format": "FAI",
        "content": b"Chr01\t8\t7\t8\t9\n",
    },
    "FILE_INTERRUPTED": {
        "file_name": "interrupted.txt",
        "accession": "IR64",
        "assembly": "ASM_IR64",
        "role": "other",
        "format": "TXT",
        "content": b"resume-this-transfer",
    },
    "FILE_BADSHA": {
        "file_name": "bad-sha.txt",
        "accession": "IR64",
        "assembly": "ASM_IR64",
        "role": "other",
        "format": "TXT",
        "content": b"server-content",
        "advertised_sha256": "0" * 64,
    },
}


def file_payload(code, origin):
    item = FILES[code]
    return {
        "file_code": code,
        "file_name": item["file_name"],
        "accession": item["accession"],
        "accessions": [item["accession"]],
        "assembly": item["assembly"],
        "assemblies": [item["assembly"]],
        "dataset": "DS_TEST",
        "datasets": ["DS_TEST"],
        "role": item["role"],
        "roles": [item["role"]],
        "format": item["format"],
        "size": len(item["content"]),
        "sha256": item.get("advertised_sha256", hashlib.sha256(item["content"]).hexdigest()),
        "content_url": "%s/gd/api/v1/files/%s/content/" % (origin, code),
    }


class GeneDataHandler(BaseHTTPRequestHandler):
    server_version = "GeneDataMock/1.0"

    def log_message(self, format_string, *args):
        return

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.server.server_port

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/gd/api/v1/files/":
            marker = query.get("name_contains", [""])[0]
            if marker == "unauthorized":
                return self.json_error(401, "authentication_required")
            if marker == "forbidden":
                return self.json_error(403, "insufficient_scope")
            if marker == "limited":
                return self.json_error(429, "throttled", {"Retry-After": "2"})
            results = [file_payload(code, self.origin) for code in ("FILE_FASTA", "FILE_FAI")]
            return self.json_response({"count": len(results), "page": 1, "page_size": 100, "results": results})

        parts = parsed.path.strip("/").split("/")
        if len(parts) in (5, 6) and parts[:4] == ["gd", "api", "v1", "files"]:
            code = parts[4]
            if code not in FILES:
                return self.json_error(404, "not_found")
            if len(parts) == 5:
                return self.json_response(file_payload(code, self.origin))
            if parts[5] == "content":
                return self.file_response(code)

        if parsed.path == "/gd/api/v1/file-batches/batch_test/manifest/":
            if not self.authorized():
                return self.json_error(401, "authentication_required")
            files = [self.batch_item(code, position) for position, code in enumerate(self.server.batch_codes, 1)]
            return self.json_response({
                "batch_id": "batch_test",
                "snapshot_sha256": "b" * 64,
                "files": files,
            })
        if parsed.path == "/gd/api/v1/file-batches/batch_test/manifest.tsv":
            if not self.authorized():
                return self.json_error(401, "authentication_required")
            body = "position\tfile_code\n" + "".join(
                "%d\t%s\n" % (position, code)
                for position, code in enumerate(self.server.batch_codes, 1)
            )
            return self.bytes_response(200, body.encode("utf-8"), "text/tab-separated-values")
        return self.json_error(404, "not_found")

    def do_POST(self):
        if self.headers.get("Authorization") == "Bearer gdt_expired":
            return self.json_error(401, "invalid_token")
        if self.headers.get("Authorization") != "Bearer gdt_test":
            return self.json_error(403, "insufficient_scope")
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        codes = payload.get("file_codes") or []
        if "FILE_CONFLICT" in codes:
            return self.json_error(409, "strict_resolution_failed")
        if "FILE_LIMITED" in codes:
            return self.json_error(429, "throttled", {"Retry-After": "2"})
        if any(code not in FILES for code in codes):
            return self.json_error(409, "strict_resolution_failed")
        resolution = {
            "summary": {
                "resolved": len(codes), "ambiguous": 0, "missing": 0,
                "blocked": 0, "total_size": sum(len(FILES[code]["content"]) for code in codes),
            },
            "resolved": [file_payload(code, self.origin) for code in codes],
            "ambiguous": [], "missing": [], "blocked": [],
        }
        if self.path == "/gd/api/v1/file-batches/resolve/":
            return self.json_response(resolution)
        if self.path == "/gd/api/v1/file-batches/":
            self.server.batch_codes = list(codes)
            return self.json_response({
                "batch_id": "batch_test",
                "snapshot_sha256": "b" * 64,
                "manifest_url": "/gd/api/v1/file-batches/batch_test/manifest/",
                "manifest_tsv_url": "/gd/api/v1/file-batches/batch_test/manifest.tsv",
            }, status=201)
        return self.json_error(404, "not_found")

    def authorized(self):
        return self.headers.get("Authorization") == "Bearer gdt_test"

    def batch_item(self, code, position):
        item = file_payload(code, self.origin)
        item["position"] = position
        return item

    def file_response(self, code):
        content = FILES[code]["content"]
        range_header = self.headers.get("Range")
        start = 0
        status = 200
        if range_header:
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            status = 206
        body = content[start:]
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(content) - 1, len(content)))
        self.end_headers()
        if code == "FILE_INTERRUPTED" and not range_header and not self.server.interrupted_once:
            self.server.interrupted_once = True
            halfway = max(1, len(body) // 2)
            self.wfile.write(body[:halfway])
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            return
        self.wfile.write(body)

    def json_error(self, status, code, headers=None):
        return self.json_response({"detail": code, "code": code}, status=status, headers=headers)

    def json_response(self, payload, status=200, headers=None):
        return self.bytes_response(
            status,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            "application/json",
            headers,
        )

    def bytes_response(self, status, body, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(
    os.environ.get("GENEDATA_RUN_INSTALLED_INTEGRATION") == "1",
    "requires an installed genedata wheel",
)
class InstalledCliHttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), GeneDataHandler)
        cls.httpd.batch_codes = []
        cls.httpd.interrupted_once = False
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = "http://127.0.0.1:%d" % cls.httpd.server_port

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def run_cli(self, *arguments, token=None):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["GENEDATA_BASE_URL"] = self.origin
        if token is None:
            environment.pop("GENEDATA_TOKEN", None)
        else:
            environment["GENEDATA_TOKEN"] = token
        return subprocess.run(
            [sys.executable, "-m", "genedata_cli", *map(str, arguments)],
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def write_selection(self, codes, name="selected-files.tsv"):
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SELECTION_HEADERS, dialect="excel-tab", lineterminator="\n")
            writer.writeheader()
            for code in codes:
                item = file_payload(code, self.origin) if code in FILES else {
                    "file_code": code,
                    "file_name": "%s.dat" % code,
                    "accession": "", "assembly": "", "dataset": "", "role": "", "format": "",
                    "size": 1, "sha256": "a" * 64,
                    "content_url": "%s/gd/api/v1/files/%s/content/" % (self.origin, code),
                }
                writer.writerow({key: item.get(key, "") for key in SELECTION_HEADERS})
        return path

    def test_help_search_show_and_anonymous_single_download(self):
        self.assertEqual(self.run_cli("--help").returncode, 0)
        search = self.run_cli("search", "files", "--accession", "IR64", "--format", "FASTA")
        show = self.run_cli("show", "FILE_FASTA")
        download = self.run_cli("download", "FILE_FASTA", "--output", self.root / "single")

        self.assertEqual(search.returncode, 0, search.stderr)
        self.assertEqual(json.loads(search.stdout)["count"], 2)
        self.assertEqual(show.returncode, 0, show.stderr)
        self.assertEqual(json.loads(show.stdout)["file_code"], "FILE_FASTA")
        self.assertEqual(download.returncode, 0, download.stderr)
        self.assertEqual((self.root / "single" / "genome.IR64.fasta").read_bytes(), FILES["FILE_FASTA"]["content"])

    def test_preview_and_authoritative_batch_download_fasta_with_fai(self):
        selection = self.write_selection(["FILE_FASTA", "FILE_FAI"])
        preview = self.run_cli("download", "manifest", selection, "--preview", token="gdt_test")
        output_dir = self.root / "batch-output"
        download = self.run_cli(
            "download", "manifest", selection, "--jobs", "2", "--output", output_dir,
            token="gdt_test",
        )

        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["summary"]["resolved"], 2)
        self.assertEqual(download.returncode, 0, download.stderr)
        analysis_dir = output_dir / "IR64" / "ASM_IR64"
        self.assertTrue((analysis_dir / "genome.IR64.fasta").is_file())
        self.assertTrue((analysis_dir / "genome.IR64.fasta.fai").is_file())
        self.assertTrue((output_dir / "batch_test.manifest.json").is_file())
        self.assertTrue((output_dir / "download-report.tsv").is_file())

    def test_range_resume_after_interrupted_response(self):
        self.httpd.interrupted_once = False
        output_dir = self.root / "resume"
        first = self.run_cli("download", "FILE_INTERRUPTED", "--output", output_dir)

        self.assertEqual(first.returncode, 6, first.stderr)
        self.assertTrue(
            (output_dir / "interrupted.txt.part").is_file(),
            "stderr=%r files=%r" % (first.stderr, list(output_dir.glob("**/*"))),
        )
        second = self.run_cli("download", "FILE_INTERRUPTED", "--output", output_dir)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((output_dir / "interrupted.txt").read_bytes(), FILES["FILE_INTERRUPTED"]["content"])

    def test_checksum_mismatch_is_retained_as_partial_and_fails(self):
        output_dir = self.root / "bad-sha"
        result = self.run_cli("download", "FILE_BADSHA", "--output", output_dir)

        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertFalse((output_dir / "bad-sha.txt").exists())
        self.assertTrue((output_dir / "bad-sha.txt.part").exists())

    def test_http_errors_have_stable_exit_code_and_do_not_echo_token(self):
        for marker, expected_code in (
            ("unauthorized", "authentication_required"),
            ("forbidden", "insufficient_scope"),
            ("limited", "throttled"),
        ):
            with self.subTest(marker=marker):
                result = self.run_cli("search", "files", "--name-contains", marker, token="secret-token")
                self.assertEqual(result.returncode, 3)
                self.assertIn(expected_code, result.stderr)
                self.assertNotIn("secret-token", result.stderr + result.stdout)

        conflict = self.write_selection(["FILE_CONFLICT"], "conflict.tsv")
        result = self.run_cli("download", "manifest", conflict, token="gdt_test")
        self.assertEqual(result.returncode, 3)
        self.assertIn("strict_resolution_failed", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
