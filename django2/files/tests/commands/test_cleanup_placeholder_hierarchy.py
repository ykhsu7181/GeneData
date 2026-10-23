import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation


class CleanupPlaceholderHierarchyCommandTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)

    def hierarchy(self, code, *, replacement=True):
        accession = Accession.objects.create(accession=code)
        placeholder = Assembly.objects.create(
            accession=accession,
            name="default",
            is_default=True,
        )
        placeholder_annotation = Annotation.objects.create(
            accession=accession,
            assembly=placeholder,
            name="default-annotation",
            is_default=True,
        )
        real_assembly = None
        real_annotation = None
        if replacement:
            real_assembly = Assembly.objects.create(
                accession=accession,
                name=f"{code} genome assembly",
                assembly_code=f"ASM_{code}",
            )
            real_annotation = Annotation.objects.create(
                accession=accession,
                assembly=real_assembly,
                name=f"{code} annotation",
                annotation_code=f"ANN_{code}",
            )
        return placeholder, placeholder_annotation, real_assembly, real_annotation

    def run_command(self, *args):
        stdout = StringIO()
        call_command(
            "cleanup_placeholder_hierarchy",
            *args,
            output_dir=self.output_dir.name,
            stdout=stdout,
        )
        report = sorted(
            Path(self.output_dir.name).glob("cleanup_placeholder_hierarchy_*.tsv")
        )[-1]
        with report.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return stdout.getvalue(), rows

    def test_default_dry_run_keeps_candidate_rows(self):
        placeholder, _, real_assembly, _ = self.hierarchy("IR64")

        output, rows = self.run_command()

        self.assertIn("mode\tDRY_RUN", output)
        assembly_row = next(row for row in rows if row["object_type"] == "assembly")
        self.assertEqual(assembly_row["status"], "candidate")
        self.assertTrue(Assembly.objects.filter(id=placeholder.id).exists())
        self.assertFalse(real_assembly.is_default)

    def test_apply_deletes_safe_placeholder_and_promotes_replacement(self):
        placeholder, placeholder_annotation, real_assembly, real_annotation = self.hierarchy("MH63")

        output, rows = self.run_command("--apply")

        self.assertIn("mode\tAPPLY", output)
        self.assertFalse(Assembly.objects.filter(id=placeholder.id).exists())
        self.assertFalse(Annotation.objects.filter(id=placeholder_annotation.id).exists())
        real_assembly.refresh_from_db()
        real_annotation.refresh_from_db()
        self.assertTrue(real_assembly.is_default)
        self.assertTrue(real_annotation.is_default)
        self.assertTrue(all(row["status"] == "deleted" for row in rows))

    def test_blocks_placeholder_without_replacement(self):
        placeholder, _, _, _ = self.hierarchy("NO_MANIFEST", replacement=False)

        _, rows = self.run_command("--apply")

        assembly_row = next(row for row in rows if row["object_type"] == "assembly")
        self.assertEqual(assembly_row["status"], "blocked")
        self.assertIn("no_real_replacement_assembly", assembly_row["reason"])
        self.assertTrue(Assembly.objects.filter(id=placeholder.id).exists())

    def test_blocks_placeholder_with_file_relation(self):
        placeholder, _, _, _ = self.hierarchy("BOUND")
        data_file = DataFile.objects.create(
            file_code="FILE_BOUND",
            file_name="genome.BOUND.fasta",
            file_path="/tmp/genome.BOUND.fasta",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(placeholder.id),
            file_role="genome",
        )

        _, rows = self.run_command("--apply")

        assembly_row = next(row for row in rows if row["object_type"] == "assembly")
        self.assertEqual(assembly_row["status"], "blocked")
        self.assertIn("assembly_has_file_relations", assembly_row["reason"])
        self.assertTrue(Assembly.objects.filter(id=placeholder.id).exists())
