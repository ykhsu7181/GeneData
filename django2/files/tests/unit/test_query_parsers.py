import gzip
import io
import os
import tarfile
import tempfile
import zipfile

from django.test import SimpleTestCase

from files.parsers.archive import parse_feature_file, safe_extract_zip
from files.parsers.bed import parse_lines as parse_bed_lines
from files.parsers.codon import load_payload
from files.parsers.fasta import build_sequence_aliases, list_sequence_ids, parse_sequence_id, sequence_length
from files.parsers.gff import parse_lines as parse_gff_lines


class QueryParserTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def path(self, name):
        return os.path.join(self.temp_dir.name, name)

    def write(self, name, content):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def make_tar(self, name, members):
        path = self.path(name)
        with tarfile.open(path, "w:gz") as archive:
            for member_name, content in members.items():
                encoded = content.encode("utf-8")
                info = tarfile.TarInfo(member_name)
                info.size = len(encoded)
                archive.addfile(info, io.BytesIO(encoded))
        return path

    def test_fasta_parser_supports_gzip_aliases_and_lengths(self):
        path = self.path("genome.fa.gz")
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(">contig_01 description OriSeqID=Chr01\nACGT\n>Chr02\nAAC\n")

        self.assertEqual(parse_sequence_id(">contig_01 OriSeqID=Chr01"), "Chr01")
        self.assertEqual(build_sequence_aliases(path)["contig_01"], "Chr01")
        self.assertEqual(list_sequence_ids(path), ["Chr01", "Chr02"])
        self.assertEqual(sequence_length(path, "contig_01"), 4)
        self.assertIsNone(sequence_length(path, "missing"))

    def test_gff_and_bed_parsers_preserve_response_shape(self):
        aliases = {"contig_01": "Chr01", "Chr01": "Chr01"}
        gff = parse_gff_lines(
            ["contig_01\tsource\tgene\t1\t4\t.\t+\t.\tID=gene-1;Name=Gene 1\n"],
            chromosome="Chr01",
            chromosome_aliases=aliases,
        )
        bed = parse_bed_lines(
            ["contig_01\t0\t4\tfeature-1\n"],
            chromosome="Chr01",
            chromosome_aliases=aliases,
        )

        self.assertEqual(gff[0]["name"], "Gene 1")
        self.assertEqual(gff[0]["length"], 4)
        self.assertEqual(bed[0]["id"], "Chr01:0-4:1")
        self.assertEqual(bed[0]["length"], 4)

    def test_archive_parser_reads_feature_member(self):
        path = self.make_tar(
            "features.tar.gz",
            {"nested/features.gff3": "chr1\tsource\tgene\t1\t3\t.\t+\t.\tID=gene-1\n"},
        )

        rows = parse_feature_file(path, chromosome="chr1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attributes"], {"ID": "gene-1"})

    def test_codon_archive_parser_builds_existing_payload(self):
        path = self.make_tar(
            "codon.tar.gz",
            {
                "result/species.blk": "AUG10 1.00\nUUU5 0.50\n",
                "result/species.txt": "GC\tGenes\n45.5\t2\n",
            },
        )

        payload = load_payload(path, "IR64")

        self.assertEqual(payload["organism"], "IR64")
        self.assertEqual(payload["total_codons"], 15)
        self.assertEqual(payload["statistics"], {"GC": 45.5, "Genes": 2})

    def test_zip_parser_rejects_path_traversal(self):
        path = self.path("unsafe.zip")
        destination = self.path("extracted")
        os.makedirs(destination)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")

        with self.assertRaises(ValueError):
            safe_extract_zip(path, destination)

        self.assertFalse(os.path.exists(self.path("outside.txt")))
