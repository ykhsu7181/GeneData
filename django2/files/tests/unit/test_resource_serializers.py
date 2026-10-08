from decimal import Decimal

from django.test import TestCase

from files.models import Accession, Annotation, Assembly
from files.services.resource_serializers import serialize_annotation, serialize_assembly


class ResourceSerializerTests(TestCase):
    def setUp(self):
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="legacy-name",
            assembly_code="ASM_IR64",
            assembly_name="IR64 assembly",
            assembly_accession="GCA_001",
            assembly_level="Chromosome",
            display_name="IR64 display",
            standard_id="STANDARD_ASM",
            bio_project="PRJEB73710",
            reference="Reference",
            source_database="GenBank",
            external_project="PROJECT",
            file_name="genome.IR64.fasta",
            file_type="FASTA",
            description="Assembly description",
            is_default=True,
            biosample_accession="SAMN001",
            assembly_type="haploid",
            assembly_method="hifiasm",
            sequencing_technology="PacBio HiFi",
            genome_size=387400000,
            chromosome_count=12,
            contig_count=19,
            n50=27000000,
            gc_content=Decimal("43.500"),
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="legacy-annotation",
            annotation_code="ANN_IR64",
            annotation_name="IR64 annotation",
            annotation_version="v2",
            display_name="IR64 annotation display",
            standard_id="STANDARD_ANN",
            source_name="MAKER",
            release_version="release-2",
            source_database="InterPro",
            external_project="PROJECT",
            file_name="annotation.IR64.gff3",
            file_type="GFF3",
            description="Annotation description",
            is_default=True,
        )

    def test_assembly_default_payload_preserves_accession_api_contract(self):
        payload = serialize_assembly(self.assembly)

        self.assertEqual(set(payload), {
            "id", "name", "assembly_code", "assembly_name", "assembly_accession",
            "assembly_level", "display_name", "standard_id", "bio_project",
            "reference", "source_database", "external_project", "file_name",
            "file_type", "description", "is_default",
        })
        self.assertEqual(payload["assembly_name"], "IR64 assembly")
        self.assertEqual(payload["assembly_accession"], "GCA_001")

    def test_assembly_detail_payload_adds_phase_one_metadata(self):
        payload = serialize_assembly(self.assembly, include_detail=True)

        self.assertEqual(payload["biosample_accession"], "SAMN001")
        self.assertEqual(payload["assembly_method"], "hifiasm")
        self.assertEqual(payload["genome_size"], 387400000)
        self.assertEqual(payload["gc_content"], Decimal("43.500"))

    def test_assembly_serializer_uses_legacy_fallback_priority(self):
        self.assembly.assembly_name = None
        self.assembly.assembly_accession = None

        payload = serialize_assembly(self.assembly)

        self.assertEqual(payload["assembly_name"], "IR64 display")
        self.assertEqual(payload["assembly_accession"], "STANDARD_ASM")

    def test_annotation_payload_preserves_accession_api_contract(self):
        payload = serialize_annotation(self.annotation, assembly=self.assembly)

        self.assertEqual(set(payload), {
            "id", "name", "annotation_code", "annotation_name", "annotation_version",
            "display_name", "standard_id", "source_name", "release_version",
            "source_database", "external_project", "file_name", "file_type",
            "description", "is_default", "assembly_id", "assembly_name",
        })
        self.assertEqual(payload["annotation_name"], "IR64 annotation")
        self.assertEqual(payload["annotation_version"], "v2")
        self.assertEqual(payload["assembly_name"], "IR64 display")

    def test_annotation_serializer_uses_legacy_fallback_priority(self):
        self.annotation.annotation_name = None
        self.annotation.annotation_version = None

        payload = serialize_annotation(self.annotation)

        self.assertEqual(payload["annotation_name"], "IR64 annotation display")
        self.assertEqual(payload["annotation_version"], "release-2")
