import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation
from files.services.fasta_statistics_service import calculate_fasta_statistics


class FastaStatisticsServiceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.fasta_path = Path(self.temp_dir.name) / "genome.TEST.fasta"
        self.fasta_path.write_text(
            ">chr1 description\nACGTNN\nNNAC\n>chr2\nGGNTA\n",
            encoding="utf-8",
        )

    def test_calculates_streaming_assembly_statistics(self):
        statistics = calculate_fasta_statistics(self.fasta_path)

        self.assertEqual(statistics["genome_size"], 15)
        self.assertEqual(statistics["n50"], 10)
        self.assertEqual(statistics["gc_content"], Decimal("50.000"))
        self.assertEqual(statistics["at_content"], Decimal("50.000"))
        self.assertEqual(statistics["n_count"], 5)
        self.assertEqual(statistics["n_percentage"], Decimal("33.333"))
        self.assertEqual(statistics["sequence_count"], 2)
        self.assertEqual(statistics["gap_count"], 2)
        self.assertEqual(
            statistics["sequence_md5"],
            hashlib.md5(b"ACGTNNNNAC\nGGNTA\n").hexdigest(),
        )

    def test_rejects_sequence_data_before_the_first_header(self):
        invalid_path = Path(self.temp_dir.name) / "invalid.fasta"
        invalid_path.write_text("ACGT\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "before first header"):
            calculate_fasta_statistics(invalid_path)

    def test_backfill_command_fills_blanks_without_overwriting_curated_values(self):
        accession = Accession.objects.create(accession="TEST")
        assembly = Assembly.objects.create(
            accession=accession,
            name="default",
            genome_size=999,
        )
        data_file = DataFile.objects.create(
            file_code="TEST_FASTA",
            file_name=self.fasta_path.name,
            file_path=str(self.fasta_path),
            is_current=True,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(assembly.id),
            file_role="genome_fasta",
            is_primary=True,
        )

        call_command("backfill_assembly_fasta_statistics", assembly_id=[assembly.id])

        assembly.refresh_from_db()
        self.assertEqual(assembly.genome_size, 999)
        self.assertEqual(assembly.n50, 10)
        self.assertEqual(assembly.gc_content, Decimal("50.000"))
        self.assertEqual(assembly.sequence_count, 2)
        self.assertEqual(assembly.gap_count, 2)
