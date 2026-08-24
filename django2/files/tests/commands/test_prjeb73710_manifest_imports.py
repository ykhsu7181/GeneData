import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, AccessionExternalMapping, Dataset, Project, Sample, Species


class PRJEB73710ManifestImportTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(accession="IR64", species=self.species)

    def write_manifest(self, header, row):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", encoding="utf-8", delete=False, newline="")
        handle.write(header + "\n" + row + "\n")
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_import_dataset_manifest_creates_project_and_dataset_idempotently(self):
        path = self.write_manifest(
            "accession\tproject_code\tproject_name\tdataset_code\tdataset_name\tdataset_type\tncbi_bioproject\tdescription",
            "IR64\tPRJEB73710\tRice project\tPRJEB73710_IR64_RNA\tIR64 RNA-seq\ttranscriptome\tPRJEB73710\tImported from ENA",
        )
        call_command("import_dataset_manifest", "--input", path)
        call_command("import_dataset_manifest", "--input", path)

        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Dataset.objects.count(), 1)
        dataset = Dataset.objects.get(dataset_code="PRJEB73710_IR64_RNA")
        self.assertEqual(dataset.project.project_code, "PRJEB73710")
        self.assertEqual(dataset.species, self.species)
        self.assertEqual(dataset.bioproject_accession, "PRJEB73710")

    def test_import_sample_manifest_accepts_accession_column_and_external_ids(self):
        path = self.write_manifest(
            "sample_code\tsample_name\tspecies_code\taccession\ttissue\tdata_type\tbiosample_accession\texperiment_accession",
            "ERX12707172\tIR64 leaf\tORYZA_SATIVA\tIR64\tleaf\tRNA-Seq\tSAMEA115396723\tERX12707172",
        )
        call_command("import_sample_manifest", "--input", path)

        sample = Sample.objects.get(sample_code="ERX12707172")
        self.assertEqual(sample.accession, self.accession)
        self.assertEqual(sample.biosample_accession, "SAMEA115396723")
        self.assertEqual(sample.experiment_accession, "ERX12707172")

    def test_import_external_mapping_manifest_is_idempotent(self):
        path = self.write_manifest(
            "accession\tena_study\tbiosample\texperiment\trun\tscientific_name\tlibrary_strategy\tinstrument_platform\tinstrument_model\tfastq_ftp\tfastq_md5",
            "IR64\tERP158450\tSAMEA115396723\tERX12707172\tERR13336206\tOryza sativa\tRNA-Seq\tILLUMINA\tHiSeq 4000\tftp://example.org/ERR13336206.fastq.gz\tabc123",
        )
        call_command("import_accession_external_mapping_manifest", "--input", path)
        call_command("import_accession_external_mapping_manifest", "--input", path)

        self.assertEqual(AccessionExternalMapping.objects.count(), 1)
        mapping = AccessionExternalMapping.objects.get(accession=self.accession)
        self.assertEqual(mapping.external_database, "ENA")
        self.assertEqual(mapping.run_accession, "ERR13336206")
        self.assertEqual(mapping.fastq_url, "ftp://example.org/ERR13336206.fastq.gz")

    def test_import_external_mapping_splits_paired_fastq_checksums(self):
        path = self.write_manifest(
            "accession\tena_study\tbiosample\texperiment\trun\tfastq_ftp\tfastq_md5",
            "IR64\tERP158450\tSAMEA115396723\tERX12707172\tERR13336206\tftp://example.org/R1.fastq.gz;ftp://example.org/R2.fastq.gz\t0123456789abcdef0123456789abcdef;abcdef0123456789abcdef0123456789",
        )
        call_command("import_accession_external_mapping_manifest", "--input", path)

        mappings = AccessionExternalMapping.objects.filter(accession=self.accession)
        self.assertEqual(mappings.count(), 2)
        self.assertEqual({item.fastq_md5 for item in mappings}, {
            "0123456789abcdef0123456789abcdef",
            "abcdef0123456789abcdef0123456789",
        })
