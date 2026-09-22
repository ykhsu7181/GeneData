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
            for extension in ("fastq.gz", "fastaq.gz"):
                with self.subTest(tissue=tissue, extension=extension):
                    parsed = parse_ingestion_filename(
                        f"transcriptome.{tissue}.IR64.{extension}"
                    )
                    self.assertEqual(parsed["accession_code"], "IR64")
                    self.assertEqual(parsed["file_role"], f"transcriptome.{tissue}")

    def test_parses_telomere_and_fasta_index(self):
        telomere = parse_ingestion_filename("telomere.MH63.txt")
        self.assertEqual(telomere["accession_code"], "MH63")
        self.assertEqual(telomere["file_role"], "telomere")

        index = parse_ingestion_filename("genome.MH63.fasta.fai")
        self.assertEqual(index["accession_code"], "MH63")
        self.assertEqual(index["file_role"], "genome_index")
        self.assertEqual(index["extension"], "fasta.fai")

    def test_unknown_role_is_rejected(self):
        self.assertIsNone(parse_ingestion_filename("unknown.IR64.fasta"))
        with self.assertRaises(ValueError):
            validate_file_role("unknown")

    def test_registry_contains_phase_1a_roles(self):
        expected = {
            "genome", "genome_fasta", "genome_index", "annotation", "centromere",
            "telomere", "codon", "coreBlocks",
            "variableBlocks", "miRNA", "tRNA", "rRNA", "TEs",
            "transcriptome.all", "transcriptome.root", "transcriptome.stem",
            "transcriptome.leaf", "transcriptome.panicles", "transcriptome.shoot",
            "hifi_reads", "raw_reads_R1", "raw_reads_R2", "rnaseq_raw",
            "wgs_reads", "other",
        }
        self.assertEqual(CANONICAL_FILE_ROLES, expected)
