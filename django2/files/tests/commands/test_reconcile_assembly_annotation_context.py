import os
import tempfile
import uuid

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, Species


class ReconcileAssemblyAnnotationContextCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        suffix = uuid.uuid4().hex[:8].upper()
        self.species = Species.objects.create(
            species_code=f"SPECIES_{suffix}",
            chinese_name="测试物种",
            scientific_name="Test species",
        )
        self.accession = Accession.objects.create(species=self.species, accession=f"ACC_{suffix}")
        self.file_type = FileType.objects.create(code=f"FA_{suffix}", name="FASTA", extension="fa")

    def test_promotes_curated_assembly_and_annotation_from_existing_relations(self):
        placeholder = Assembly.objects.create(accession=self.accession, name="default", is_default=True)
        curated = Assembly.objects.create(
            accession=self.accession,
            name="Curated assembly",
            assembly_code=f"ASM_{self.accession.accession}",
        )
        annotation = Annotation.objects.create(
            accession=self.accession,
            assembly=curated,
            name="Curated annotation",
            annotation_code=f"ANN_{self.accession.accession}",
        )
        genome_file = self._file("genome.fa")
        annotation_file = self._file("annotation.gff")
        FileRelation.objects.create(
            file=genome_file,
            related_type="assembly",
            related_id=str(curated.id),
            file_role="genome_fasta",
        )
        FileRelation.objects.create(
            file=annotation_file,
            related_type="annotation",
            related_id=str(annotation.id),
            file_role="annotation_gff3",
        )

        call_command("reconcile_assembly_annotation_context", output_dir=self.temp_dir.name)

        placeholder.refresh_from_db()
        curated.refresh_from_db()
        annotation.refresh_from_db()
        self.assertFalse(placeholder.is_default)
        self.assertTrue(curated.is_default)
        self.assertTrue(annotation.is_default)

    def test_dry_run_reports_change_without_writing_database(self):
        placeholder = Assembly.objects.create(accession=self.accession, name="default", is_default=True)
        curated = Assembly.objects.create(
            accession=self.accession,
            name="Curated assembly",
            assembly_code=f"ASM_{self.accession.accession}",
        )
        FileRelation.objects.create(
            file=self._file("genome.fa"),
            related_type="assembly",
            related_id=str(curated.id),
            file_role="genome_fasta",
        )

        call_command("reconcile_assembly_annotation_context", dry_run=True, output_dir=self.temp_dir.name)

        placeholder.refresh_from_db()
        curated.refresh_from_db()
        self.assertTrue(placeholder.is_default)
        self.assertFalse(curated.is_default)
        log_path = self._report("reconcile_assembly_annotation_context_log_", ".txt")
        with open(log_path, encoding="utf-8") as handle:
            self.assertIn("updated_default_assembly_count: 1", handle.read())

    def test_ambiguous_curated_assemblies_are_reported_without_changing_default(self):
        placeholder = Assembly.objects.create(accession=self.accession, name="default", is_default=True)
        for suffix in ("A", "B"):
            assembly = Assembly.objects.create(
                accession=self.accession,
                name=f"Curated {suffix}",
                assembly_code=f"ASM_{suffix}_{self.accession.id}",
            )
            FileRelation.objects.create(
                file=self._file(f"genome-{suffix}.fa"),
                related_type="assembly",
                related_id=str(assembly.id),
                file_role="genome_fasta",
            )

        call_command("reconcile_assembly_annotation_context", output_dir=self.temp_dir.name)

        placeholder.refresh_from_db()
        self.assertTrue(placeholder.is_default)
        details_path = self._report("reconcile_assembly_annotation_context_details_", ".tsv")
        with open(details_path, encoding="utf-8") as handle:
            self.assertIn("ambiguous curated Assembly candidates: 2", handle.read())

    def test_placeholder_only_is_reported_for_review(self):
        placeholder = Assembly.objects.create(accession=self.accession, name="default", is_default=True)
        FileRelation.objects.create(
            file=self._file("genome.fa"),
            related_type="assembly",
            related_id=str(placeholder.id),
            file_role="genome_fasta",
        )

        call_command("reconcile_assembly_annotation_context", output_dir=self.temp_dir.name)

        placeholder.refresh_from_db()
        self.assertTrue(placeholder.is_default)
        details_path = self._report("reconcile_assembly_annotation_context_details_", ".tsv")
        with open(details_path, encoding="utf-8") as handle:
            self.assertIn("only generated default Assembly", handle.read())

    def _file(self, name):
        return DataFile.objects.create(
            file_code=f"FILE_{uuid.uuid4().hex[:12].upper()}",
            file_type=self.file_type,
            file_name=name,
            file_path=os.path.join(self.temp_dir.name, name),
        )

    def _report(self, prefix, suffix):
        matches = [
            os.path.join(self.temp_dir.name, name)
            for name in os.listdir(self.temp_dir.name)
            if name.startswith(prefix) and name.endswith(suffix)
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]
