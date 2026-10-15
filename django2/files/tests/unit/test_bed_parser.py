from django.test import SimpleTestCase

from files.parsers.bed import parse_lines


class BedParserTests(SimpleTestCase):
    def test_parses_standard_bed_row(self):
        rows = parse_lines(["Chr01\t10\t20\tfeature-1\t8\t+\n"])

        self.assertEqual(
            rows[0],
            {
                "id": "Chr01:10-20:1",
                "seqid": "Chr01",
                "start": 10,
                "end": 20,
                "length": 10,
                "name": "feature-1",
                "score": "8",
                "strand": "+",
                "phase": None,
                "attributes": {},
            },
        )

    def test_parses_legacy_mirna_row_and_normalizes_reverse_coordinates(self):
        rows = parse_lines(
            ["MIR821\tRF00885\tChr01\t24655203\t24654929\t-\t278.0\t5.9e-57\n"]
        )

        self.assertEqual(rows[0]["seqid"], "Chr01")
        self.assertEqual(rows[0]["start"], 24654929)
        self.assertEqual(rows[0]["end"], 24655203)
        self.assertEqual(rows[0]["length"], 274)
        self.assertEqual(rows[0]["name"], "MIR821")
        self.assertEqual(rows[0]["score"], "278.0")
        self.assertEqual(rows[0]["strand"], "-")
        self.assertEqual(
            rows[0]["attributes"],
            {"rfam": "RF00885", "evalue": "5.9e-57"},
        )

    def test_skips_non_numeric_unknown_layout(self):
        self.assertEqual(parse_lines(["not\ta\tbed\trow\n"]), [])
