from django.test import TestCase

from files.models import Accession, Dataset, DatasetAccession, Project, Species
from files.services.accession_detail_service import (
    get_accession_datasets,
    get_accession_summary,
)


class AccessionDetailDatasetLinksTestCase(TestCase):
    def setUp(self):
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="W0137", species=species)
        project = Project.objects.create(project_code="PRJEB73710")
        self.dataset = Dataset.objects.create(
            dataset_code="PRJEB73710_W0137_RNASEQ",
            dataset_name="W0137 RNA-seq",
            dataset_type="transcriptome",
            bioproject_accession="PRJEB73710",
            species=species,
            project=project,
        )

    def test_explicit_dataset_accession_link_is_returned_without_datafile_dataset(self):
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
            relation_role="primary",
            source="PRJEB73710",
        )

        result = get_accession_datasets(self.accession)

        self.assertEqual(result["pagination"]["total"], 1)
        self.assertEqual(result["results"][0]["dataset_code"], "PRJEB73710_W0137_RNASEQ")
        self.assertEqual(result["results"][0]["relation_role"], "primary")
        self.assertEqual(result["results"][0]["relation_source"], "PRJEB73710")

    def test_summary_counts_explicit_dataset_accession_link(self):
        DatasetAccession.objects.create(dataset=self.dataset, accession=self.accession)

        result = get_accession_summary(self.accession)

        self.assertEqual(result["summary"]["dataset_count"], 1)
