import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Project,
    Sample,
    Species,
)


class AuditDataFileAssetMappingReadinessTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.output = Path(self.temporary_directory.name) / "reports"

        species = Species.objects.create(species_code="ORYZA")
        project = Project.objects.create(project_code="RICE")
        self.accession = Accession.objects.create(accession="ACC_A", species=species)
        self.other_accession = Accession.objects.create(
            accession="ACC_B", species=species
        )
        self.unmapped_accession = Accession.objects.create(
            accession="ACC_UNMAPPED", species=species
        )
        self.genome = self.make_dataset("DS_GENOME", "genome", project, species)
        self.transcriptome = self.make_dataset(
            "DS_TRANSCRIPTOME", "transcriptome", project, species
        )
        self.hic = self.make_dataset("DS_HIC", "hic", project, species)
        for dataset in (self.genome, self.transcriptome, self.hic):
            DatasetAccession.objects.create(
                dataset=dataset, accession=self.accession, relation_role="primary"
            )

        assembly = Assembly.objects.create(accession=self.accession)
        annotation = Annotation.objects.create(assembly=assembly, accession=self.accession)
        conflicting_annotation = Annotation.objects.create(
            assembly=assembly,
            accession=self.other_accession,
            name="conflicting",
        )
        sample_without_accession = Sample.objects.create(sample_code="SAMPLE_NO_ACC")

        self.relate(self.make_file("GENOME"), "accession", self.accession.id, "genome_fasta")
        self.relate(
            self.make_file("TRANSCRIPTOME"),
            "assembly",
            assembly.id,
            "transcriptome_matrix",
        )
        self.relate(self.make_file("HIC"), "accession", self.accession.id, "hic_matrix")
        self.relate(
            self.make_file("ANNOTATION"),
            "annotation",
            annotation.id,
            "annotation_gff3",
        )
        self.relate(
            self.make_file("SAMPLE_NO_ACC"),
            "sample",
            sample_without_accession.id,
            "raw_reads",
        )
        self.relate(self.make_file("OTHER"), "other", "external-1", "other")
        self.relate(self.make_file("INVALID"), "assembly", "not-an-id", "genome")
        self.relate(
            self.make_file("NO_DATASET"),
            "accession",
            self.unmapped_accession.id,
            "genome",
        )
        self.relate(
            self.make_file("ANNOTATION_CONFLICT"),
            "annotation",
            conflicting_annotation.id,
            "annotation",
        )
        self.make_file("CURRENT", dataset=self.genome)
        self.make_file("NO_RELATION")

    @staticmethod
    def make_dataset(code, dataset_type, project, species):
        return Dataset.objects.create(
            dataset_code=code,
            dataset_type=dataset_type,
            project=project,
            species=species,
        )

    @staticmethod
    def make_file(code, dataset=None):
        return DataFile.objects.create(
            file_code=code,
            file_name=f"{code}.dat",
            file_path=f"/private/secret/{code}.dat",
            dataset=dataset,
        )

    @staticmethod
    def relate(data_file, related_type, related_id, file_role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=file_role,
        )

    def read_rows(self, name):
        path = self.output / f"datafile_t1_{name}.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_writes_explainable_read_only_candidates_without_physical_paths(self):
        before = self.snapshot()
        stdout = StringIO()

        call_command(
            "audit_datafile_asset_mapping_readiness",
            "--output-dir",
            str(self.output),
            stdout=stdout,
        )

        self.assertEqual(before, self.snapshot())
        self.assertIn("mode\tREAD_ONLY", stdout.getvalue())
        self.assertEqual(
            {path.name for path in self.output.glob("*.tsv")},
            {
                "datafile_t1_summary.tsv",
                "datafile_t1_files.tsv",
                "datafile_t1_relations.tsv",
            },
        )

        files = {row["file_code"]: row for row in self.read_rows("files")}
        self.assertEqual(files["GENOME"]["classification"], "unique_type_candidate")
        self.assertEqual(files["GENOME"]["type_compatible_candidates"], "DS_GENOME")
        self.assertEqual(
            files["TRANSCRIPTOME"]["type_compatible_candidates"], "DS_TRANSCRIPTOME"
        )
        self.assertEqual(files["HIC"]["type_compatible_candidates"], "DS_HIC")
        self.assertEqual(files["ANNOTATION"]["classification"], "needs_semantic_rule")
        self.assertEqual(files["SAMPLE_NO_ACC"]["classification"], "no_accession_context")
        self.assertIn("unresolved_relation_type", files["OTHER"]["issues"])
        self.assertEqual(files["INVALID"]["classification"], "invalid_context")
        self.assertEqual(files["NO_DATASET"]["classification"], "no_dataset_candidate")
        self.assertEqual(
            files["ANNOTATION_CONFLICT"]["classification"], "invalid_context"
        )
        self.assertEqual(files["CURRENT"]["classification"], "current_context_aligned")
        self.assertIn("no_ownership_relation", files["NO_RELATION"]["issues"])

        summary = {row["metric"]: int(row["value"]) for row in self.read_rows("summary")}
        self.assertEqual(summary["datafile_total"], 11)
        self.assertEqual(summary["file_relation_total"], 9)
        self.assertEqual(summary["file_classification:unique_type_candidate"], 3)
        self.assertEqual(summary["file_classification:invalid_context"], 2)

        for path in self.output.glob("*.tsv"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("/private/secret", content)
            self.assertNotIn("file_path", content)
            self.assertNotIn("file_name", content)

    def test_refuses_to_overwrite_existing_reports(self):
        call_command(
            "audit_datafile_asset_mapping_readiness",
            "--output-dir",
            str(self.output),
            stdout=StringIO(),
        )

        with self.assertRaises(CommandError):
            call_command(
                "audit_datafile_asset_mapping_readiness",
                "--output-dir",
                str(self.output),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    @staticmethod
    def snapshot():
        return (
            Dataset.objects.count(),
            DatasetAccession.objects.count(),
            DataFile.objects.count(),
            FileRelation.objects.count(),
        )
