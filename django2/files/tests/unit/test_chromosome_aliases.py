from django.test import SimpleTestCase

from files.parsers.bed import parse_lines as parse_bed_lines
from files.parsers.fasta import parse_sequence_id, resolve_sequence_alias
from files.parsers.gff import parse_lines as parse_gff_lines


class ChromosomeAliasTests(SimpleTestCase):
    def setUp(self):
        self.aliases = {
            "contig_01": "Chr01",
            "Chr01": "Chr01",
        }

    def test_fasta_parser_prefers_ori_sequence_id(self):
        self.assertEqual(
            parse_sequence_id(">contig_01 description OriSeqID=Chr01 source=assembly"),
            "Chr01",
        )

    def test_fasta_parser_uses_first_token_without_ori_sequence_id(self):
        self.assertEqual(parse_sequence_id(">Chr02 description"), "Chr02")

    def test_alias_resolver_accepts_raw_and_canonical_ids(self):
        self.assertEqual(resolve_sequence_alias("contig_01", self.aliases), "Chr01")
        self.assertEqual(resolve_sequence_alias("Chr01", self.aliases), "Chr01")

    def test_gff_filter_matches_raw_sequence_id_to_canonical_request(self):
        rows = parse_gff_lines(
            ["contig_01\tsource\tgene\t10\t20\t.\t+\t.\tID=gene-1\n"],
            chromosome="Chr01",
            chromosome_aliases=self.aliases,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seqid"], "Chr01")

    def test_bed_filter_matches_canonical_sequence_id_to_raw_request(self):
        rows = parse_bed_lines(
            ["Chr01\t10\t20\tfeature-1\n"],
            chromosome="contig_01",
            chromosome_aliases=self.aliases,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seqid"], "Chr01")
