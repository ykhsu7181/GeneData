from django.test import SimpleTestCase

from files.services.ingestion.file_parser import parse_ingestion_filename
from files.services.ingestion.roles import CANONICAL_FILE_ROLES, validate_file_role


class IngestionFileParserTestCase(SimpleTestCase):
    def test_parses_simple_accession(self):
        parsed = parse_ingestion_filename("annotation.IR64.gff")
        self.assertEqual(parsed["accession_code"], "IR64")
        self.assertEqual(parsed["file_role"], "annotation")

    def test_preserves_dots_in_accession(self):
        for filename in (
            "genome.Nanoay P.A.fasta",
            "annotation.Nanoay P.A.gff",
        ):
            with self.subTest(filename=filename):
                parsed = parse_ingestion_filename(filename)
                self.assertEqual(parsed["accession_code"], "Nanoay P.A")

    def test_parses_dotted_transcriptome_roles(self):
        for tissue in ("root", "leaf"):
            parsed = parse_ingestion_filename(f"transcriptome.{tissue}.IR64.fastq.gz")
            self.assertEqual(parsed["accession_code"], "IR64")
            self.assertEqual(parsed["file_role"], f"transcriptome.{tissue}")

    def test_unknown_role_is_rejected(self):
        self.assertIsNone(parse_ingestion_filename("unknown.IR64.fasta"))
        with self.assertRaises(ValueError):
            validate_file_role("unknown")

    def test_registry_contains_phase_1a_roles(self):
        expected = {
            "genome", "annotation", "centromere", "codon", "coreBlocks",
            "variableBlocks", "miRNA", "tRNA", "rRNA", "TEs",
            "transcriptome.all", "transcriptome.root", "transcriptome.stem",
            "transcriptome.leaf", "transcriptome.panicles", "transcriptome.shoot",
            "hifi_reads", "raw_reads_R1", "raw_reads_R2", "rnaseq_raw",
            "wgs_reads", "other",
        }
        self.assertEqual(CANONICAL_FILE_ROLES, expected)
