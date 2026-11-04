from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from filemanager.urls import debug_urlpatterns
from rest_framework.test import APITestCase

from files.file_categories import FILE_CATEGORY_CHOICES
from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    Project,
    Sample,
    Species,
)


class ProjectRoutingSmokeTest(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_debug_endpoint_route_exists_in_debug_mode(self):
        patterns = debug_urlpatterns()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(str(patterns[0].pattern), 'gd/api/debug/')


class FileCategoryCompatibilityTestCase(TestCase):
    def test_coreblocks_category_in_choices(self):
        categories = [choice[0] for choice in FILE_CATEGORY_CHOICES]
        self.assertIn('coreBlocks', categories)

class AccessionHierarchyModelTestCase(TestCase):
    def setUp(self):
        self.accession = Accession.objects.create(accession='IR64')
        self.default_assembly = Assembly.objects.create(
            accession=self.accession,
            name='default',
            is_default=True,
        )
        self.default_annotation = Annotation.objects.create(
            assembly=self.default_assembly,
            name='default-annotation',
            is_default=True,
        )

    def test_accession_default_assembly_property(self):
        self.assertEqual(self.accession.default_assembly, self.default_assembly)

    def test_assembly_default_annotation_property(self):
        self.assertEqual(self.default_assembly.default_annotation, self.default_annotation)


class DataWarehousePhaseOneModelTestCase(TestCase):
    def test_accession_species_is_optional_and_can_be_linked(self):
        accession = Accession.objects.create(accession='IR64')
        species = Species.objects.create(
            species_code='oryza_sativa',
            scientific_name='Oryza sativa',
            common_name='rice',
        )

        self.assertIsNone(accession.species)

        accession.species = species
        accession.save(update_fields=['species'])

        self.assertEqual(Accession.objects.get(accession='IR64').species, species)

    def test_data_file_uses_file_path_as_phase_one_dedup_key(self):
        file_type = FileType.objects.create(
            name='GFF3',
            extension='gff3',
            code='gff3',
            category='annotation',
            format='gff3',
        )
        data_file = DataFile.objects.create(
            file_code='FILE-001',
            file_type=file_type,
            file_name='annotation.IR64.gff3',
            original_name='annotation.IR64.gff3',
            file_path='/tmp/annotation.IR64.gff3',
            file_size=123,
        )

        self.assertTrue(data_file.is_current)

        with self.assertRaises(IntegrityError):
            DataFile.objects.create(
                file_code='FILE-002',
                file_name='duplicate.gff3',
                file_path='/tmp/annotation.IR64.gff3',
            )

    def test_file_relation_allows_one_file_to_link_multiple_objects(self):
        accession = Accession.objects.create(accession='IR64')
        assembly = Assembly.objects.create(
            accession=accession,
            name='default',
            is_default=True,
        )
        data_file = DataFile.objects.create(
            file_code='FILE-003',
            file_name='genome.IR64.fasta',
            file_path='/tmp/genome.IR64.fasta',
        )

        FileRelation.objects.create(
            file=data_file,
            related_type='accession',
            related_id=str(accession.id),
            related_code=accession.accession,
            file_role='genome_fasta',
        )
        FileRelation.objects.create(
            file=data_file,
            related_type='assembly',
            related_id=str(assembly.id),
            related_code=assembly.name,
            file_role='genome_fasta',
            is_primary=True,
        )

        self.assertEqual(data_file.relations.count(), 2)

        with self.assertRaises(IntegrityError):
            FileRelation.objects.create(
                file=data_file,
                related_type='assembly',
                related_id=str(assembly.id),
                related_code=assembly.name,
                file_role='genome_fasta',
            )

    def test_project_dataset_and_sample_are_optional_scaffolding(self):
        species = Species.objects.create(species_code='oryza_sativa')
        project = Project.objects.create(project_code='PRJ-001', project_name='Rice project')
        dataset = Dataset.objects.create(
            dataset_code='DS-001',
            dataset_name='IR64 genome dataset',
            dataset_type='genome',
            species=species,
            project=project,
            visibility='lab_internal',
            status='draft',
        )
        sample = Sample.objects.create(
            sample_code='SMP-001',
            sample_name='IR64 leaf sample',
            species=species,
            tissue='leaf',
            data_type='transcriptome',
        )

        self.assertEqual(dataset.project, project)
        self.assertEqual(sample.species, species)


class AccessionDetailApiTestCase(APITestCase):
    def setUp(self):
        self.accession = Accession.objects.create(
            accession='IR64',
            sub_population='indica',
            seq_data='https://example.com/IR64',
            longitude=114.3,
            latitude=30.5,
        )

        self.default_assembly = Assembly.objects.create(
            accession=self.accession,
            name='default',
            is_default=True,
        )
        self.default_annotation = Annotation.objects.create(
            assembly=self.default_assembly,
            name='default-annotation',
            is_default=True,
        )

        self.file_type = FileType.objects.create(
            name='FASTA',
            extension='fasta',
        )
        self.gff_type = FileType.objects.create(
            name='GFF',
            extension='gff',
        )

        genome_data_file = DataFile.objects.create(
            file_code='FILE-ACCESSION-DETAIL-GENOME',
            file_type=self.file_type,
            file_name='genome.IR64.fasta',
            original_name='genome.IR64.fasta',
            file_path='/tmp/genome.IR64.fasta',
            file_size=1234,
        )
        annotation_data_file = DataFile.objects.create(
            file_code='FILE-ACCESSION-DETAIL-ANNOTATION',
            file_type=self.gff_type,
            file_name='annotation.IR64.gff',
            original_name='annotation.IR64.gff',
            file_path='/tmp/annotation.IR64.gff',
            file_size=5678,
        )
        FileRelation.objects.create(
            file=genome_data_file,
            related_type='assembly',
            related_id=str(self.default_assembly.id),
            related_code=self.default_assembly.name,
            file_role='genome',
            is_primary=True,
        )
        FileRelation.objects.create(
            file=annotation_data_file,
            related_type='annotation',
            related_id=str(self.default_annotation.id),
            related_code=self.default_annotation.name,
            file_role='annotation',
            is_primary=True,
        )

    def test_accession_detail_success(self):
        response = self.client.get('/gd/api/files/accessions/IR64/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['accession']['accession'], 'IR64')
        self.assertEqual(response.data['data']['summary']['assembly_count'], 1)
        self.assertEqual(response.data['data']['summary']['annotation_count'], 1)
        self.assertEqual(response.data['data']['file_count'], 2)
        self.assertEqual(len(response.data['data']['assemblies']), 1)
        self.assertEqual(response.data['data']['assemblies'][0]['name'], 'default')
        self.assertEqual(len(response.data['data']['assemblies'][0]['annotations']), 1)
        self.assertEqual(response.data['data']['assemblies'][0]['annotations'][0]['name'], 'default-annotation')
        self.assertTrue(response.data['data']['file_status']['genome'])
        self.assertTrue(response.data['data']['file_status']['annotation'])

    def test_accession_detail_not_found(self):
        response = self.client.get('/gd/api/files/accessions/NOT_EXISTS/')

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])


class PaginatedOverviewApiTestCase(APITestCase):
    def test_legacy_paginated_overview_is_archived(self):
        response = self.client.get('/gd/api/files/genome-files/paginated_overview/')

        self.assertEqual(response.status_code, 410)
        self.assertTrue(response.data['archived'])
