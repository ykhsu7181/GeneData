import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import Accession, DataFile, Dataset, DatasetAccession, FileRelation


class PublishExternalDatasetsTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "protected"
        self.root.mkdir()
        self.output = Path(self.temporary_directory.name) / "reports"
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.accession = Accession.objects.create(accession="IR64")
        path = self.root / "annotation.IR64.gff"
        path.write_bytes(b"##gff-version 3\n")
        self.data_file = DataFile.objects.create(
            file_code="GFF_IR64",
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
        )
        FileRelation.objects.create(
            file=self.data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="annotation",
        )

    def manifest(self, sha256=None):
        path = Path(self.temporary_directory.name) / "dataset.tsv"
        path.write_text(
            "dataset_code\tdataset_name\tdataset_type\taccession\trelation_role\tfile_code\tfile_role\tis_primary\tsha256\n"
            f"DS_IR64\tIR64 reference\tgenome\tIR64\treference\tGFF_IR64\tannotation\tyes\t{sha256 or self.data_file.sha256}\n",
            encoding="utf-8",
        )
        return path

    def test_dry_run_apply_and_idempotent_reapply(self):
        manifest = self.manifest()
        dry_run = StringIO()
        call_command(
            "publish_external_datasets", manifest=manifest, output_dir=self.output,
            stdout=dry_run,
        )
        self.assertFalse(Dataset.objects.filter(dataset_code="DS_IR64").exists())
        self.assertIn("mode\tDRY_RUN", dry_run.getvalue())

        call_command(
            "publish_external_datasets", manifest=manifest, output_dir=self.output,
            apply=True, stdout=StringIO(),
        )
        dataset = Dataset.objects.get(dataset_code="DS_IR64")
        self.assertEqual((dataset.visibility, dataset.status), ("public", "released"))
        self.assertTrue(DatasetAccession.objects.filter(dataset=dataset, accession=self.accession).exists())
        self.assertTrue(FileRelation.objects.filter(
            file=self.data_file, related_type="dataset", related_id=str(dataset.id),
            file_role="annotation",
        ).exists())

        call_command(
            "publish_external_datasets", manifest=manifest, output_dir=self.output,
            apply=True, stdout=StringIO(),
        )
        self.assertEqual(Dataset.objects.filter(dataset_code="DS_IR64").count(), 1)
        self.assertEqual(DatasetAccession.objects.filter(dataset=dataset).count(), 1)

    def test_checksum_mismatch_blocks_entire_apply(self):
        with self.assertRaises(CommandError):
            call_command(
                "publish_external_datasets", manifest=self.manifest("0" * 64),
                output_dir=self.output, apply=True, stdout=StringIO(), stderr=StringIO(),
            )

        self.assertFalse(Dataset.objects.filter(dataset_code="DS_IR64").exists())

    def test_apply_can_promote_explicit_target_dataset_without_weakening_other_policies(self):
        dataset = Dataset.objects.create(
            dataset_code="DS_IR64",
            dataset_name="IR64 reference",
            dataset_type="genome",
            visibility="private",
            status="draft",
        )
        self.data_file.access_level = DataFile.ACCESS_LEVEL_INHERITED
        self.data_file.dataset = dataset
        self.data_file.save(update_fields=["access_level", "dataset", "updated_at"])

        call_command(
            "publish_external_datasets", manifest=self.manifest(),
            output_dir=self.output, apply=True, stdout=StringIO(),
        )

        dataset.refresh_from_db()
        self.assertEqual((dataset.visibility, dataset.status), ("public", "released"))

    def test_other_private_dataset_policy_blocks_publication(self):
        other = Dataset.objects.create(
            dataset_code="DS_OTHER_PRIVATE",
            visibility="private",
            status="released",
        )
        FileRelation.objects.create(
            file=self.data_file,
            related_type="dataset",
            related_id=str(other.id),
            file_role="annotation",
        )

        with self.assertRaises(CommandError):
            call_command(
                "publish_external_datasets", manifest=self.manifest(),
                output_dir=self.output, apply=True, stdout=StringIO(), stderr=StringIO(),
            )

        self.assertFalse(Dataset.objects.filter(dataset_code="DS_IR64").exists())
