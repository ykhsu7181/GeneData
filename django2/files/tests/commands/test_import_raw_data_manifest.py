import os
import tempfile
import uuid
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, DataFile, FileRelation, Sample, Species
from files.management.commands.import_raw_data_manifest import Command


class ImportRawDataManifestTestCase(TestCase):
    def setUp(self):
        self.suffix = uuid.uuid4().hex[:8]
        self.species = Species.objects.create(
            species_code=f"RICE_{self.suffix}",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            species=self.species,
            accession=f"IR64_{self.suffix}",
            sub_population="XI",
        )
        self.sample = Sample.objects.create(
            sample_code=f"IR64_leaf_01_{self.suffix}",
            species=self.species,
            accession=self.accession,
            tissue="leaf",
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manifest_path = os.path.join(self.temp_dir.name, "raw_data.tsv")

    def write_manifest(self, file_path, *, accession_code=None, sample_code=None, file_role="raw_reads_R1"):
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            handle.write(
                "\t".join(
                    [
                        "accession_code",
                        "sample_code",
                        "species_code",
                        "raw_data_type",
                        "sequencing_platform",
                        "file_role",
                        "cluster_name",
                        "file_path",
                        "file_size",
                        "md5",
                        "check_status",
                        "remark",
                    ]
                )
                + "\n"
            )
            handle.write(
                "\t".join(
                    [
                        self.accession.accession if accession_code is None else accession_code,
                        self.sample.sample_code if sample_code is None else sample_code,
                        self.species.species_code,
                        "RNA-seq",
                        "Illumina",
                        file_role,
                        "cluster01",
                        file_path,
                        "128",
                        "a83f21cc91de42b88a0e8e3d17d91de42",
                        "verified",
                        "leaf paired-end reads",
                    ]
                )
                + "\n"
            )

    def test_dry_run_does_not_write_database(self):
        self.write_manifest("/data/project/rice/raw/IR64_leaf_01_R1.fastq.gz")

        call_command("import_raw_data_manifest", "--input", self.manifest_path, "--dry-run")

        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_import_creates_datafile_and_new_relations_idempotently(self):
        raw_path = "/data/project/rice/raw/IR64_leaf_01_R1.fastq.gz"
        self.write_manifest(raw_path)

        call_command("import_raw_data_manifest", "--input", self.manifest_path)
        call_command("import_raw_data_manifest", "--input", self.manifest_path)

        self.assertEqual(DataFile.objects.count(), 1)
        data_file = DataFile.objects.get()
        self.assertEqual(data_file.file_path, raw_path)
        self.assertEqual(data_file.file_name, "IR64_leaf_01_R1.fastq.gz")
        self.assertEqual(data_file.file_size, 128)
        self.assertEqual(data_file.md5, "a83f21cc91de42b88a0e8e3d17d91de42")
        self.assertIn('"raw_data_type": "RNA-seq"', data_file.description)

        self.assertEqual(
            FileRelation.objects.filter(
                file=data_file,
                related_type="accession",
                related_id=str(self.accession.id),
                file_role="raw_reads_R1",
            ).count(),
            1,
        )

    def test_import_marks_existing_datafile_with_raw_data_metadata(self):
        raw_path = "/data/project/rice/raw/IR64_leaf_01_R1.fastq.gz"
        DataFile.objects.create(
            file_code=f"EXIST{self.suffix}",
            file_name="IR64_leaf_01_R1.fastq.gz",
            file_path=raw_path,
            description=json.dumps({"note": "existing metadata"}, ensure_ascii=False),
        )
        self.write_manifest(raw_path)

        call_command("import_raw_data_manifest", "--input", self.manifest_path)

        self.assertEqual(DataFile.objects.count(), 1)
        data_file = DataFile.objects.get()
        payload = json.loads(data_file.description)
        self.assertEqual(payload["note"], "existing metadata")
        self.assertEqual(payload["raw_data"]["raw_data_type"], "RNA-seq")
        self.assertEqual(payload["raw_data"]["sequencing_platform"], "Illumina")
        self.assertEqual(payload["raw_data"]["cluster_name"], "cluster01")
        self.assertEqual(
            FileRelation.objects.filter(
                file=data_file,
                related_type="sample",
                related_id=str(self.sample.id),
                file_role="raw_reads_R1",
            ).count(),
            1,
        )

    def test_unknown_accession_does_not_create_datafile(self):
        self.write_manifest("/raw/unknown-accession.fastq.gz", accession_code="UNKNOWN")
        call_command("import_raw_data_manifest", "--input", self.manifest_path)
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_unknown_sample_does_not_create_datafile(self):
        self.write_manifest("/raw/unknown-sample.fastq.gz", sample_code="UNKNOWN")
        call_command("import_raw_data_manifest", "--input", self.manifest_path)
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_no_relation_target_does_not_create_datafile(self):
        self.write_manifest("/raw/no-target.fastq.gz", accession_code="", sample_code="")
        call_command("import_raw_data_manifest", "--input", self.manifest_path)
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_invalid_role_does_not_create_datafile(self):
        self.write_manifest("/raw/invalid-role.fastq.gz", file_role="not_canonical")
        call_command("import_raw_data_manifest", "--input", self.manifest_path)
        self.assertEqual(DataFile.objects.count(), 0)
        self.assertEqual(FileRelation.objects.count(), 0)

    def test_relation_failure_rolls_back_new_datafile(self):
        row = {
            "file_path": "/raw/relation-failure.fastq.gz",
            "file_role": "raw_reads_R1",
            "accession_code": self.accession.accession,
        }

        with patch(
            "files.services.file_write_service.FileRelation.objects.get_or_create",
            side_effect=RuntimeError("failed"),
        ):
            with self.assertRaises(RuntimeError):
                Command().import_row(row)

        self.assertFalse(DataFile.objects.filter(file_path=row["file_path"]).exists())
