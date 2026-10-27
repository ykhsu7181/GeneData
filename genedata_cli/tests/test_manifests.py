import csv
import tempfile
import unittest
from pathlib import Path

from genedata_cli.errors import InputError
from genedata_cli.manifests import (
    SELECTION_HEADERS,
    compare_selection_to_snapshot,
    read_selection_manifest,
)


class SelectionManifestTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "selected-files.tsv"

    def write(self, rows, headers=SELECTION_HEADERS):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers, dialect="excel-tab", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def row(code="FILE000013", **overrides):
        values = {
            "file_code": code,
            "file_name": "genome.IR64.fasta",
            "accession": "IR64",
            "assembly": "ASM_IR64",
            "dataset": "DS_IR64",
            "role": "genome_fasta",
            "format": "FASTA",
            "size": "11",
            "sha256": "a" * 64,
            "content_url": "https://example.test/gd/api/v1/files/%s/content/" % code,
        }
        values.update(overrides)
        return values

    def test_reads_utf8_bom_and_deduplicates_by_first_file_code(self):
        self.write([self.row(), self.row(file_name="ignored.fasta")])
        self.path.write_bytes(b"\xef\xbb\xbf" + self.path.read_bytes())

        rows = read_selection_manifest(self.path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_name"], "genome.IR64.fasta")
        self.assertEqual(rows[0]["size"], 11)

    def test_rejects_changed_header_and_invalid_integrity_fields(self):
        self.write([self.row()], headers=list(reversed(SELECTION_HEADERS)))
        with self.assertRaisesRegex(InputError, "invalid header"):
            read_selection_manifest(self.path)

        self.write([self.row(size="-1")])
        with self.assertRaisesRegex(InputError, "negative size"):
            read_selection_manifest(self.path)

        self.write([self.row(sha256="not-a-digest")])
        with self.assertRaisesRegex(InputError, "invalid SHA-256"):
            read_selection_manifest(self.path)

    def test_snapshot_comparison_detects_authoritative_changes(self):
        selected = [self.row()]
        snapshot = [{
            "file_code": "FILE000013",
            "file_name": "genome.IR64.fasta",
            "size": 12,
            "sha256": "a" * 64,
            "content_url": "/gd/api/v1/files/FILE000013/content/",
        }]

        differences = compare_selection_to_snapshot(selected, snapshot, base_url="https://example.test")

        self.assertEqual(differences, ["FILE000013 size changed"])


if __name__ == "__main__":
    unittest.main()
