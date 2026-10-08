from decimal import Decimal

from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, Species


class AssemblyDetailApiTestCase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            species_code="ORYZA_SATIVA",
            scientific_name="Oryza sativa",
            chinese_name="水稻",
        )
        self.accession = Accession.objects.create(
            accession="IR64",
            species=self.species,
            sub_population="GJ",
        )
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            assembly_code="ASM_IR64_DEFAULT",
            assembly_name="IR64 default",
            assembly_accession="GCA_001",
            assembly_level="Chromosome",
            biosample_accession="SAMN001",
            assembly_type="haploid",
            assembly_method="hifiasm",
            sequencing_technology="PacBio HiFi",
            genome_size=387400000,
            chromosome_count=12,
            contig_count=19,
            n50=27000000,
            gc_content=Decimal("43.500"),
            at_content=Decimal("56.500"),
            n_count=1200,
            n_percentage=Decimal("0.310"),
            sequence_count=12,
            sequence_md5="0123456789abcdef0123456789abcdef",
            gap_count=18,
            is_default=True,
        )
        self.related_assembly = Assembly.objects.create(
            accession=self.accession,
            name="v2-polish",
            assembly_code="ASM_IR64_V2",
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="default-annotation",
            annotation_code="ANN_IR64_DEFAULT",
            is_default=True,
        )
        self.related_annotation = Annotation.objects.create(
            assembly=self.related_assembly,
            accession=self.accession,
            name="v2-annotation",
            annotation_code="ANN_IR64_V2",
        )
        self.other_accession = Accession.objects.create(accession="OTHER", species=self.species)
        self.other_assembly = Assembly.objects.create(
            accession=self.other_accession,
            name="default",
            assembly_code="ASM_OTHER",
            is_default=True,
        )

    def create_file(self, code, name=None, *, is_current=True):
        return DataFile.objects.create(
            file_code=code,
            file_name=name or f"{code}.dat",
            file_path=f"/data/{code}.dat",
            is_current=is_current,
        )

    @staticmethod
    def relate(data_file, related_type, related_id, role, *, is_primary=False):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=is_primary,
        )

    def summary_url(self, assembly=None):
        return f"/gd/api/files/assemblies/{(assembly or self.assembly).id}/summary/"

    def test_summary_returns_current_context_and_primary_download(self):
        genome_file = self.create_file("GENOME_IR64", "genome.IR64.fasta")
        self.relate(
            genome_file,
            "assembly",
            self.assembly.id,
            "genome_fasta",
            is_primary=True,
        )

        response = self.client.get(self.summary_url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["assembly"]["id"], self.assembly.id)
        self.assertEqual(data["assembly"]["accession"], "IR64")
        self.assertEqual(data["assembly"]["biosample_accession"], "SAMN001")
        self.assertEqual(data["species"]["scientific_name"], "Oryza sativa")
        self.assertEqual(data["sub_population"], "GJ")
        self.assertEqual(data["statistics"]["genome_size"], 387400000)
        self.assertEqual(data["statistics"]["gc_content"], 43.5)
        self.assertEqual(data["statistics"]["at_content"], 56.5)
        self.assertEqual(data["statistics"]["n_count"], 1200)
        self.assertEqual(data["statistics"]["sequence_count"], 12)
        self.assertEqual(
            data["statistics"]["sequence_md5"],
            "0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(data["statistics"]["gap_count"], 18)
        self.assertEqual(
            {item["id"] for item in data["annotations"]},
            {self.annotation.id},
        )
        self.assertEqual(
            {item["id"] for item in data["related_assemblies"]},
            {self.assembly.id, self.related_assembly.id},
        )
        self.assertEqual(
            data["genome_download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )
        self.assertEqual(
            data["related_files_url"],
            "/gd/api/files/accessions/IR64/files/",
        )

    def test_summary_returns_null_for_missing_statistics_and_genome_file(self):
        response = self.client.get(self.summary_url(self.related_assembly))

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIsNone(data["genome_download_url"])
        self.assertEqual(data["statistics"], {
            "genome_size": None,
            "n50": None,
            "gc_content": None,
            "at_content": None,
            "n_count": None,
            "n_percentage": None,
            "chromosome_count": None,
            "sequence_count": None,
            "sequence_md5": None,
            "gap_count": None,
            "assembly_level": None,
        })

    def test_summary_returns_404_for_unknown_assembly(self):
        response = self.client.get("/gd/api/files/assemblies/999999/summary/")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_summary_downloads_named_fasta_with_legacy_genome_role(self):
        genome_file = self.create_file("GENOME_IR64_LEGACY", "genome.IR64.fasta")
        self.relate(genome_file, "assembly", self.assembly.id, "genome")

        response = self.client.get(self.summary_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["genome_download_url"],
            f"/gd/api/files/data-files/{genome_file.id}/download/",
        )

    def test_summary_returns_409_for_multiple_primary_genome_files(self):
        for suffix in ("A", "B"):
            data_file = self.create_file(f"GENOME_{suffix}")
            self.relate(
                data_file,
                "assembly",
                self.assembly.id,
                "genome_fasta",
                is_primary=True,
            )

        response = self.client.get(self.summary_url())

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()["success"])
        self.assertIn("multiple current primary", response.json()["detail"])

    def test_related_files_endpoint_stays_within_accession_scope(self):
        in_scope = {
            "ACCESSION_FILE": ("accession", self.accession.id),
            "ASSEMBLY_FILE": ("assembly", self.assembly.id),
            "RELATED_ASSEMBLY_FILE": ("assembly", self.related_assembly.id),
            "ANNOTATION_FILE": ("annotation", self.annotation.id),
            "RELATED_ANNOTATION_FILE": ("annotation", self.related_annotation.id),
        }
        for code, (related_type, related_id) in in_scope.items():
            self.relate(self.create_file(code), related_type, related_id, "other")

        outside_file = self.create_file("OTHER_ACCESSION_FILE")
        self.relate(outside_file, "assembly", self.other_assembly.id, "other")
        dataset_only_file = self.create_file("DATASET_ONLY_FILE")
        self.relate(dataset_only_file, "dataset", 999, "other")

        shared_file = self.create_file("SHARED_FILE")
        self.relate(shared_file, "assembly", self.assembly.id, "other")
        self.relate(shared_file, "assembly", self.other_assembly.id, "other")

        response = self.client.get(
            "/gd/api/files/accessions/IR64/files/",
            {"page_size": 100},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]["results"]
        returned_codes = {row["file_code"] for row in rows}
        self.assertEqual(returned_codes, {*in_scope, "SHARED_FILE"})
        shared_row = next(row for row in rows if row["file_code"] == "SHARED_FILE")
        self.assertEqual(len(shared_row["relations"]), 1)
        self.assertEqual(shared_row["relations"][0]["related_id"], str(self.assembly.id))
