import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from genedata_cli.downloader import download_batch, download_single
from genedata_cli.errors import InputError


class FakeResponse(io.BytesIO):
    def __init__(self, content, status):
        super().__init__(content)
        self.status = status

    def getcode(self):
        return self.status


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def open(self, url, *, authenticated, range_start=None):
        self.calls.append((url, authenticated, range_start))
        start = range_start or 0
        return FakeResponse(self.content[start:], 206 if start else 200)


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.content = b">chr1\nACGT\n"
        self.item = {
            "file_code": "FILE000013",
            "file_name": "genome.IR64.fasta",
            "accession": "IR64",
            "assembly": "ASM_IR64",
            "size": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
            "content_url": "/gd/api/v1/files/FILE000013/content/",
        }

    def test_resumes_partial_download_and_then_uses_verified_cache(self):
        target = self.root / "IR64" / "ASM_IR64" / "genome.IR64.fasta"
        target.parent.mkdir(parents=True)
        target.with_name(target.name + ".part").write_bytes(self.content[:4])
        client = FakeClient(self.content)

        first = download_batch(client, [self.item], self.root, jobs=1)
        second = download_batch(client, [self.item], self.root, jobs=1)

        self.assertEqual(first[0]["status"], "downloaded")
        self.assertEqual(second[0]["status"], "cached")
        self.assertEqual(target.read_bytes(), self.content)
        self.assertEqual(client.calls, [(self.item["content_url"], True, 4)])

    def test_rejects_manifest_path_traversal(self):
        client = FakeClient(self.content)
        invalid = {**self.item, "file_name": "../secret.fasta"}

        with self.assertRaisesRegex(InputError, "invalid file_name"):
            download_batch(client, [invalid], self.root, jobs=1)

    def test_completes_a_fully_received_partial_without_another_request(self):
        target = self.root / "IR64" / "ASM_IR64" / "genome.IR64.fasta"
        target.parent.mkdir(parents=True)
        target.with_name(target.name + ".part").write_bytes(self.content)
        client = FakeClient(self.content)

        reports = download_batch(client, [self.item], self.root, jobs=1)

        self.assertEqual(reports[0]["status"], "downloaded")
        self.assertEqual(client.calls, [])
        self.assertEqual(target.read_bytes(), self.content)

    def test_single_public_file_download_is_anonymous(self):
        client = FakeClient(self.content)

        report = download_single(client, self.item, self.root)

        self.assertEqual(report["status"], "downloaded")
        self.assertEqual(client.calls, [(self.item["content_url"], False, 0)])


if __name__ == "__main__":
    unittest.main()
