import os
import tempfile
import uuid

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation, FileType, Species


class GenomeTranscriptomeReadinessCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            species=self.species,
            accession=f"IR64_{self.suffix}",
        )
        self.file_type = FileType.objects.create(
            code=f"FASTA_{self.suffix}",
            name="FASTA",
            extension="fa",
        )
        self.data_file = DataFile.objects.create(
            file_code=f"FILE_{self.suffix}",
            file_type=self.file_type,
            file_name="genome.fa",
            file_path=os.path.join(self.temp_dir.name, "genome.fa"),
            file_size=2048,
        )
        self.accession_relation = FileRelation.objects.create(
            file=self.data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome_fasta",
            is_primary=True,
        )

    def test_audit_readiness_reports_missing_assembly_without_writing_database(self):
        before_counts = self._counts()
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command("audit_genome_transcriptome_readiness", output_dir=output_dir)

        self.assertEqual(before_counts, self._counts())
        reports = os.listdir(output_dir)
        self.assertTrue(any(name.startswith("genome_transcriptome_readiness_") and name.endswith(".txt") for name in reports))
        detail_reports = [
            name
            for name in reports
            if name.startswith("genome_transcriptome_readiness_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(detail_reports), 1)
        with open(os.path.join(output_dir, detail_reports[0]), encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("has accession-level genome FileRelation but no Assembly", content)

    def test_backfill_dry_run_does_not_create_assembly_or_relation(self):
        before_counts = self._counts()
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command(
            "backfill_assembly_from_genome_relations",
            dry_run=True,
            output_dir=output_dir,
        )

        self.assertEqual(before_counts, self._counts())
        log_file = self._single_report(output_dir, "backfill_assembly_from_genome_relations_log_", ".txt")
        with open(log_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("created_assembly_count: 0", content)
        self.assertIn("created_filerelation_count: 0", content)
        self.assertIn("metadata_pending_count: 1", content)

    def test_backfill_default_does_not_create_placeholder(self):
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command("backfill_assembly_from_genome_relations", output_dir=output_dir)

        self.assertFalse(Assembly.objects.filter(accession=self.accession).exists())
        self.assertFalse(FileRelation.objects.filter(related_type="assembly").exists())
        report = self._single_report(
            output_dir,
            "backfill_assembly_from_genome_relations_unmapped_",
            ".tsv",
        )
        with open(report, encoding="utf-8") as handle:
            self.assertIn("metadata_pending", handle.read())

    def test_allow_placeholder_creates_default_assembly_and_assembly_relation(self):
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command(
            "backfill_assembly_from_genome_relations",
            output_dir=output_dir,
            assembly_level="Chromosome",
            allow_placeholder=True,
        )

        assembly = Assembly.objects.get(accession=self.accession, name="default")
        self.assertTrue(assembly.is_default)
        self.assertEqual(assembly.display_name, f"{self.accession.accession} default assembly")
        self.assertIn("Chromosome", assembly.description)
        relation = FileRelation.objects.get(
            file=self.data_file,
            related_type="assembly",
            related_id=str(assembly.id),
            file_role="genome_fasta",
        )
        self.assertTrue(relation.is_primary)
        self.assertEqual(relation.related_code, assembly.display_name)

    def test_backfill_is_idempotent(self):
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command(
            "backfill_assembly_from_genome_relations",
            output_dir=output_dir,
            allow_placeholder=True,
        )
        first_counts = self._counts()
        call_command(
            "backfill_assembly_from_genome_relations",
            output_dir=output_dir,
            allow_placeholder=True,
        )

        self.assertEqual(first_counts, self._counts())
        self.assertEqual(Assembly.objects.filter(accession=self.accession).count(), 1)
        self.assertEqual(
            FileRelation.objects.filter(
                file=self.data_file,
                related_type="assembly",
                file_role="genome_fasta",
            ).count(),
            1,
        )

    def test_backfill_reuses_existing_default_assembly(self):
        assembly = Assembly.objects.create(
            accession=self.accession,
            name="curated-v1",
            display_name="Curated v1",
            is_default=True,
        )

        call_command("backfill_assembly_from_genome_relations", output_dir=self.temp_dir.name)

        self.assertEqual(Assembly.objects.filter(accession=self.accession).count(), 1)
        self.assertTrue(
            FileRelation.objects.filter(
                file=self.data_file,
                related_type="assembly",
                related_id=str(assembly.id),
                file_role="genome_fasta",
            ).exists()
        )

    def test_backfill_reports_invalid_accession_related_id(self):
        invalid_file = DataFile.objects.create(
            file_code=f"FILE_INVALID_{self.suffix}",
            file_type=self.file_type,
            file_name="invalid.fa",
            file_path=os.path.join(self.temp_dir.name, "invalid.fa"),
            file_size=512,
        )
        FileRelation.objects.create(
            file=invalid_file,
            related_type="accession",
            related_id="not-a-number",
            related_code="BROKEN",
            file_role="genome_fasta",
        )
        output_dir = tempfile.mkdtemp(dir=self.temp_dir.name)

        call_command("backfill_assembly_from_genome_relations", dry_run=True, output_dir=output_dir)

        unmapped_file = self._single_report(
            output_dir,
            "backfill_assembly_from_genome_relations_unmapped_",
            ".tsv",
        )
        with open(unmapped_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("not-a-number", content)
        self.assertIn("accession related_id is not numeric", content)

    def _counts(self):
        return {
            "accession": Accession.objects.count(),
            "assembly": Assembly.objects.count(),
            "data_file": DataFile.objects.count(),
            "file_relation": FileRelation.objects.count(),
        }

    def _single_report(self, output_dir, prefix, suffix):
        reports = [
            os.path.join(output_dir, name)
            for name in os.listdir(output_dir)
            if name.startswith(prefix) and name.endswith(suffix)
        ]
        self.assertEqual(len(reports), 1)
        return reports[0]
