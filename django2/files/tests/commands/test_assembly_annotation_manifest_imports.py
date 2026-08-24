import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import Client, TestCase

from files.models import Accession, Annotation, Assembly, Species
from files.services.accession_detail_service import (
    get_accession_annotations,
    get_accession_assemblies,
)


class AssemblyAnnotationManifestImportTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="IR64", species=self.species)
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def write_manifest(self, name, header, row):
        path = Path(self.temp_dir.name) / name
        path.write_text(f"{header}\n{row}\n", encoding="utf-8")
        return path

    def assembly_manifest(self):
        return self.write_manifest(
            "assembly.tsv",
            "assembly_code\taccession\tassembly_accession\tassembly_name\tspecies_code\tassembly_level\treference\tsource_database\texternal_project\tfile_name\tfile_type\tdescription",
            "ASM_IR64\tIR64\tGCA_001\tIR64 genome assembly\tORYZA_SATIVA\tchromosome\tNipponbare\tFigshare\tPRJEB73710\tgenome.IR64.fasta\tFASTA\tImported assembly",
        )

    def annotation_manifest(self):
        return self.write_manifest(
            "annotation.tsv",
            "annotation_code\taccession\tassembly_code\tannotation_name\tannotation_version\tspecies_code\tsource_database\texternal_project\tfile_name\tfile_type\tdescription",
            "ANN_IR64\tIR64\tASM_IR64\tIR64 genome annotation\tv1\tORYZA_SATIVA\tFigshare\tPRJEB73710\tannotation.IR64.gff\tGFF\tImported annotation",
        )

    def command_args(self, command, manifest, dry_run=False):
        args = [command, "--file", str(manifest), "--output-dir", self.temp_dir.name]
        if dry_run:
            args.append("--dry-run")
        return args

    def test_assembly_dry_run_does_not_write(self):
        call_command(*self.command_args("import_assembly_manifest", self.assembly_manifest(), dry_run=True))
        self.assertFalse(Assembly.objects.exists())

    def test_assembly_and_annotation_import_are_idempotent_and_exposed_by_api_service(self):
        assembly_path = self.assembly_manifest()
        annotation_path = self.annotation_manifest()
        call_command(*self.command_args("import_assembly_manifest", assembly_path))
        call_command(*self.command_args("import_assembly_manifest", assembly_path))
        call_command(*self.command_args("import_annotation_manifest", annotation_path))
        call_command(*self.command_args("import_annotation_manifest", annotation_path))

        self.assertEqual(Assembly.objects.count(), 1)
        self.assertEqual(Annotation.objects.count(), 1)
        assembly = Assembly.objects.get(assembly_code="ASM_IR64")
        annotation = Annotation.objects.get(annotation_code="ANN_IR64")
        self.assertEqual(assembly.accession, self.accession)
        self.assertEqual(annotation.accession, self.accession)
        self.assertEqual(annotation.assembly, assembly)

        assembly_row = get_accession_assemblies(self.accession)["results"][0]
        annotation_row = get_accession_annotations(self.accession)["results"][0]
        self.assertEqual(assembly_row["assembly_name"], "IR64 genome assembly")
        self.assertEqual(assembly_row["assembly_level"], "chromosome")
        self.assertEqual(assembly_row["source_database"], "Figshare")
        self.assertEqual(assembly_row["file_name"], "genome.IR64.fasta")
        self.assertEqual(annotation_row["annotation_name"], "IR64 genome annotation")
        self.assertEqual(annotation_row["annotation_version"], "v1")
        self.assertEqual(annotation_row["file_name"], "annotation.IR64.gff")
        self.assertEqual(annotation_row["file_type"], "GFF")

        assemblies_response = self.client.get("/gd/api/files/accessions/IR64/assemblies/")
        annotations_response = self.client.get("/gd/api/files/accessions/IR64/annotations/")
        self.assertEqual(assemblies_response.status_code, 200)
        self.assertEqual(annotations_response.status_code, 200)
        self.assertEqual(
            assemblies_response.json()["data"]["results"][0]["file_name"],
            "genome.IR64.fasta",
        )
        self.assertEqual(
            annotations_response.json()["data"]["results"][0]["annotation_version"],
            "v1",
        )

    def test_annotation_import_reports_missing_assembly_without_writing(self):
        call_command(*self.command_args("import_annotation_manifest", self.annotation_manifest()))
        self.assertFalse(Annotation.objects.exists())
