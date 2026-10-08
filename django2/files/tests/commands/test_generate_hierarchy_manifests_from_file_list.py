import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, Species


class GenerateHierarchyManifestsFromFileListTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
        )
        self.cg14 = Accession.objects.create(accession="CG14", species=species)
        self.a123 = Accession.objects.create(accession="A123", species=species)
        for accession in (self.cg14, self.a123):
            assembly = Assembly.objects.create(
                accession=accession,
                name="default",
                is_default=True,
            )
            Annotation.objects.create(
                accession=accession,
                assembly=assembly,
                name="default-annotation",
                is_default=True,
            )
        self.file_list = Path(self.temp_dir.name) / "files.txt"
        self.file_list.write_text(
            "\n".join([
                "/srv/manual_files/genome.CG14.fasta",
                "/srv/manual_files/annotation.CG14.gff",
                "/srv/manual_files/annotation.CG14.IGDBv1.Allset.gff",
                "/srv/manual_files/coreBlocks.CG14.bed",
                "/srv/manual_files/genome.A123.fasta",
                "/srv/manual_files/codon.sh",
            ]),
            encoding="utf-8",
        )

    def read_tsv(self, name):
        with (Path(self.temp_dir.name) / "out" / name).open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_generates_full_hierarchy_and_explicit_annotation_defaults(self):
        call_command(
            "generate_hierarchy_manifests_from_file_list",
            file_list=str(self.file_list),
            output_dir=str(Path(self.temp_dir.name) / "out"),
        )

        assemblies = self.read_tsv("assemblies.full.tsv")
        annotations = self.read_tsv("annotations.full.tsv")
        files = self.read_tsv("files.full.tsv")
        exceptions = self.read_tsv("exceptions.full.tsv")

        self.assertEqual(len(assemblies), 2)
        self.assertEqual(len(annotations), 2)
        self.assertEqual(len(files), 5)
        self.assertEqual(
            {row["assembly_code"] for row in assemblies},
            {"ASM_A123", "ASM_CG14"},
        )
        defaults = {row["file_name"]: row["is_default"] for row in annotations}
        self.assertEqual(defaults["annotation.CG14.gff"], "true")
        self.assertEqual(
            defaults["annotation.CG14.IGDBv1.Allset.gff"],
            "false",
        )
        versioned = next(
            row for row in annotations
            if row["file_name"] == "annotation.CG14.IGDBv1.Allset.gff"
        )
        self.assertEqual(versioned["annotation_version"], "IGDBv1.Allset")
        self.assertEqual(versioned["annotation_code"], "ANN_CG14_IGDBv1_Allset")
        self.assertTrue(any(row["reason"] == "unrecognized_filename" for row in exceptions))
