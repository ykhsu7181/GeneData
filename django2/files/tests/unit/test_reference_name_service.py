import json
import os
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from files.models import Accession, Assembly, DataFile, FileRelation
from files.services.reference_name_service import (
    REFNAME_MAPPING_ROLE,
    ReferenceNameError,
    build_refname_mapping,
    load_current_refname_mapping,
    resolve_refname,
)


class ReferenceNameServiceTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.settings_override = override_settings(
            MANUAL_FILES_DIR=str(self.root / "manual"),
            GENEDATA_DERIVED_DATA_DIR=str(self.root / "derived"),
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        (self.root / "manual").mkdir()
        (self.root / "derived").mkdir()
        accession = Accession.objects.create(accession="TEST")
        self.assembly = Assembly.objects.create(
            accession=accession,
            name="Test assembly",
            assembly_code="ASM_TEST",
            is_default=True,
        )
        self.genome = self._file(
            self.root / "manual" / "test.fasta",
            "GENOME_TEST",
            ">contigA OriSeqID=chr1\nACGT\n>contigB OriSeqID=chr1\nAACCGG\n",
        )
        self.fai = self._file(
            self.root / "derived" / "test.fasta.fai",
            "FAI_TEST",
            "contigA\t4\t0\t4\t5\ncontigB\t6\t0\t6\t7\n",
        )
        self._relation(self.genome, "genome_fasta")
        self._relation(self.fai, "genome_index")

    def _file(self, path, code, content):
        path.write_text(content, encoding="utf-8", newline="\n")
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            is_current=True,
        )

    def _relation(self, data_file, role):
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role=role,
            is_primary=True,
        )

    def test_build_registers_private_mapping_and_preserves_ambiguity(self):
        result = build_refname_mapping(
            self.assembly,
            self.genome,
            self.fai,
            output_root=str(self.root / "derived"),
        )

        self.assertEqual(result["status"], "built")
        relation = FileRelation.objects.get(file_role=REFNAME_MAPPING_ROLE)
        payload = json.loads(Path(relation.file.file_path).read_text(encoding="utf-8"))
        self.assertEqual(payload["aliases"]["chr1"]["status"], "ambiguous")
        with self.assertRaisesRegex(ReferenceNameError, "multiple"):
            resolve_refname(payload, "chr1")
        self.assertEqual(resolve_refname(payload, "contigA"), ("contigA", 4))

    def test_mapping_becomes_stale_when_fai_bytes_change(self):
        build_refname_mapping(
            self.assembly,
            self.genome,
            self.fai,
            output_root=str(self.root / "derived"),
        )
        Path(self.fai.file_path).write_text(
            "contigA\t5\t0\t5\t6\ncontigB\t6\t0\t6\t7\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ReferenceNameError, "FAI changed"):
            load_current_refname_mapping(self.assembly, self.genome, self.fai)

    def test_single_assembly_command_supports_dry_run_and_apply(self):
        call_command(
            "backfill_jbrowse_refname_aliases",
            assembly_id=self.assembly.id,
            dry_run=True,
        )
        self.assertFalse(FileRelation.objects.filter(file_role=REFNAME_MAPPING_ROLE).exists())

        call_command(
            "backfill_jbrowse_refname_aliases",
            assembly_id=self.assembly.id,
            apply=True,
            output_dir=str(self.root / "derived"),
        )
        self.assertTrue(FileRelation.objects.filter(file_role=REFNAME_MAPPING_ROLE).exists())
