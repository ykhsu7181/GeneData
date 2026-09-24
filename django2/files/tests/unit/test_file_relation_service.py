from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_files_for_accession,
    get_files_for_annotation,
    get_files_for_assembly,
    get_files_for_object,
    get_primary_file,
    get_primary_genome_file_for_assembly,
)


class FileRelationServiceTestCase(TestCase):
    def setUp(self):
        self.file_type = FileType.objects.create(name="FASTA", extension="fasta")
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="default-annotation",
            is_default=True,
        )
        self.data_file = DataFile.objects.create(
            file_code="FILE000001",
            file_type=self.file_type,
            file_name="genome.IR64.fasta",
            file_path="/tmp/genome.IR64.fasta",
            file_size=1234,
            md5="abc123",
        )

    def add_relation(self, related_type, related_id, file_role="genome", is_primary=False):
        return FileRelation.objects.create(
            file=self.data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=file_role,
            is_primary=is_primary,
        )

    def add_assembly_genome_file(self, code, *, is_current=True, is_primary=False):
        data_file = DataFile.objects.create(
            file_code=code,
            file_type=self.file_type,
            file_name=f"{code}.fasta",
            file_path=f"/tmp/{code}.fasta",
            is_current=is_current,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role="genome_fasta",
            is_primary=is_primary,
        )
        return data_file

    def test_get_files_for_accession_returns_data_file(self):
        self.add_relation("accession", self.accession.id, file_role="genome")

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_id"], self.data_file.id)
        self.assertEqual(files[0]["file_code"], "FILE000001")
        self.assertEqual(files[0]["file_name"], "genome.IR64.fasta")
        self.assertEqual(files[0]["file_path"], "/tmp/genome.IR64.fasta")
        self.assertEqual(files[0]["file_size"], 1234)
        self.assertEqual(files[0]["md5"], "abc123")
        self.assertEqual(files[0]["file_role"], "genome")
        self.assertEqual(files[0]["related_type"], "accession")
        self.assertEqual(files[0]["related_id"], str(self.accession.id))
        self.assertEqual(files[0]["source"], "new_relation")

    def test_get_files_for_assembly_returns_data_file(self):
        self.add_relation("assembly", self.assembly.id, file_role="genome")

        files = get_files_for_assembly(self.assembly.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_id"], self.data_file.id)
        self.assertEqual(files[0]["related_type"], "assembly")
        self.assertEqual(files[0]["related_id"], str(self.assembly.id))
        self.assertEqual(files[0]["source"], "new_relation")

    def test_get_files_for_annotation_returns_data_file(self):
        self.add_relation("annotation", self.annotation.id, file_role="annotation")

        files = get_files_for_annotation(self.annotation.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_id"], self.data_file.id)
        self.assertEqual(files[0]["related_type"], "annotation")
        self.assertEqual(files[0]["related_id"], str(self.annotation.id))
        self.assertEqual(files[0]["source"], "new_relation")

    def test_file_role_filter_is_applied(self):
        self.add_relation("accession", self.accession.id, file_role="genome")
        transcript_file = DataFile.objects.create(
            file_code="FILE000002",
            file_name="transcriptome.root.IR64.tar.gz",
            file_path="/tmp/transcriptome.root.IR64.tar.gz",
        )
        FileRelation.objects.create(
            file=transcript_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="transcriptome.root",
        )

        files = get_files_for_accession(self.accession.id, file_role="transcriptome.root")

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_code"], "FILE000002")
        self.assertEqual(files[0]["file_role"], "transcriptome.root")

    def test_returns_empty_when_relation_missing_even_if_genome_file_exists(self):
        GenomeFile.objects.create(
            name="annotation.IR64.gff",
            organism="IR64",
            accession=self.accession,
            category="annotation",
            file_path="/tmp/annotation.IR64.gff",
            file_type=self.file_type,
            size=5678,
        )

        files = get_files_for_accession(self.accession.id, file_role="annotation")

        self.assertEqual(files, [])

    def test_returns_empty_when_only_organism_matches_legacy_file(self):
        GenomeFile.objects.create(
            name="organism.IR64.fasta",
            organism=self.accession.accession,
            category="genome",
            file_path="/tmp/organism.IR64.fasta",
            file_type=self.file_type,
            size=5678,
        )

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    def test_get_primary_file_prefers_primary_relation(self):
        self.add_relation("accession", self.accession.id, file_role="genome", is_primary=False)
        primary_file = DataFile.objects.create(
            file_code="FILE000003",
            file_name="genome.IR64.primary.fasta",
            file_path="/tmp/genome.IR64.primary.fasta",
        )
        FileRelation.objects.create(
            file=primary_file,
            related_type="accession",
            related_id=str(self.accession.id),
            file_role="genome",
            is_primary=True,
        )

        primary = get_primary_file("accession", self.accession.id, file_role="genome")

        self.assertEqual(primary["file_code"], "FILE000003")
        self.assertEqual(primary["source"], "new_relation")

    def test_get_primary_file_returns_none_when_no_file_exists(self):
        primary = get_primary_file("accession", self.accession.id, file_role="genome")

        self.assertIsNone(primary)

    def test_assembly_genome_selector_prefers_current_primary(self):
        self.add_assembly_genome_file("GENOME_UNMARKED")
        primary_file = self.add_assembly_genome_file("GENOME_PRIMARY", is_primary=True)

        selected = get_primary_genome_file_for_assembly(self.assembly.id)

        self.assertEqual(selected["file_id"], primary_file.id)
        self.assertEqual(selected["file_role"], "genome_fasta")

    def test_assembly_genome_selector_ignores_noncurrent_primary(self):
        self.add_assembly_genome_file("GENOME_OLD", is_current=False, is_primary=True)
        current_file = self.add_assembly_genome_file("GENOME_CURRENT")

        selected = get_primary_genome_file_for_assembly(self.assembly.id)

        self.assertEqual(selected["file_id"], current_file.id)

    def test_assembly_genome_selector_rejects_multiple_current_primaries(self):
        self.add_assembly_genome_file("GENOME_PRIMARY_A", is_primary=True)
        self.add_assembly_genome_file("GENOME_PRIMARY_B", is_primary=True)

        with self.assertRaisesRegex(GenomeFileSelectionError, "multiple current primary"):
            get_primary_genome_file_for_assembly(self.assembly.id)

    def test_assembly_genome_selector_rejects_multiple_unmarked_candidates(self):
        self.add_assembly_genome_file("GENOME_A")
        self.add_assembly_genome_file("GENOME_B")

        with self.assertRaisesRegex(GenomeFileSelectionError, "multiple current unmarked"):
            get_primary_genome_file_for_assembly(self.assembly.id)

    def test_assembly_genome_selector_accepts_named_legacy_genome_role_in_exact_scope(self):
        self.add_relation("assembly", self.assembly.id, file_role="genome", is_primary=True)
        other_assembly = Assembly.objects.create(accession=self.accession, name="other")
        other_file = DataFile.objects.create(
            file_code="GENOME_OTHER",
            file_name="other.fasta",
            file_path="/tmp/other.fasta",
        )
        FileRelation.objects.create(
            file=other_file,
            related_type="assembly",
            related_id=str(other_assembly.id),
            file_role="genome_fasta",
            is_primary=True,
        )

        selected = get_primary_genome_file_for_assembly(self.assembly.id)

        self.assertEqual(selected["file_id"], self.data_file.id)
        self.assertEqual(selected["file_name"], "genome.IR64.fasta")
        self.assertEqual(selected["file_role"], "genome")

    def test_assembly_genome_selector_rejects_non_fasta_legacy_genome_role(self):
        self.data_file.file_name = "genome.IR64.fasta.fai"
        self.data_file.save(update_fields=["file_name"])
        self.add_relation("assembly", self.assembly.id, file_role="genome", is_primary=True)

        selected = get_primary_genome_file_for_assembly(self.assembly.id)

        self.assertIsNone(selected)

    def test_assembly_genome_selector_prefers_canonical_role_over_legacy_primary(self):
        self.add_relation("assembly", self.assembly.id, file_role="genome", is_primary=True)
        canonical_file = self.add_assembly_genome_file("GENOME_CANONICAL")

        selected = get_primary_genome_file_for_assembly(self.assembly.id)

        self.assertEqual(selected["file_id"], canonical_file.id)
        self.assertEqual(selected["file_role"], "genome_fasta")
