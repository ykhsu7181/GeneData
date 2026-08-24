from django.db import IntegrityError, transaction
from django.test import TestCase

from files.models import Accession, Dataset, DatasetAccession, Species


class DatasetAccessionModelTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="TEST_SPECIES",
            chinese_name="测试物种",
            scientific_name="Test species",
        )
        self.accession = Accession.objects.create(
            accession="TEST_ACCESSION",
            species=self.species,
        )
        self.dataset = Dataset.objects.create(
            dataset_code="DS_TEST_ACCESSION",
            dataset_type="transcriptome",
            species=self.species,
        )

    def test_creates_explicit_dataset_accession_link(self):
        link = DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
            source="PRJEB73710",
        )

        self.assertEqual(link.relation_role, "primary")
        self.assertEqual(self.dataset.accession_links.get(), link)
        self.assertEqual(self.accession.dataset_links.get(), link)

    def test_same_dataset_accession_pair_cannot_be_duplicated(self):
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DatasetAccession.objects.create(
                    dataset=self.dataset,
                    accession=self.accession,
                )

    def test_allows_one_dataset_to_link_multiple_accessions(self):
        second_accession = Accession.objects.create(
            accession="TEST_ACCESSION_2",
            species=self.species,
        )
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=self.accession,
        )
        DatasetAccession.objects.create(
            dataset=self.dataset,
            accession=second_accession,
            relation_role="derived",
        )

        self.assertEqual(self.dataset.accession_links.count(), 2)
