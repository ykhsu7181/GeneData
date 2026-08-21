from django.test import TestCase

from files.models import Dataset


class DatasetTypeChoicesTestCase(TestCase):
    def test_hic_is_a_supported_dataset_type(self):
        choices = dict(Dataset._meta.get_field("dataset_type").choices)

        self.assertIn("hic", choices)
        self.assertEqual(choices["hic"], "Hi-C")

    def test_hic_passes_model_choice_validation(self):
        dataset = Dataset(dataset_code="DS_HIC_TEST", dataset_type="hic")

        dataset.full_clean()
