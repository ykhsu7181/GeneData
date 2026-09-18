from rest_framework import serializers

from .models import Accession, Annotation, Assembly, FileCategory, FileType, GenomeFile, Organism
from .services.accession_context import classify_file_scope


class FileTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileType
        fields = '__all__'


class OrganismSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organism
        fields = '__all__'


class FileCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FileCategory
        fields = '__all__'


class GenomeFileSerializer(serializers.ModelSerializer):
    file_type_name = serializers.ReadOnlyField(source='file_type.name')

    class Meta:
        model = GenomeFile
        fields = '__all__'


class GenomeFileListSerializer(serializers.ModelSerializer):
    file_type_name = serializers.ReadOnlyField(source='file_type.name')

    class Meta:
        model = GenomeFile
        fields = ['id', 'name', 'organism', 'category', 'file_type_name', 'size', 'created_at']


class AccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = [
            'id',
            'accession',
            'genetic_stock_id',
            'sub_population',
            'seq_data',
            'country',
            'region',
            'longitude',
            'latitude',
            'description',
            'created_at',
            'updated_at',
        ]


class AccessionGenomeFileSerializer(serializers.ModelSerializer):
    file_type_name = serializers.ReadOnlyField(source='file_type.name')
    accession_id = serializers.IntegerField(source='accession.id', read_only=True)
    assembly_id = serializers.IntegerField(source='assembly.id', read_only=True)
    annotation_id = serializers.IntegerField(source='annotation.id', read_only=True)
    scope = serializers.SerializerMethodField()

    class Meta:
        model = GenomeFile
        fields = [
            'id',
            'name',
            'organism',
            'category',
            'file_type_name',
            'file_path',
            'size',
            'created_at',
            'accession_id',
            'assembly_id',
            'annotation_id',
            'scope',
        ]

    def get_scope(self, obj):
        return classify_file_scope(obj.category)


class AnnotationDetailSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    source_summary = serializers.SerializerMethodField()
    feature_types_summary = serializers.SerializerMethodField()
    chromosomes_summary = serializers.SerializerMethodField()
    coordinate_range_summary = serializers.SerializerMethodField()

    class Meta:
        model = Annotation
        fields = [
            'id',
            'name',
            'display_name',
            'standard_id',
            'source_name',
            'release_version',
            'description',
            'is_default',
            'created_at',
            'updated_at',
            'files',
            'source_summary',
            'feature_types_summary',
            'chromosomes_summary',
            'coordinate_range_summary',
        ]

    def get_files(self, obj):
        files = getattr(obj, 'prefetched_files', None)
        if files is None:
            files = obj.files.select_related('file_type').order_by('category', 'name')
        return AccessionGenomeFileSerializer(files, many=True).data

    def _get_summary(self, obj):
        return getattr(obj, 'summary_metadata', {}) or {}

    def get_source_summary(self, obj):
        return self._get_summary(obj).get('source_summary')

    def get_feature_types_summary(self, obj):
        return self._get_summary(obj).get('feature_types_summary')

    def get_chromosomes_summary(self, obj):
        return self._get_summary(obj).get('chromosomes_summary')

    def get_coordinate_range_summary(self, obj):
        return self._get_summary(obj).get('coordinate_range_summary')


class AssemblyDetailSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()

    class Meta:
        model = Assembly
        fields = [
            'id',
            'name',
            'display_name',
            'standard_id',
            'bio_project',
            'reference',
            'description',
            'is_default',
            'created_at',
            'updated_at',
            'files',
            'annotations',
        ]

    def get_files(self, obj):
        files = getattr(obj, 'prefetched_files', None)
        if files is None:
            files = obj.files.select_related('file_type').filter(annotation__isnull=True).order_by('category', 'name')
        return AccessionGenomeFileSerializer(files, many=True).data

    def get_annotations(self, obj):
        annotations = getattr(obj, 'prefetched_annotations', None)
        if annotations is None:
            annotations = obj.annotations.all().order_by('-is_default', 'name', 'id')
        return AnnotationDetailSerializer(annotations, many=True).data


class AssemblyListSerializer(serializers.ModelSerializer):
    accession = serializers.CharField(source='accession.accession', read_only=True)
    accession_id = serializers.IntegerField(source='accession.id', read_only=True)
    assembly = serializers.SerializerMethodField()
    species = serializers.SerializerMethodField()
    taxon_id = serializers.SerializerMethodField()

    class Meta:
        model = Assembly
        fields = [
            'id',
            'accession',
            'accession_id',
            'assembly',
            'assembly_accession',
            'assembly_level',
            'genome_size',
            'chromosome_count',
            'contig_count',
            'n50',
            'gc_content',
            'species',
            'taxon_id',
            'is_default',
        ]

    def get_assembly(self, obj):
        return obj.display_name or obj.assembly_name or obj.name

    def _species(self, obj):
        accession = getattr(obj, 'accession', None)
        return getattr(accession, 'species', None)

    def get_species(self, obj):
        species = self._species(obj)
        if species:
            return species.scientific_name or species.common_name or species.species_code
        return obj.species_code

    def get_taxon_id(self, obj):
        species = self._species(obj)
        return getattr(species, 'taxonomy_id', None)


class AccessionDetailSerializer(serializers.ModelSerializer):
    assemblies = serializers.SerializerMethodField()

    class Meta:
        model = Accession
        fields = [
            'id',
            'accession',
            'genetic_stock_id',
            'sub_population',
            'seq_data',
            'country',
            'region',
            'longitude',
            'latitude',
            'description',
            'created_at',
            'updated_at',
            'assemblies',
        ]

    def get_assemblies(self, obj):
        assemblies = getattr(obj, 'prefetched_assemblies', None)
        if assemblies is None:
            assemblies = obj.assemblies.all().order_by('-is_default', 'name', 'id')
        return AssemblyDetailSerializer(assemblies, many=True).data
