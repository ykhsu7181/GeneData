from django.test import TestCase

from files.management.commands.import_accession_external_mapping_manifest import (
    Command as ExternalMappingCommand,
)
from files.management.commands.import_accession_manifest import Command as AccessionCommand
from files.management.commands.import_dataset_manifest import Command as DatasetCommand
from files.management.commands.import_sample_manifest import Command as SampleCommand
from files.models import (
    Accession, AccessionExternalMapping, Dataset, Project, Sample, Species,
)


class MetadataOverwritePolicyTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
        )
        self.other_species = Species.objects.create(
            species_code="ORYZA_NIVARA",
            scientific_name="Oryza nivara",
        )
        self.accession = Accession.objects.create(
            accession="IR64",
            species=self.species,
            country="China",
        )
        self.other_accession = Accession.objects.create(
            accession="NIVARA",
            species=self.other_species,
        )

    def test_accession_nonblank_metadata_conflict_preserves_curated_value(self):
        result = AccessionCommand().import_row(
            {
                "accession": "IR64",
                "species_code": self.species.species_code,
                "country": "Vietnam",
            },
            line_number=2,
        )

        self.accession.refresh_from_db()
        self.assertEqual(self.accession.country, "China")
        self.assertEqual({item["field"] for item in result["conflicts"]}, {"country"})

    def test_sample_metadata_and_ownership_conflicts_are_preserved(self):
        sample = Sample.objects.create(
            sample_code="S1",
            sample_name="Curated sample",
            species=self.species,
            accession=self.accession,
            tissue="root",
        )

        result = SampleCommand().import_row(
            {
                "sample_code": "S1",
                "sample_name": "Incoming sample",
                "species_code": self.other_species.species_code,
                "accession": self.other_accession.accession,
                "tissue": "leaf",
            },
            line_number=2,
        )

        sample.refresh_from_db()
        self.assertEqual(sample.accession, self.accession)
        self.assertEqual(sample.species, self.species)
        self.assertEqual(sample.tissue, "root")
        self.assertEqual(
            {item["field"] for item in result["conflicts"]},
            {"sample_name", "species", "accession", "tissue"},
        )

    def test_dataset_metadata_and_ownership_conflicts_are_preserved(self):
        project = Project.objects.create(project_code="P1", project_name="Curated project")
        Project.objects.create(project_code="P2", project_name="Incoming project")
        dataset = Dataset.objects.create(
            dataset_code="D1",
            dataset_name="Curated dataset",
            dataset_type="genome",
            species=self.species,
            project=project,
        )

        result = DatasetCommand().import_row(
            {
                "accession": self.other_accession.accession,
                "project_code": "P2",
                "dataset_code": "D1",
                "dataset_type": "annotation",
                "dataset_name": "Incoming dataset",
            },
            dry_run=False,
            line_number=2,
        )

        dataset.refresh_from_db()
        self.assertEqual(dataset.project, project)
        self.assertEqual(dataset.species, self.species)
        self.assertEqual(dataset.dataset_type, "genome")
        self.assertEqual(
            {item["field"] for item in result["conflicts"] if item["object_type"] == "dataset"},
            {"dataset_name", "dataset_type", "species", "project"},
        )

    def test_external_mapping_metadata_conflict_preserves_curated_value(self):
        mapping = AccessionExternalMapping.objects.create(
            accession=self.accession,
            external_database="ENA",
            external_study_accession="ERP1",
            run_accession="ERR1",
            instrument_model="PacBio Revio",
        )

        result = ExternalMappingCommand().import_row(
            {
                "accession": self.accession.accession,
                "ena_study": "ERP1",
                "run": "ERR1",
                "instrument_model": "Illumina NovaSeq",
            },
            dry_run=False,
            line_number=2,
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.instrument_model, "PacBio Revio")
        self.assertEqual(
            {item["field"] for item in result["conflicts"]},
            {"instrument_model"},
        )
