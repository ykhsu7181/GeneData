import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Dataset, DatasetAccession, Project, Species


class DatasetAccessionManifestImportTests(TestCase):
    def setUp(self):
        species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="IR64", species=species)
        project = Project.objects.create(project_code="PRJEB73710", project_name="ENA study")
        self.dataset = Dataset.objects.create(
            dataset_code="PRJEB73710_IR64_RNA",
            dataset_name="IR64 RNA-seq",
            dataset_type="transcriptome",
            project=project,
            species=species,
        )

    def write_manifest(self, rows):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", encoding="utf-8", delete=False, newline="")
        handle.write("accession\tdataset_code\tproject_code\trelation_role\n")
        handle.write(rows)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def call_import(self, *args):
        with patch("files.management.commands.import_dataset_accession_manifest.write_key_value_report"), patch(
            "files.management.commands.import_dataset_accession_manifest.Command.write_unmapped"
        ):
            call_command("import_dataset_accession_manifest", *args)

    def test_import_creates_dataset_accession_link_and_is_idempotent(self):
        path = self.write_manifest("IR64\tPRJEB73710_IR64_RNA\tPRJEB73710\tprimary\n")

        self.call_import("--input", path)
        self.call_import("--input", path)

        self.assertEqual(DatasetAccession.objects.count(), 1)
        link = DatasetAccession.objects.get(dataset=self.dataset, accession=self.accession)
        self.assertEqual(link.relation_role, "primary")
        self.assertEqual(link.source, "PRJEB73710")

    def test_dry_run_does_not_write_dataset_accession_link(self):
        path = self.write_manifest("IR64\tPRJEB73710_IR64_RNA\tPRJEB73710\tprimary\n")

        self.call_import("--input", path, "--dry-run")

        self.assertFalse(DatasetAccession.objects.exists())

    def test_missing_accession_or_dataset_does_not_create_link(self):
        path = self.write_manifest(
            "UNKNOWN\tPRJEB73710_IR64_RNA\tPRJEB73710\tprimary\n"
            "IR64\tUNKNOWN_DATASET\tPRJEB73710\tprimary\n"
        )

        self.call_import("--input", path)

        self.assertFalse(DatasetAccession.objects.exists())
