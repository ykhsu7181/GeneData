import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, Species


ASSEMBLY_HEADER = (
    "assembly_code\taccession\tassembly_accession\tassembly_name\t"
    "species_code\tassembly_level\treference\tsource_database\t"
    "external_project\tfile_name\tfile_type\tdescription"
)
ANNOTATION_HEADER = (
    "annotation_code\taccession\tassembly_code\tannotation_name\t"
    "annotation_version\tspecies_code\tsource_database\texternal_project\t"
    "file_name\tfile_type\tdescription"
)


class IncrementalHierarchyManifestCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manual_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(self.manual_dir.cleanup)
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="IR64", species=species)
        self.placeholder = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.placeholder_annotation = Annotation.objects.create(
            accession=self.accession,
            assembly=self.placeholder,
            name="default-annotation",
            is_default=True,
        )
        self.genome = Path(self.manual_dir.name) / "genome.IR64.fasta"
        self.genome.write_text(">chr1\nACGTNN\n", encoding="utf-8")
        self.gff = Path(self.manual_dir.name) / "annotation.IR64.gff"
        self.gff.write_text(
            "##gff-version 3\nchr1\tdemo\tgene\t1\t6\t.\t+\t.\tID=g1\n",
            encoding="utf-8",
        )
        self.assembly_manifest = Path(self.temp_dir.name) / "assembly.tsv"
        self.assembly_manifest.write_text(
            ASSEMBLY_HEADER
            + "\nASM_IR64\tIR64\tGCA_TEST\tIR64 genome assembly\t"
            "ORYZA_SATIVA\tchromosome\tNipponbare\tPublic database\t"
            "TEST_PROJECT\tgenome.IR64.fasta\tFASTA\tImported assembly\n",
            encoding="utf-8",
        )
        self.annotation_manifest = Path(self.temp_dir.name) / "annotation.tsv"
        self.annotation_manifest.write_text(
            ANNOTATION_HEADER
            + "\nANN_IR64\tIR64\tASM_IR64\tIR64 annotation\tv1\t"
            "ORYZA_SATIVA\tPublic database\tTEST_PROJECT\t"
            "annotation.IR64.gff\tGFF\tImported annotation\n",
            encoding="utf-8",
        )

    def run_command(self, *args):
        stdout = StringIO()
        call_command(
            "import_incremental_hierarchy_manifest",
            *args,
            assembly_file=str(self.assembly_manifest),
            annotation_file=str(self.annotation_manifest),
            manual_files_dir=self.manual_dir.name,
            output_dir=self.temp_dir.name,
            batch_id="test-batch",
            stdout=stdout,
        )
        return stdout.getvalue()

    def test_default_dry_run_rolls_back_complete_batch(self):
        output = self.run_command()

        self.assertIn("mode\tDRY_RUN", output)
        self.assertIn("status\tREADY", output)
        self.assertFalse(Assembly.objects.filter(assembly_code="ASM_IR64").exists())
        self.assertFalse(Annotation.objects.filter(annotation_code="ANN_IR64").exists())
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertTrue(Assembly.objects.filter(id=self.placeholder.id).exists())

    def test_apply_is_atomic_idempotent_and_removes_only_safe_placeholder(self):
        other = Accession.objects.create(accession="OTHER", species=self.accession.species)
        other_placeholder = Assembly.objects.create(
            accession=other,
            name="default",
            is_default=True,
        )
        Annotation.objects.create(
            accession=other,
            assembly=other_placeholder,
            name="default-annotation",
            is_default=True,
        )

        first = self.run_command("--apply")
        second = self.run_command("--apply")

        self.assertIn("status\tAPPLIED", first)
        self.assertIn("status\tAPPLIED", second)
        assembly = Assembly.objects.get(assembly_code="ASM_IR64")
        annotation = Annotation.objects.get(annotation_code="ANN_IR64")
        self.assertTrue(assembly.is_default)
        self.assertTrue(annotation.is_default)
        self.assertEqual(annotation.assembly, assembly)
        self.assertFalse(Assembly.objects.filter(id=self.placeholder.id).exists())
        self.assertTrue(Assembly.objects.filter(id=other_placeholder.id).exists())
        self.assertEqual(DataFile.objects.count(), 2)
        self.assertEqual(FileRelation.objects.count(), 5)
        self.assertEqual(
            FileRelation.objects.filter(is_primary=True).count(),
            3,
        )

    def test_explicit_default_selects_standard_annotation_with_multiple_versions(self):
        versioned_gff = Path(self.manual_dir.name) / "annotation.IR64.IGDBv1.Allset.gff"
        versioned_gff.write_text(
            "##gff-version 3\nchr1\tdemo\tgene\t1\t6\t.\t+\t.\tID=g2\n",
            encoding="utf-8",
        )
        self.annotation_manifest.write_text(
            ANNOTATION_HEADER
            + "\tis_default\n"
            + "ANN_IR64_IGDBv1_Allset\tIR64\tASM_IR64\tIR64 IGDBv1 Allset annotation\t"
            "IGDBv1.Allset\tORYZA_SATIVA\tPublic database\tTEST_PROJECT\t"
            "annotation.IR64.IGDBv1.Allset.gff\tGFF\tVersioned annotation\tfalse\n"
            + "ANN_IR64\tIR64\tASM_IR64\tIR64 annotation\tv1\t"
            "ORYZA_SATIVA\tPublic database\tTEST_PROJECT\t"
            "annotation.IR64.gff\tGFF\tDefault annotation\ttrue\n",
            encoding="utf-8",
        )

        output = self.run_command("--apply")

        self.assertIn("status\tAPPLIED", output)
        self.assertTrue(Annotation.objects.get(annotation_code="ANN_IR64").is_default)
        self.assertFalse(
            Annotation.objects.get(annotation_code="ANN_IR64_IGDBv1_Allset").is_default
        )

    def test_multiple_annotations_without_explicit_default_are_blocked(self):
        versioned_gff = Path(self.manual_dir.name) / "annotation.IR64.IGDBv1.Allset.gff"
        versioned_gff.write_text(
            "##gff-version 3\nchr1\tdemo\tgene\t1\t6\t.\t+\t.\tID=g2\n",
            encoding="utf-8",
        )
        self.annotation_manifest.write_text(
            ANNOTATION_HEADER
            + "\nANN_IR64\tIR64\tASM_IR64\tIR64 annotation\tv1\t"
            "ORYZA_SATIVA\tPublic database\tTEST_PROJECT\t"
            "annotation.IR64.gff\tGFF\tDefault annotation\n"
            + "ANN_IR64_IGDBv1_Allset\tIR64\tASM_IR64\tIR64 IGDBv1 Allset annotation\t"
            "IGDBv1.Allset\tORYZA_SATIVA\tPublic database\tTEST_PROJECT\t"
            "annotation.IR64.IGDBv1.Allset.gff\tGFF\tVersioned annotation\n",
            encoding="utf-8",
        )

        output = self.run_command("--apply")

        self.assertIn("status\tBLOCKED", output)
        self.assertFalse(Assembly.objects.filter(assembly_code="ASM_IR64").exists())

    def test_missing_file_blocks_entire_batch(self):
        self.gff.unlink()

        output = self.run_command("--apply")

        self.assertIn("status\tBLOCKED", output)
        self.assertIn("errors\t1", output)
        self.assertFalse(Assembly.objects.filter(assembly_code="ASM_IR64").exists())
        self.assertFalse(Annotation.objects.filter(annotation_code="ANN_IR64").exists())
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertTrue(Assembly.objects.filter(id=self.placeholder.id).exists())

    def test_metadata_conflict_blocks_batch_without_overwriting(self):
        existing = Assembly.objects.create(
            accession=self.accession,
            assembly_code="ASM_IR64",
            name="Curated name",
            source_database="CuratedDB",
        )

        output = self.run_command("--apply")

        self.assertIn("status\tBLOCKED", output)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Curated name")
        self.assertEqual(existing.source_database, "CuratedDB")
        self.assertFalse(Annotation.objects.filter(annotation_code="ANN_IR64").exists())
