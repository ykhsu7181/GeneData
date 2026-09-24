import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, GenomeFile


class MigratePlaceholderHierarchyCommandTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def manifests(self, rows):
        assembly_path = self.root / "assemblies.tsv"
        files_path = self.root / "files.tsv"
        with assembly_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("assembly_code", "accession", "file_name"),
                delimiter="\t",
            )
            writer.writeheader()
            for accession, code in rows:
                writer.writerow(
                    {
                        "assembly_code": code,
                        "accession": accession,
                        "file_name": f"genome.{accession}.fasta",
                    }
                )
        with files_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("file_path", "file_role", "accession", "assembly_code"),
                delimiter="\t",
            )
            writer.writeheader()
            for accession, code in rows:
                writer.writerow(
                    {
                        "file_path": f"/production/manual_files/genome.{accession}.fasta",
                        "file_role": "genome",
                        "accession": accession,
                        "assembly_code": code,
                    }
                )
        return assembly_path, files_path

    def hierarchy(self, accession_code):
        accession = Accession.objects.create(accession=accession_code)
        placeholder = Assembly.objects.create(
            accession=accession,
            name="default",
            is_default=True,
            genome_size=123,
        )
        target = Assembly.objects.create(
            accession=accession,
            name=f"{accession_code} assembly",
            assembly_code=f"ASM_{accession_code}",
        )
        return placeholder, target

    def run_command(self, assembly_path, files_path, *args):
        stdout = StringIO()
        call_command(
            "migrate_placeholder_hierarchy",
            *args,
            assembly_file=str(assembly_path),
            file_manifest=str(files_path),
            output_dir=str(self.root / "reports"),
            stdout=stdout,
        )
        report = sorted((self.root / "reports").glob("migrate_placeholder_hierarchy_*.tsv"))[-1]
        with report.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return stdout.getvalue(), rows

    def test_dry_run_reports_mapping_without_mutation(self):
        placeholder, target = self.hierarchy("IR64")
        assembly_path, files_path = self.manifests([("IR64", "ASM_IR64")])

        output, rows = self.run_command(assembly_path, files_path)

        self.assertIn("mode\tDRY_RUN", output)
        self.assertEqual(rows[0]["status"], "ready")
        self.assertEqual(rows[0]["expected_genome_file"], "genome.IR64.fasta")
        self.assertTrue(Assembly.objects.filter(id=placeholder.id).exists())
        target.refresh_from_db()
        self.assertFalse(target.is_default)

    def test_apply_moves_dependencies_copies_blank_metadata_and_deletes_placeholder(self):
        placeholder, target = self.hierarchy("MH63")
        assembly_path, files_path = self.manifests([("MH63", "ASM_MH63")])
        data_file = DataFile.objects.create(
            file_code="FILE_MH63",
            file_name="genome.MH63.fasta",
            file_path="/production/manual_files/genome.MH63.fasta",
        )
        relation = FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(placeholder.id),
            related_code="default",
            file_role="genome",
        )
        legacy = GenomeFile.objects.create(
            name="genome.MH63.fasta",
            organism="MH63",
            accession=placeholder.accession,
            assembly=placeholder,
            category="genome",
            file_path="/production/manual_files/genome.MH63.fasta",
        )

        output, rows = self.run_command(assembly_path, files_path, "--apply")

        self.assertIn("mode\tAPPLY", output)
        self.assertEqual(rows[0]["status"], "migrated")
        self.assertFalse(Assembly.objects.filter(id=placeholder.id).exists())
        target.refresh_from_db()
        relation.refresh_from_db()
        legacy.refresh_from_db()
        self.assertTrue(target.is_default)
        self.assertEqual(target.genome_size, 123)
        self.assertEqual(relation.related_id, str(target.id))
        self.assertEqual(relation.related_code, target.assembly_code)
        self.assertEqual(legacy.assembly_id, target.id)

    def test_apply_reuses_duplicate_target_relation(self):
        placeholder, target = self.hierarchy("R498")
        assembly_path, files_path = self.manifests([("R498", "ASM_R498")])
        data_file = DataFile.objects.create(
            file_code="FILE_R498",
            file_name="genome.R498.fasta",
            file_path="/production/manual_files/genome.R498.fasta",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(placeholder.id),
            file_role="genome",
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(target.id),
            related_code=target.assembly_code,
            file_role="genome",
        )

        _, rows = self.run_command(assembly_path, files_path, "--apply")

        self.assertEqual(rows[0]["relations_to_reuse"], "1")
        self.assertEqual(
            FileRelation.objects.filter(
                file=data_file,
                related_type="assembly",
                related_id=str(target.id),
                file_role="genome",
            ).count(),
            1,
        )

    def test_missing_physical_file_does_not_block_manifest_mapping(self):
        placeholder, target = self.hierarchy("NO_FASTA")
        assembly_path, files_path = self.manifests([("NO_FASTA", "ASM_NO_FASTA")])

        _, rows = self.run_command(assembly_path, files_path, "--apply")

        self.assertEqual(rows[0]["status"], "migrated")
        self.assertFalse(Assembly.objects.filter(id=placeholder.id).exists())
        target.refresh_from_db()
        self.assertTrue(target.is_default)

    def test_blocks_missing_target_and_placeholder_annotations(self):
        placeholder, _ = self.hierarchy("BLOCKED")
        Assembly.objects.filter(accession=placeholder.accession).exclude(id=placeholder.id).delete()
        Annotation.objects.create(
            accession=placeholder.accession,
            assembly=placeholder,
            name="legacy-annotation",
        )
        assembly_path, files_path = self.manifests([("BLOCKED", "ASM_BLOCKED")])

        _, rows = self.run_command(assembly_path, files_path)

        self.assertEqual(rows[0]["status"], "blocked")
        self.assertIn("target_assembly_not_imported", rows[0]["reason"])
        self.assertIn("placeholder_has_annotations", rows[0]["reason"])
        self.assertTrue(Assembly.objects.filter(id=placeholder.id).exists())

    def test_apply_refuses_entire_batch_when_any_row_is_blocked(self):
        ready_placeholder, _ = self.hierarchy("READY")
        blocked_placeholder, _ = self.hierarchy("BLOCKED_BATCH")
        Assembly.objects.filter(accession=blocked_placeholder.accession).exclude(
            id=blocked_placeholder.id
        ).delete()
        assembly_path, files_path = self.manifests(
            [("READY", "ASM_READY"), ("BLOCKED_BATCH", "ASM_BLOCKED_BATCH")]
        )

        with self.assertRaises(CommandError):
            self.run_command(assembly_path, files_path, "--apply")

        self.assertTrue(Assembly.objects.filter(id=ready_placeholder.id).exists())
        self.assertTrue(Assembly.objects.filter(id=blocked_placeholder.id).exists())

    def test_file_manifest_exact_mapping_takes_precedence(self):
        placeholder, target = self.hierarchy("PREFERRED")
        assembly_path, files_path = self.manifests([("PREFERRED", "ASM_PREFERRED")])
        with assembly_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(("ASM_OTHER", "PREFERRED", "genome.PREFERRED.fasta"))

        _, rows = self.run_command(assembly_path, files_path)

        self.assertEqual(rows[0]["status"], "ready")
        self.assertEqual(rows[0]["target_id"], str(target.id))
