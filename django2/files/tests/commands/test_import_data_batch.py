import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import (
    Accession, AccessionExternalMapping, Assembly, DataFile, Dataset,
    FileRelation, FileType, Project, Sample, Species,
)
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
        self.assertFalse(FileType.objects.exists())
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
        self.assertEqual(data_file.file_type.extension, "fasta")
        self.assertEqual(FileType.objects.filter(extension="fasta").count(), 1)
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
        self.assertIn("post_apply_audit: PASS", summary)
        self.assertIn("dry_run: False", summary)
        for directory in ("audit_file_relations", "validate_new_file_structure", "readiness"):
            self.assertTrue((self.batch_dir / "reports" / directory / "command_output.txt").is_file())

    def test_existing_accession_sample_and_dataset_conflicts_block_batch(self):
        other_species = Species.objects.create(
            species_code="ORYZA_NIVARA",
            scientific_name="Oryza nivara",
        )
        ir64 = Accession.objects.create(
            accession="IR64", species=self.species, country="China",
        )
        other = Accession.objects.create(accession="OTHER", species=other_species)
        Sample.objects.create(
            sample_code="S1", species=self.species, accession=ir64, tissue="root",
        )
        project = Project.objects.create(project_code="P1", project_name="Curated")
        Dataset.objects.create(
            dataset_code="D1", dataset_name="Curated dataset", dataset_type="genome",
            species=self.species, project=project,
        )
        self.write_tsv(
            "accessions",
            ["accession", "species_code", "country"],
            ["IR64", self.species.species_code, "Vietnam"],
        )
        self.write_tsv(
            "samples",
            ["sample_code", "species_code", "accession", "tissue"],
            ["S1", other_species.species_code, other.accession, "leaf"],
        )
        self.write_tsv(
            "datasets",
            ["accession", "project_code", "dataset_code", "dataset_type", "dataset_name"],
            [other.accession, "P2", "D1", "annotation", "Incoming dataset"],
        )

        call_command("import_data_batch", batch_dir=self.batch_dir, dry_run=True)

        conflicts = (self.batch_dir / "reports" / "batch_conflicts.tsv").read_text(encoding="utf-8")
        self.assertIn("accessions", conflicts)
        self.assertIn("samples", conflicts)
        self.assertIn("datasets", conflicts)
        self.assertIn("metadata conflict", conflicts)
        summary = (self.batch_dir / "reports" / "batch_summary.txt").read_text(encoding="utf-8")
        self.assertIn("ready_to_import: NO", summary)

    def test_post_apply_audit_failure_is_reported_as_failure(self):
        self.write_tsv(
            "accessions",
            ["accession", "species_code"],
            ["IR64", self.species.species_code],
        )
        failed_audits = [{
            "command": "validate_new_file_structure",
            "status": "FAIL",
            "accepted": False,
            "report_dir": "reports/validate_new_file_structure",
            "message": "new-only validation failed",
        }]

        with patch.object(Command, "_run_post_apply_audits", return_value=failed_audits):
            with self.assertRaises(CommandError):
                call_command("import_data_batch", batch_dir=self.batch_dir, apply=True)

        self.assertTrue(Accession.objects.filter(accession="IR64").exists())
        summary = (self.batch_dir / "reports" / "batch_summary.txt").read_text(encoding="utf-8")
        self.assertIn("applied: True", summary)
        self.assertIn("post_apply_audit: FAIL", summary)
        audit_report = (self.batch_dir / "reports" / "batch_audits.tsv").read_text(encoding="utf-8")
        self.assertIn("validate_new_file_structure", audit_report)
        self.assertIn("FAIL", audit_report)

    def test_post_apply_runner_calls_all_three_audits(self):
        outputs = {
            "audit_file_relations": "broken_relation_count\t0\nduplicate_relation_count\t0\nduplicate_primary_count\t0\n",
            "validate_new_file_structure": "result\tPASS\n",
            "audit_genome_transcriptome_readiness": "status=PASS\n",
        }
        calls = []

        def fake_call(command, **kwargs):
            calls.append(command)
            kwargs["stdout"].write(outputs[command])

        with patch("files.management.commands.import_data_batch.call_command", side_effect=fake_call):
            results = Command()._run_post_apply_audits(self.batch_dir / "reports")

        self.assertEqual(calls, [
            "audit_file_relations",
            "validate_new_file_structure",
            "audit_genome_transcriptome_readiness",
        ])
        self.assertTrue(all(item["accepted"] for item in results))

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
        import_results = (self.batch_dir / "reports" / "batch_import_results.tsv").read_text(
            encoding="utf-8",
        )
        self.assertIn("raw_data\timport_raw_data_manifest\tPASS", import_results)
        checksums = (self.batch_dir / "reports" / "batch_manifest_checksums.tsv").read_text(
            encoding="utf-8",
        )
        self.assertIn("raw_data.resolved.tsv", checksums)
        self.assertIn("derived\tmetadata/raw_data.tsv", checksums)

    def test_external_mapping_and_raw_metadata_conflicts_block_batch(self):
        accession = Accession.objects.create(accession="IR64", species=self.species)
        AccessionExternalMapping.objects.create(
            accession=accession,
            external_database="ENA",
            external_study_accession="ERP1",
            run_accession="ERR1",
            instrument_model="PacBio Revio",
        )
        physical = self.batch_dir / "files" / "IR64_R1.fastq.gz"
        physical.write_bytes(b"reads")
        DataFile.objects.create(
            file_code="FILE900001",
            file_name=physical.name,
            file_path=str(physical.resolve()),
            description=json.dumps({"raw_data": {"raw_data_type": "WGS"}}),
        )
        self.write_tsv(
            "external_mappings",
            ["accession", "ena_study", "run", "instrument_model"],
            ["IR64", "ERP1", "ERR1", "Illumina NovaSeq"],
        )
        self.write_tsv(
            "raw_data",
            ["file_path", "file_role", "accession_code", "raw_data_type"],
            [physical.name, "raw_reads_R1", "IR64", "RNA-seq"],
        )

        call_command("import_data_batch", batch_dir=self.batch_dir, dry_run=True)

        conflicts = (self.batch_dir / "reports" / "batch_conflicts.tsv").read_text(
            encoding="utf-8",
        )
        self.assertIn("external_mappings", conflicts)
        self.assertIn("instrument_model", conflicts)
        self.assertIn("raw_data", conflicts)
        self.assertIn("raw_data_type", conflicts)

    def test_importer_result_with_nonzero_conflicts_is_failed(self):
        result = Command()._import_result(
            "samples",
            "import_sample_manifest",
            "scanned_count=1\ncreated_count=0\nconflict_count=1\n",
            self.batch_dir,
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["conflict_count"], 1)

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
