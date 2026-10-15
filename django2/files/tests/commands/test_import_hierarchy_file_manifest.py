import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    FileRelation,
    FileType,
    Species,
)


class ImportHierarchyFileManifestTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.manual_root = self.root / "manual_files"
        self.manual_root.mkdir()
        self.reports = self.root / "reports"
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="IR64", species=species)
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 assembly",
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

    def write_manifest(self, rows):
        path = self.root / "files.full.tsv"
        fields = [
            "file_path",
            "file_role",
            "accession",
            "assembly_code",
            "annotation_code",
            "sample_code",
            "dataset_code",
            "md5",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, file_path, role="genome", annotation_code=""):
        return {
            "file_path": str(file_path),
            "file_role": role,
            "accession": "IR64",
            "assembly_code": "ASM_IR64",
            "annotation_code": annotation_code,
            "sample_code": "",
            "dataset_code": "",
            "md5": "",
        }

    def test_dry_run_rolls_back_all_database_writes(self):
        genome = self.manual_root / "genome.IR64.fasta"
        genome.write_text(">chr1\nATGC\n", encoding="utf-8")
        manifest = self.write_manifest([self.row(genome)])

        call_command(
            "import_hierarchy_file_manifest",
            file=manifest,
            manual_files_dir=self.manual_root,
            output_dir=self.reports,
            dry_run=True,
        )

        self.assertFalse(DataFile.objects.exists())
        self.assertFalse(FileRelation.objects.exists())
        self.assertFalse(FileType.objects.exists())
        report = next(self.reports.glob("hierarchy_file_manifest_*.tsv"))
        self.assertIn("ready", report.read_text(encoding="utf-8-sig"))

    def test_apply_binds_explicit_hierarchy_and_is_idempotent(self):
        gff = self.manual_root / "annotation.IR64.gff"
        gff.write_text("##gff-version 3\nchr1\tdemo\tgene\t1\t4\t.\t+\t.\tID=g1\n", encoding="utf-8")
        manifest = self.write_manifest([
            self.row(gff, role="annotation", annotation_code="ANN_IR64")
        ])
        kwargs = {
            "file": manifest,
            "manual_files_dir": self.manual_root,
            "output_dir": self.reports,
            "apply": True,
        }

        call_command("import_hierarchy_file_manifest", **kwargs)
        call_command("import_hierarchy_file_manifest", **kwargs)

        data_file = DataFile.objects.get(file_path=str(gff.resolve()))
        self.assertEqual(DataFile.objects.count(), 1)
        self.assertEqual(FileType.objects.get().extension, "gff")
        self.assertEqual(data_file.relations.count(), 3)
        self.assertTrue(
            data_file.relations.get(
                related_type="assembly", related_id=str(self.assembly.id)
            ).is_primary
        )
        self.assertTrue(
            data_file.relations.get(
                related_type="annotation", related_id=str(self.annotation.id)
            ).is_primary
        )

    def test_preflight_blocks_empty_and_outside_files(self):
        empty = self.manual_root / "miRNA.IR64.bed"
        empty.touch()
        outside = self.root / "outside.bed"
        outside.write_text("chr1\t1\t2\n", encoding="utf-8")
        manifest = self.write_manifest([
            self.row(empty, role="miRNA"),
            self.row(outside, role="rRNA"),
        ])

        call_command(
            "import_hierarchy_file_manifest",
            file=manifest,
            manual_files_dir=self.manual_root,
            output_dir=self.reports,
            dry_run=True,
        )

        self.assertFalse(DataFile.objects.exists())
        report = next(self.reports.glob("hierarchy_file_manifest_*.tsv")).read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("empty_file", report)
        self.assertIn("path_outside_manual_files", report)

    def test_preflight_requires_matching_explicit_assembly(self):
        genome = self.manual_root / "genome.IR64.fasta"
        genome.write_text(">chr1\nATGC\n", encoding="utf-8")
        row = self.row(genome)
        row["assembly_code"] = "ASM_UNKNOWN"
        manifest = self.write_manifest([row])

        call_command(
            "import_hierarchy_file_manifest",
            file=manifest,
            manual_files_dir=self.manual_root,
            output_dir=self.reports,
            dry_run=True,
        )

        self.assertFalse(DataFile.objects.exists())
        report = next(self.reports.glob("hierarchy_file_manifest_*.tsv")).read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("unknown_assembly", report)
