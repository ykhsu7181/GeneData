import os
import tempfile
import uuid

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, DataFile, FileRelation, Sample, Species


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

    def write_manifest(self, file_path):
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
                        self.accession.accession,
                        self.sample.sample_code,
                        self.species.species_code,
                        "RNA-seq",
                        "Illumina",
                        "raw_reads_R1",
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
        self.assertEqual(
            FileRelation.objects.filter(
                file=data_file,
                related_type="sample",
                related_id=str(self.sample.id),
                file_role="raw_reads_R1",
            ).count(),
            1,
        )
