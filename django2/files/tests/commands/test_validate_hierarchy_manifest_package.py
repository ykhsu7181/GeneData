import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, Species


class ValidateHierarchyManifestPackageTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
        )
        accession = Accession.objects.create(accession="IR64", species=species)
        assembly = Assembly.objects.create(
            accession=accession,
            assembly_code="ASM_IR64",
            name="IR64 assembly",
            is_default=True,
        )
        Annotation.objects.create(
            accession=accession,
            assembly=assembly,
            annotation_code="ANN_IR64",
            name="IR64 annotation",
            is_default=True,
        )
        source = self.root / "files.txt"
        source.write_text(
            "/srv/manual_files/genome.IR64.fasta\n"
            "/srv/manual_files/annotation.IR64.gff\n",
            encoding="utf-8",
        )
        self.package = self.root / "package"
        call_command(
            "generate_hierarchy_manifests_from_file_list",
            file_list=str(source),
            output_dir=str(self.package),
            stdout=StringIO(),
        )

    def test_accepts_consistent_package_and_writes_report(self):
        report = self.root / "acceptance.txt"
        output = StringIO()
        call_command(
            "validate_hierarchy_manifest_package",
            manifest_dir=str(self.package),
            report=str(report),
            stdout=output,
        )
        self.assertIn("status\tPASS", output.getvalue())
        self.assertIn("status\tPASS", report.read_text(encoding="utf-8"))

    def test_rejects_cross_table_assembly_reference(self):
        path = self.package / "annotations.full.tsv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = list(reader)
            fields = reader.fieldnames
        rows[0]["assembly_code"] = "ASM_MISSING"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        with self.assertRaises(CommandError):
            call_command(
                "validate_hierarchy_manifest_package",
                manifest_dir=str(self.package),
                stdout=StringIO(),
                stderr=StringIO(),
            )
