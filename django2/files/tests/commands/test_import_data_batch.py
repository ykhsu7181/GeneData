import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Assembly, DataFile, FileRelation, Species
from files.management.commands.import_data_batch import Command, IMPORT_SEQUENCE


class ImportDataBatchTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.batch_dir = Path(self.temp_dir.name)
        (self.batch_dir / "metadata").mkdir()
        (self.batch_dir / "files").mkdir()
        (self.batch_dir / "batch.yaml").write_text(
            'batch_id: batch-001\nsource: lab_internal\nsource_version: "1"\ndescription: test batch\n',
            encoding="utf-8",
        )
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )

    def write_tsv(self, name, headers, values):
        path = self.batch_dir / "metadata" / f"{name}.tsv"
        path.write_text(
            "\t".join(headers) + "\n" + "\t".join(values) + "\n",
            encoding="utf-8",
        )
        return path

    def add_accession_and_file_manifests(self, role="genome"):
        self.write_tsv(
            "accessions",
            ["accession", "species_code"],
            ["IR64", self.species.species_code],
        )
        physical = self.batch_dir / "files" / "genome.IR64.fasta"
        physical.write_text(">chr1\nATGC\n", encoding="utf-8")
        self.write_tsv(
            "files",
            [
                "file_path", "file_role", "accession", "assembly_code",
                "annotation_code", "sample_code", "dataset_code", "md5",
            ],
            [physical.name, role, "IR64", "", "", "", "", ""],
        )
        return physical.resolve()

    def test_dry_run_validates_and_writes_reports_without_database_changes(self):
        self.add_accession_and_file_manifests()

        call_command("import_data_batch", batch_dir=self.batch_dir, dry_run=True)

        self.assertFalse(Accession.objects.filter(accession="IR64").exists())
        self.assertFalse(DataFile.objects.exists())
        report_dir = self.batch_dir / "reports"
        summary = (report_dir / "batch_summary.txt").read_text(encoding="utf-8")
        self.assertIn("ready_to_import: YES", summary)
        for name in (
            "batch_manifest_checksums.tsv", "batch_errors.tsv",
            "batch_conflicts.tsv", "batch_unmapped.tsv", "batch_plan.tsv",
        ):
            self.assertTrue((report_dir / name).is_file())
        plan = (report_dir / "batch_plan.tsv").read_text(encoding="utf-8")
        self.assertIn("metadata/accessions.tsv", plan)
        self.assertIn("metadata/files.tsv", plan)

    def test_apply_imports_in_dependency_order_and_is_idempotent(self):
        physical = self.add_accession_and_file_manifests()

        call_command("import_data_batch", batch_dir=self.batch_dir, apply=True)
        call_command("import_data_batch", batch_dir=self.batch_dir, apply=True)

        accession = Accession.objects.get(accession="IR64")
        data_file = DataFile.objects.get(file_path=str(physical))
        self.assertEqual(DataFile.objects.count(), 1)
        self.assertEqual(
            FileRelation.objects.filter(
                file=data_file,
                related_type="accession",
                related_id=str(accession.id),
                file_role="genome",
            ).count(),
            1,
        )
        summary = (self.batch_dir / "reports" / "batch_summary.txt").read_text(encoding="utf-8")
        self.assertIn("applied: True", summary)

    def test_failed_gate_does_not_apply_any_manifest(self):
        self.add_accession_and_file_manifests(role="unknown_role")

        with self.assertRaises(CommandError):
            call_command("import_data_batch", batch_dir=self.batch_dir, apply=True)

        self.assertFalse(Accession.objects.filter(accession="IR64").exists())
        self.assertFalse(DataFile.objects.exists())
        errors = (self.batch_dir / "reports" / "batch_errors.tsv").read_text(encoding="utf-8")
        self.assertIn("unknown file_role", errors)

    def test_multiple_assemblies_require_explicit_assembly_code(self):
        accession = Accession.objects.create(accession="IR64", species=self.species)
        Assembly.objects.create(accession=accession, assembly_code="ASM1", name="v1")
        Assembly.objects.create(accession=accession, assembly_code="ASM2", name="v2")
        physical = self.batch_dir / "files" / "genome.IR64.fasta"
        physical.write_text(">chr1\nATGC\n", encoding="utf-8")
        self.write_tsv(
            "files",
            [
                "file_path", "file_role", "accession", "assembly_code",
                "annotation_code", "sample_code", "dataset_code", "md5",
            ],
            [physical.name, "genome", "IR64", "", "", "", "", ""],
        )

        call_command("import_data_batch", batch_dir=self.batch_dir, dry_run=True)

        conflicts = (self.batch_dir / "reports" / "batch_conflicts.tsv").read_text(encoding="utf-8")
        self.assertIn("ambiguous assembly", conflicts)

    def test_apply_orchestrates_existing_importers_in_dependency_order(self):
        manifests = {
            name: {"path": self.batch_dir / "metadata" / f"{name}.tsv", "rows": []}
            for name, _, _ in IMPORT_SEQUENCE
        }
        manifests["files"] = {"path": Path("files.tsv"), "rows": []}
        manifests["raw_data"] = {"path": Path("raw_data.tsv"), "rows": [{}]}
        calls = []

        with patch(
            "files.management.commands.import_data_batch.call_command",
            side_effect=lambda command, **kwargs: calls.append(command),
        ), patch.object(Command, "_apply_files") as apply_files, patch.object(
            Command, "_write_resolved_raw_manifest"
        ):
            Command()._apply_manifests(
                self.batch_dir,
                self.batch_dir,
                {"batch_id": "B", "source": "S", "source_version": "1"},
                manifests,
            )

        self.assertEqual(calls, [item[1] for item in IMPORT_SEQUENCE] + ["import_raw_data_manifest"])
        apply_files.assert_called_once()

    def test_apply_resolves_and_imports_raw_data_after_metadata(self):
        self.write_tsv(
            "accessions",
            ["accession", "species_code"],
            ["IR64", self.species.species_code],
        )
        physical = self.batch_dir / "files" / "IR64_R1.fastq.gz"
        physical.write_bytes(b"reads")
        self.write_tsv(
            "raw_data",
            ["file_path", "file_role", "accession_code"],
            [physical.name, "raw_reads_R1", "IR64"],
        )

        call_command("import_data_batch", batch_dir=self.batch_dir, apply=True)

        accession = Accession.objects.get(accession="IR64")
        data_file = DataFile.objects.get(file_path=str(physical.resolve()))
        self.assertTrue(
            FileRelation.objects.filter(
                file=data_file,
                related_type="accession",
                related_id=str(accession.id),
                file_role="raw_reads_R1",
            ).exists()
        )

    def test_relative_file_path_cannot_escape_batch_files_directory(self):
        outside = self.batch_dir / "outside.fasta"
        outside.write_text(">chr1\nATGC\n", encoding="utf-8")
        self.write_tsv(
            "files",
            [
                "file_path", "file_role", "accession", "assembly_code",
                "annotation_code", "sample_code", "dataset_code", "md5",
            ],
            ["../outside.fasta", "genome", "IR64", "", "", "", "", ""],
        )

        call_command("import_data_batch", batch_dir=self.batch_dir, dry_run=True)

        errors = (self.batch_dir / "reports" / "batch_errors.tsv").read_text(encoding="utf-8")
        self.assertIn("escapes the batch files directory", errors)
