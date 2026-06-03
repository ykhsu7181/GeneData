from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    FileRelation,
    FileType,
    GenomeFile,
    Project,
    Sample,
    Species,
)


class ProjectRoutingSmokeTest(SimpleTestCase):
    def test_debug_endpoint_route_exists(self):
        self.assertEqual(reverse('debug'), '/gd/api/debug/')


class GenomeFileModelTestCase(TestCase):
    def test_coreblocks_category_in_choices(self):
        categories = [choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES]
        self.assertIn('coreBlocks', categories)

    def test_create_genome_file_str(self):
        file_type = FileType.objects.create(
            name='BED',
            extension='bed',
        )

        genome_file = GenomeFile.objects.create(
            name='coreBlocks.IR64.bed',
            organism='IR64',
            category='coreBlocks',
            file_path='/tmp/coreBlocks.IR64.bed',
            file_type=file_type,
            size=1000,
        )

        self.assertEqual(str(genome_file), 'IR64-coreBlocks-coreBlocks.IR64.bed')


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

        GenomeFile.objects.create(
            name='genome.IR64.fasta',
            organism='IR64',
            accession=self.accession,
            assembly=self.default_assembly,
            category='genome',
            file_path='/tmp/genome.IR64.fasta',
            file_type=self.file_type,
            size=1234,
        )
        GenomeFile.objects.create(
            name='annotation.IR64.gff',
            organism='IR64',
            accession=self.accession,
            assembly=self.default_assembly,
            annotation=self.default_annotation,
            category='annotation',
            file_path='/tmp/annotation.IR64.gff',
            file_type=self.gff_type,
            size=5678,
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

    def test_accession_detail_fallback_to_legacy_organism_files(self):
        legacy_accession = Accession.objects.create(accession='LEGACY')
        legacy_assembly = Assembly.objects.create(
            accession=legacy_accession,
            name='default',
            is_default=True,
        )
        Annotation.objects.create(
            assembly=legacy_assembly,
            name='default-annotation',
            is_default=True,
        )

        GenomeFile.objects.create(
            name='genome.LEGACY.fasta',
            organism='LEGACY',
            category='genome',
            file_path='/tmp/genome.LEGACY.fasta',
            file_type=self.file_type,
            size=100,
        )

        response = self.client.get('/gd/api/files/accessions/LEGACY/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['file_count'], 1)
        self.assertTrue(response.data['data']['file_status']['genome'])
        self.assertEqual(len(response.data['data']['assemblies']), 1)

    def test_accession_detail_not_found(self):
        response = self.client.get('/gd/api/files/accessions/NOT_EXISTS/')

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])


class PaginatedOverviewApiTestCase(APITestCase):
    def setUp(self):
        self.accession = Accession.objects.create(
            accession='IR64',
            sub_population='XI',
            seq_data='https://example.com/IR64',
            longitude=114.3,
            latitude=30.5,
        )
        self.default_assembly = Assembly.objects.create(
            accession=self.accession,
            name='default',
            is_default=True,
        )
        self.alt_assembly = Assembly.objects.create(
            accession=self.accession,
            name='alt-v2',
            is_default=False,
        )
        self.default_annotation = Annotation.objects.create(
            assembly=self.default_assembly,
            name='default-annotation',
            is_default=True,
        )
        Annotation.objects.create(
            assembly=self.alt_assembly,
            name='alt-annotation',
            is_default=True,
        )

        self.file_type = FileType.objects.create(name='FASTA', extension='fasta')
        self.gff_type = FileType.objects.create(name='GFF', extension='gff')
        self.tar_type = FileType.objects.create(name='TAR.GZ', extension='tar.gz')

        GenomeFile.objects.create(
            name='genome.IR64.fasta',
            organism='IR64',
            accession=self.accession,
            assembly=self.default_assembly,
            category='genome',
            file_path='/tmp/genome.IR64.fasta',
            file_type=self.file_type,
            size=1234,
        )
        GenomeFile.objects.create(
            name='annotation.IR64.gff',
            organism='IR64',
            accession=self.accession,
            assembly=self.default_assembly,
            annotation=self.default_annotation,
            category='annotation',
            file_path='/tmp/annotation.IR64.gff',
            file_type=self.gff_type,
            size=5678,
        )
        GenomeFile.objects.create(
            name='transcriptome.root.IR64.tar.gz',
            organism='IR64',
            accession=self.accession,
            assembly=self.default_assembly,
            category='transcriptome.root',
            file_path='/tmp/transcriptome.root.IR64.tar.gz',
            file_type=self.tar_type,
            size=7890,
        )

    def test_paginated_overview_includes_default_context_counts(self):
        response = self.client.get('/gd/api/files/genome-files/paginated_overview/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        row = response.data['results'][0]
        self.assertEqual(row['accession'], 'IR64')
        self.assertEqual(row['assembly_count'], 2)
        self.assertEqual(row['annotation_count'], 2)
        self.assertEqual(row['default_assembly_id'], self.default_assembly.id)
        self.assertEqual(row['default_annotation_id'], self.default_annotation.id)
        self.assertIsNotNone(row['genome'])
        self.assertEqual(row['genome']['name'], 'genome.IR64.fasta')
        self.assertIsNotNone(row['annotation'])
        self.assertEqual(row['annotation']['name'], 'annotation.IR64.gff')
        self.assertTrue(row['hasTranscriptome'])
