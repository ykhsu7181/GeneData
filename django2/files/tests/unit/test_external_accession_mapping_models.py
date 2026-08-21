from django.test import TestCase

from files.models import Accession, AccessionExternalMapping, Dataset, Sample, Species


class ExternalAccessionMappingModelsTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(species_code="ORYZA_RUFIPOGON_TEST")
        self.accession = Accession.objects.create(
            accession="RUFIPOGON_TEST",
            species=self.species,
        )

    def test_external_mapping_stores_ena_identifiers_and_fastq_metadata(self):
        mapping = AccessionExternalMapping.objects.create(
            accession=self.accession,
            external_database="ENA",
            external_study_accession="PRJEB73710",
            biosample_accession="SAMEA115396740",
            experiment_accession="ERX123456",
            run_accession="ERR123456",
            scientific_name="Oryza rufipogon",
            library_strategy="Hi-C",
            instrument_platform="ILLUMINA",
            instrument_model="NovaSeq 6000",
            fastq_url="https://example.org/ERR123456_1.fastq.gz",
            fastq_md5="a83f21cc91de42b88a0e8e3d17d91de42",
        )

        self.assertEqual(mapping.accession_id, self.accession.id)
        self.assertEqual(mapping.external_study_accession, "PRJEB73710")
        self.assertEqual(mapping.library_strategy, "Hi-C")

    def test_sample_and_dataset_store_external_study_identifiers(self):
        sample = Sample.objects.create(
            sample_code="RUFIPOGON_TEST_LEAF",
            accession=self.accession,
            species=self.species,
            biosample_accession="SAMEA115396740",
            experiment_accession="ERX123456",
        )
        dataset = Dataset.objects.create(
            dataset_code="PRJEB73710_TEST",
            dataset_type="hic",
            species=self.species,
            bioproject_accession="PRJEB73710",
        )

        self.assertEqual(sample.biosample_accession, "SAMEA115396740")
        self.assertEqual(sample.experiment_accession, "ERX123456")
        self.assertEqual(dataset.bioproject_accession, "PRJEB73710")
