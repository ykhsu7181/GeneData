from django.test import TestCase

from files.models import (
    Accession,
    AccessionExternalMapping,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    Sample,
    Species,
)


class AccessionCardApiTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            chinese_name="水稻",
            scientific_name="Oryza sativa",
        )
        self.accession = Accession.objects.create(
            accession="IR64",
            species=self.species,
            country="中国",
            region="湖北",
            longitude=114.3,
            latitude=30.5,
        )
        self.assembly = Assembly.objects.create(accession=self.accession, name="IR64 v1", is_default=True)
        self.annotation = Annotation.objects.create(assembly=self.assembly, name="IR64 annotation", is_default=True)
        self.dataset = Dataset.objects.create(
            dataset_code="DS-IR64-RNA",
            dataset_name="IR64 RNA-seq",
            dataset_type="transcriptome",
            bioproject_accession="PRJEB73710",
            species=self.species,
        )
        self.file_type = FileType.objects.create(name="FASTA", extension="fasta")
        self.file_obj = DataFile.objects.create(
            file_code="FILE-IR64-001",
            dataset=self.dataset,
            file_type=self.file_type,
            file_name="IR64.genome.fa",
            file_path="/data/IR64.genome.fa",
            file_size=1024,
        )
        FileRelation.objects.create(
            file=self.file_obj,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role="genome_fasta",
        )
        Sample.objects.create(
            sample_code="IR64-LEAF-01",
            sample_name="IR64 leaf sample",
            accession=self.accession,
            species=self.species,
            tissue="leaf",
            data_type="RNA-Seq",
            biosample_accession="SAMEA115396723",
            experiment_accession="ERX12707172",
        )
        AccessionExternalMapping.objects.create(
            accession=self.accession,
            external_database="ENA",
            external_study_accession="ERP158450",
            biosample_accession="SAMEA115396723",
            experiment_accession="ERX12707172",
            run_accession="ERR13336206",
        )

    def test_summary_returns_basic_geography_and_external_counts(self):
        response = self.client.get("/gd/api/files/accessions/IR64/summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["accession"]["species"]["species_code"], "ORYZA_SATIVA")
        self.assertTrue(data["geography"]["has_point"])
        self.assertEqual(data["external_identifiers"]["ena_studies"], ["ERP158450"])
        self.assertEqual(data["summary"]["file_count"], 1)

    def test_tab_endpoints_are_paginated_and_use_datafile_download(self):
        datasets = self.client.get("/gd/api/files/accessions/IR64/datasets/").json()["data"]
        samples = self.client.get("/gd/api/files/accessions/IR64/samples/").json()["data"]
        assemblies = self.client.get("/gd/api/files/accessions/IR64/assemblies/").json()["data"]
        annotations = self.client.get("/gd/api/files/accessions/IR64/annotations/").json()["data"]
        files = self.client.get("/gd/api/files/accessions/IR64/files/").json()["data"]

        self.assertEqual(datasets["results"][0]["bioproject_accession"], "PRJEB73710")
        self.assertEqual(datasets["results"][0]["external_database"], "ENA")
        self.assertEqual(datasets["results"][0]["run_count"], 1)
        self.assertEqual(samples["results"][0]["biosample_accession"], "SAMEA115396723")
        self.assertEqual(assemblies["results"][0]["name"], "IR64 v1")
        self.assertEqual(annotations["results"][0]["assembly_name"], "IR64 v1")
        self.assertEqual(files["results"][0]["source"], "new_relation")
        self.assertEqual(
            files["results"][0]["datafile_download_url"],
            f"/gd/api/files/data-files/{self.file_obj.id}/download/",
        )
        self.assertNotIn("/genome-files/", files["results"][0]["datafile_download_url"])
