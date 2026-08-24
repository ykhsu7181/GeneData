import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, AccessionExternalMapping, Dataset, Project, Sample, Species


class PRJEBRelationshipValidationTests(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.species = Species.objects.create(species_code="ORYZA_SATIVA", scientific_name="Oryza sativa")
        self.accession = Accession.objects.create(accession="IR64", species=self.species)
        project = Project.objects.create(project_code="PRJEB73710")
        Dataset.objects.create(
            dataset_code="PRJEB73710_IR64_RNA",
            dataset_type="transcriptome",
            bioproject_accession="PRJEB73710",
            species=self.species,
            project=project,
        )
        Sample.objects.create(
            sample_code="ERX12707172",
            accession=self.accession,
            species=self.species,
            experiment_accession="ERX12707172",
        )
        AccessionExternalMapping.objects.create(
            accession=self.accession,
            external_database="ENA",
            external_study_accession="ERP158450",
            experiment_accession="ERX12707172",
            run_accession="ERR13336206",
        )

    def test_validation_passes_and_is_read_only(self):
        before = self._counts()
        call_command("validate_prjeb73710_relationships", output_dir=self.output_dir.name)
        self.assertEqual(before, self._counts())
        report = self._single_report(".txt")
        self.assertIn("status: PASS", open(report, encoding="utf-8").read())

    def test_validation_reports_missing_sample_species(self):
        Sample.objects.update(species=None)
        call_command("validate_prjeb73710_relationships", output_dir=self.output_dir.name)
        details = self._single_report(".tsv")
        self.assertIn("missing species", open(details, encoding="utf-8").read())

    def _counts(self):
        return {
            "accession": Accession.objects.count(),
            "dataset": Dataset.objects.count(),
            "sample": Sample.objects.count(),
            "mapping": AccessionExternalMapping.objects.count(),
        }

    def _single_report(self, suffix):
        reports = [
            os.path.join(self.output_dir.name, name)
            for name in os.listdir(self.output_dir.name)
            if name.startswith("prjeb_relationship_validation_") and name.endswith(suffix)
        ]
        self.assertEqual(len(reports), 1)
        return reports[0]
