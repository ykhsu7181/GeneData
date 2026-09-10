import os
import tempfile

from django.test import SimpleTestCase

from files.parsers.archive import parse_feature_file
from files.parsers.fasta import build_sequence_aliases


class GenomeFeatureChromosomeAliasTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.fasta_path = self._write(
            "genome.fa",
            ">contig_01 OriSeqID=Chr01\nACGT\n",
        )
        self.gff_path = self._write(
            "annotation.gff",
            "contig_01\tsource\tgene\t1\t4\t.\t+\t.\tID=gene-1\n",
        )
        self.bed_path = self._write("features.bed", "contig_01\t0\t4\tfeature-1\n")

    def _write(self, filename, content):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def test_gff_and_bed_tracks_match_canonical_chromosome_id(self):
        aliases = build_sequence_aliases(self.fasta_path)

        gff_rows = parse_feature_file(self.gff_path, chromosome="Chr01", chromosome_aliases=aliases)
        bed_rows = parse_feature_file(self.bed_path, chromosome="Chr01", chromosome_aliases=aliases)

        self.assertEqual([row["seqid"] for row in gff_rows], ["Chr01"])
        self.assertEqual([row["seqid"] for row in bed_rows], ["Chr01"])
