from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services.file_relation_service import (
    get_files_for_accession,
    get_files_for_annotation,
    get_files_for_assembly,
    get_primary_file,
)


class FileRelationServiceNewOnlyTestCase(TestCase):
    def setUp(self):
        self.file_type = FileType.objects.create(name="FASTA_NEW_ONLY", extension="fasta")
        self.accession = Accession.objects.create(accession="IR64_NEW_ONLY")
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
            file_code="NEWONLY0001",
            file_type=self.file_type,
            file_name="genome.IR64_NEW_ONLY.fasta",
            file_path="/tmp/new-only/genome.IR64_NEW_ONLY.fasta",
            file_size=1234,
        )

    def add_relation(self, related_type, related_id, file_role="genome", is_primary=False, data_file=None):
        return FileRelation.objects.create(
            file=data_file or self.data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=file_role,
            is_primary=is_primary,
        )

    def assert_new_only_sources(self, files):
        for item in files:
            self.assertEqual(item["source"], "new_relation")
            self.assertNotEqual(item.get("source"), "legacy_genomefile")
            self.assertNotEqual(item.get("fallback_source"), "organism_fallback")

    def test_accession_relation_returns_new_relation(self):
        self.add_relation("accession", self.accession.id)

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertEqual(files[0]["file_id"], self.data_file.id)
        self.assert_new_only_sources(files)

    def test_assembly_relation_returns_new_relation(self):
        self.add_relation("assembly", self.assembly.id)

        files = get_files_for_assembly(self.assembly.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertEqual(files[0]["related_type"], "assembly")
        self.assert_new_only_sources(files)

    def test_annotation_relation_returns_new_relation(self):
        self.add_relation("annotation", self.annotation.id, file_role="annotation")

        files = get_files_for_annotation(self.annotation.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")
        self.assertEqual(files[0]["related_type"], "annotation")
        self.assert_new_only_sources(files)

    def test_genomefile_does_not_fallback_without_relation(self):
        GenomeFile.objects.create(
            name="legacy.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path="/tmp/new-only/legacy.fasta",
            file_type=self.file_type,
            size=1234,
        )

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    def test_organism_match_does_not_fallback_without_relation(self):
        GenomeFile.objects.create(
            name="organism.fasta",
            organism=self.accession.accession,
            category="genome",
            file_path="/tmp/new-only/organism.fasta",
            file_type=self.file_type,
            size=1234,
        )

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    def test_get_primary_file_only_uses_filerelation(self):
        GenomeFile.objects.create(
            name="legacy-primary.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path="/tmp/new-only/legacy-primary.fasta",
            file_type=self.file_type,
            size=1234,
        )
        primary_data_file = DataFile.objects.create(
            file_code="NEWONLY0002",
            file_name="primary.fasta",
            file_path="/tmp/new-only/primary.fasta",
        )
        self.add_relation("accession", self.accession.id, is_primary=False)
        self.add_relation("accession", self.accession.id, is_primary=True, data_file=primary_data_file)

        primary = get_primary_file("accession", self.accession.id)

        self.assertEqual(primary["file_id"], primary_data_file.id)
        self.assertEqual(primary["source"], "new_relation")

    def test_get_primary_file_returns_none_without_relation(self):
        GenomeFile.objects.create(
            name="legacy-primary.fasta",
            organism=self.accession.accession,
            accession=self.accession,
            category="genome",
            file_path="/tmp/new-only/legacy-primary.fasta",
            file_type=self.file_type,
            size=1234,
        )

        primary = get_primary_file("accession", self.accession.id)

        self.assertIsNone(primary)
