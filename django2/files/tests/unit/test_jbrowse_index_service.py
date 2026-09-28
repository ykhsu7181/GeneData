import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation
from files.services.jbrowse_index_service import (
    JBrowseIndexBuildError,
    build_jbrowse_assembly_indexes,
    inspect_jbrowse_assembly,
)


class JBrowseIndexDryRunTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 genome assembly",
            assembly_code="ASM_IR64",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="IR64 annotation",
            annotation_code="ANN_IR64",
            is_default=True,
        )
        self.fasta_path = self._write(
            "genome.IR64.fasta",
            ">Chr01\nACGT\n>Chr02 description\nAACCGG\n",
        )
        self.gff_path = self._write(
            "annotation.IR64.gff",
            "Chr01\ttest\tgene\t1\t4\t.\t+\t.\tID=gene1\n"
            "Chr02\ttest\tgene\t1\t6\t.\t+\t.\tID=gene2\n",
        )
        self.genome_file = self._data_file("GENOME_IR64", self.fasta_path)
        self.annotation_file = self._data_file("ANNOTATION_IR64", self.gff_path)
        FileRelation.objects.create(
            file=self.genome_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role="genome_fasta",
            is_primary=True,
        )
        FileRelation.objects.create(
            file=self.annotation_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            file_role="annotation",
            is_primary=True,
        )

    def _write(self, name, content):
        path = os.path.join(self.temporary_directory.name, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        return path

    def _data_file(self, code, path):
        return DataFile.objects.create(
            file_code=code,
            file_name=os.path.basename(path),
            file_path=path,
            file_size=os.path.getsize(path),
            is_current=True,
        )

    def test_ready_ir64_dry_run_scans_files_without_writing(self):
        output_root = os.path.join(self.temporary_directory.name, "derived")
        file_count = DataFile.objects.count()
        relation_count = FileRelation.objects.count()

        result = inspect_jbrowse_assembly(self.assembly.id, output_root=output_root)

        self.assertEqual(result["status"], "ready_for_build")
        self.assertEqual(result["fasta_sequence_count"], 2)
        self.assertEqual(result["gff_seqid_count"], 2)
        self.assertEqual(result["gff_feature_count"], 2)
        self.assertEqual(result["detected_format"], "likely_gff3_without_header")
        self.assertEqual(result["gff_seqids_missing_from_fasta"], [])
        self.assertFalse(result["write_performed"])
        self.assertFalse(os.path.exists(output_root))
        self.assertEqual(DataFile.objects.count(), file_count)
        self.assertEqual(FileRelation.objects.count(), relation_count)

    def test_replaced_placeholder_is_not_inspected(self):
        placeholder = Assembly.objects.create(
            accession=self.accession,
            name="default",
            assembly_code=None,
            is_default=False,
        )

        result = inspect_jbrowse_assembly(placeholder.id)

        self.assertEqual(result["status"], "assembly_not_found")

    def test_assembly_without_annotation_is_reference_only(self):
        self.annotation.delete()

        result = inspect_jbrowse_assembly(self.assembly.id)

        self.assertEqual(result["status"], "reference_only")
        self.assertEqual(result["fasta_sequence_count"], 2)
        self.assertFalse(result["write_performed"])

    def test_annotation_without_default_is_not_silently_ignored(self):
        self.annotation.is_default = False
        self.annotation.save(update_fields=["is_default"])

        result = inspect_jbrowse_assembly(self.assembly.id)

        self.assertEqual(result["status"], "missing_default_annotation")

    def test_seqid_mismatch_fails_preflight(self):
        with open(self.gff_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("Chr99\ttest\tgene\t1\t4\t.\t+\t.\tID=gene99\n")

        result = inspect_jbrowse_assembly(self.assembly.id)

        self.assertEqual(result["status"], "seqid_mismatch")
        self.assertEqual(result["gff_seqids_missing_from_fasta"], ["Chr99"])

    def test_command_outputs_json_and_remains_read_only(self):
        output_root = os.path.join(self.temporary_directory.name, "command-derived")
        stdout = StringIO()

        call_command(
            "build_jbrowse_indexes",
            assembly_id=self.assembly.id,
            dry_run=True,
            output_dir=output_root,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ready_for_build")
        self.assertFalse(payload["write_performed"])
        self.assertFalse(os.path.exists(output_root))

    def test_command_requires_explicit_mode(self):
        with self.assertRaisesRegex(CommandError, "exactly one"):
            call_command("build_jbrowse_indexes", assembly_id=self.assembly.id)

    def test_apply_builds_registers_and_sorts_artifacts(self):
        output_root = os.path.join(self.temporary_directory.name, "apply-derived")

        def fake_bgzip(_command, source_path, target_path):
            with open(source_path, "rb") as source, open(target_path, "wb") as target:
                target.write(source.read())

        def fake_tabix(_command, gff3_path):
            with open(f"{gff3_path}.tbi", "wb") as target:
                target.write(b"test-tabix-index")

        with patch(
            "files.services.jbrowse_index_service._resolve_tool",
            side_effect=lambda command: command,
        ), patch(
            "files.services.jbrowse_index_service._run_bgzip",
            side_effect=fake_bgzip,
        ), patch(
            "files.services.jbrowse_index_service._run_tabix",
            side_effect=fake_tabix,
        ):
            result = build_jbrowse_assembly_indexes(
                self.assembly.id,
                output_root=output_root,
            )

        self.assertEqual(result["status"], "built")
        self.assertTrue(result["write_performed"])
        self.assertEqual(len(result["artifacts"]), 3)
        roles = {item["file_role"] for item in result["artifacts"]}
        self.assertEqual(
            roles,
            {"genome_index", "jbrowse_annotation_gff3", "jbrowse_annotation_tabix"},
        )
        for artifact in result["artifacts"]:
            self.assertTrue(os.path.isfile(artifact["file_path"]))
            self.assertGreater(artifact["file_size"], 0)
        generated_gff = Path(result["planned_annotation_gff3"]).read_text(
            encoding="utf-8"
        )
        self.assertTrue(generated_gff.startswith("##gff-version 3\n"))
        self.assertLess(generated_gff.index("Chr01"), generated_gff.index("Chr02"))
        self.assertEqual(
            FileRelation.objects.filter(
                related_type="annotation",
                related_id=str(self.annotation.id),
                file_role__in=("jbrowse_annotation_gff3", "jbrowse_annotation_tabix"),
            ).count(),
            2,
        )

        with patch(
            "files.services.jbrowse_index_service._resolve_tool",
            side_effect=lambda command: command,
        ), patch(
            "files.services.jbrowse_index_service._run_bgzip",
            side_effect=fake_bgzip,
        ), patch(
            "files.services.jbrowse_index_service._run_tabix",
            side_effect=fake_tabix,
        ):
            second = build_jbrowse_assembly_indexes(
                self.assembly.id,
                output_root=output_root,
            )

        self.assertEqual(second["status"], "built")
        self.assertEqual(
            FileRelation.objects.filter(
                file_role__in=(
                    "genome_index",
                    "jbrowse_annotation_gff3",
                    "jbrowse_annotation_tabix",
                )
            ).count(),
            3,
        )

    def test_missing_bgzip_fails_before_creating_output(self):
        output_root = os.path.join(self.temporary_directory.name, "missing-tool")

        with self.assertRaisesRegex(JBrowseIndexBuildError, "required command"):
            build_jbrowse_assembly_indexes(
                self.assembly.id,
                output_root=output_root,
                bgzip_command="definitely-missing-bgzip-command",
            )

        self.assertFalse(os.path.exists(output_root))
