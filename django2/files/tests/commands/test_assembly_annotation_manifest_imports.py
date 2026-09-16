import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
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

    def assembly_metadata_manifest(self, *, assembly_code="ASM_IR64", genome_size="387400000", gc_content="43.500"):
        return self.write_manifest(
            "assembly-metadata.tsv",
            "assembly_code\taccession\tassembly_accession\tassembly_name\tspecies_code\tassembly_level\tbiosample_accession\tassembly_type\tassembly_method\tsequencing_technology\tgenome_size\tchromosome_count\tcontig_count\tn50\tgc_content\treference\tsource_database\texternal_project\tfile_name\tfile_type\tdescription",
            f"{assembly_code}\tIR64\tGCA_001\tIR64 genome assembly\tORYZA_SATIVA\tchromosome\tSAMN04274565\thaploid\thifiasm v0.19.8\tPacBio HiFi\t{genome_size}\t12\t19\t27000000\t{gc_content}\tNipponbare\tFigshare\tPRJEB73710\tgenome.IR64.fasta\tFASTA\tImported assembly",
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

    def test_assembly_report_contains_provenance(self):
        manifest = self.assembly_manifest()
        call_command(
            "import_assembly_manifest",
            "--file",
            str(manifest),
            "--output-dir",
            self.temp_dir.name,
            "--dry-run",
            "--batch-id",
            "batch-1",
            "--source",
            "lab",
            "--source-version",
            "v2",
        )

        report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_log_*.txt"))
        content = report.read_text(encoding="utf-8")
        self.assertIn("batch_id: batch-1", content)
        self.assertIn("source: lab", content)
        self.assertIn("source_version: v2", content)
        self.assertIn("manifest_sha256:", content)
        self.assertIn("code_commit:", content)

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

    def test_assembly_import_accepts_optional_detail_metadata(self):
        call_command(*self.command_args("import_assembly_manifest", self.assembly_metadata_manifest()))

        assembly = Assembly.objects.get(assembly_code="ASM_IR64")
        self.assertEqual(assembly.biosample_accession, "SAMN04274565")
        self.assertEqual(assembly.assembly_type, "haploid")
        self.assertEqual(assembly.assembly_method, "hifiasm v0.19.8")
        self.assertEqual(assembly.sequencing_technology, "PacBio HiFi")
        self.assertEqual(assembly.genome_size, 387400000)
        self.assertEqual(assembly.chromosome_count, 12)
        self.assertEqual(assembly.contig_count, 19)
        self.assertEqual(assembly.n50, 27000000)
        self.assertEqual(assembly.gc_content, Decimal("43.500"))

    def test_assembly_import_rejects_invalid_integer_metadata(self):
        manifest = self.assembly_metadata_manifest(genome_size="387.4 Mb")

        call_command(*self.command_args("import_assembly_manifest", manifest))

        self.assertFalse(Assembly.objects.exists())
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn(
            "invalid genome_size: expected a non-negative integer",
            error_report.read_text(encoding="utf-8"),
        )

    def test_assembly_import_rejects_negative_statistics(self):
        manifest = self.assembly_metadata_manifest(genome_size="-1")

        call_command(*self.command_args("import_assembly_manifest", manifest))

        self.assertFalse(Assembly.objects.exists())
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn(
            "invalid genome_size: expected a non-negative integer",
            error_report.read_text(encoding="utf-8"),
        )

    def test_assembly_import_rejects_out_of_range_gc_content(self):
        manifest = self.assembly_metadata_manifest(gc_content="100.001")

        call_command(*self.command_args("import_assembly_manifest", manifest))

        self.assertFalse(Assembly.objects.exists())
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn(
            "invalid gc_content: expected a percentage from 0 to 100",
            error_report.read_text(encoding="utf-8"),
        )

    def test_assembly_model_validates_statistics_ranges(self):
        assembly = Assembly(
            assembly_code="ASM_INVALID",
            accession=self.accession,
            name="Invalid statistics",
            genome_size=-1,
            chromosome_count=-1,
            contig_count=-1,
            n50=-1,
            gc_content=Decimal("100.001"),
        )

        with self.assertRaises(ValidationError) as context:
            assembly.full_clean()

        self.assertEqual(
            set(context.exception.message_dict),
            {"genome_size", "chromosome_count", "contig_count", "n50", "gc_content"},
        )

    def test_annotation_import_reports_missing_assembly_without_writing(self):
        call_command(*self.command_args("import_annotation_manifest", self.annotation_manifest()))
        self.assertFalse(Annotation.objects.exists())

    def test_assembly_import_fills_blanks_and_preserves_curated_metadata(self):
        assembly = Assembly.objects.create(
            assembly_code="ASM_IR64",
            accession=self.accession,
            name="Curated assembly name",
            source_database="CuratedDB",
            file_name=None,
        )

        call_command(*self.command_args("import_assembly_manifest", self.assembly_manifest()))

        assembly.refresh_from_db()
        self.assertEqual(assembly.name, "Curated assembly name")
        self.assertEqual(assembly.source_database, "CuratedDB")
        self.assertEqual(assembly.file_name, "genome.IR64.fasta")
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn("metadata conflict", error_report.read_text(encoding="utf-8"))

    def test_assembly_import_fills_new_blanks_and_preserves_curated_statistics(self):
        assembly = Assembly.objects.create(
            assembly_code="ASM_IR64",
            accession=self.accession,
            name="IR64 genome assembly",
            genome_size=390000000,
        )

        call_command(*self.command_args("import_assembly_manifest", self.assembly_metadata_manifest()))

        assembly.refresh_from_db()
        self.assertEqual(assembly.biosample_accession, "SAMN04274565")
        self.assertEqual(assembly.genome_size, 390000000)
        self.assertEqual(assembly.chromosome_count, 12)
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn("genome_size", error_report.read_text(encoding="utf-8"))

    def test_annotation_import_fills_blanks_and_preserves_curated_metadata(self):
        assembly = Assembly.objects.create(
            assembly_code="ASM_IR64",
            accession=self.accession,
            name="IR64 assembly",
        )
        annotation = Annotation.objects.create(
            annotation_code="ANN_IR64",
            accession=None,
            assembly=assembly,
            name="Curated annotation name",
            source_database="CuratedDB",
            file_name=None,
        )

        call_command(*self.command_args("import_annotation_manifest", self.annotation_manifest()))

        annotation.refresh_from_db()
        self.assertEqual(annotation.accession, self.accession)
        self.assertEqual(annotation.name, "Curated annotation name")
        self.assertEqual(annotation.source_database, "CuratedDB")
        self.assertEqual(annotation.file_name, "annotation.IR64.gff")
        error_report = next(Path(self.temp_dir.name).glob("import_annotation_manifest_errors_*.tsv"))
        self.assertIn("metadata conflict", error_report.read_text(encoding="utf-8"))

    def test_assembly_identity_conflict_does_not_move_existing_record(self):
        other = Accession.objects.create(accession="OTHER", species=self.species)
        assembly = Assembly.objects.create(
            assembly_code="ASM_IR64",
            accession=other,
            name="Other assembly",
        )

        call_command(*self.command_args("import_assembly_manifest", self.assembly_manifest()))

        assembly.refresh_from_db()
        self.assertEqual(assembly.accession, other)
        error_report = next(Path(self.temp_dir.name).glob("import_assembly_manifest_errors_*.tsv"))
        self.assertIn("identity conflict", error_report.read_text(encoding="utf-8"))

    def test_annotation_identity_conflict_does_not_move_existing_record(self):
        target_assembly = Assembly.objects.create(
            assembly_code="ASM_IR64",
            accession=self.accession,
            name="Target assembly",
        )
        other_assembly = Assembly.objects.create(
            assembly_code="ASM_OTHER",
            accession=self.accession,
            name="Other assembly",
        )
        annotation = Annotation.objects.create(
            annotation_code="ANN_IR64",
            accession=self.accession,
            assembly=other_assembly,
            name="Other annotation",
        )

        call_command(*self.command_args("import_annotation_manifest", self.annotation_manifest()))

        annotation.refresh_from_db()
        self.assertEqual(annotation.assembly, other_assembly)
        self.assertNotEqual(annotation.assembly, target_assembly)
        error_report = next(Path(self.temp_dir.name).glob("import_annotation_manifest_errors_*.tsv"))
        self.assertIn("identity conflict", error_report.read_text(encoding="utf-8"))
