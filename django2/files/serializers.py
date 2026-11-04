from rest_framework import serializers

from .models import Accession, Annotation, Assembly, FileCategory, FileRelation, FileType, Organism
from .services.accession_context import classify_file_scope
from .services.assembly_visibility import filter_visible_assemblies


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


def _file_relations_for(obj, related_type):
    prefetched_relations = getattr(obj, 'prefetched_file_relations', None)
    if prefetched_relations is not None:
        return prefetched_relations
    return FileRelation.objects.filter(
        related_type=related_type,
        related_id=str(obj.id),
    ).select_related('file__file_type').order_by('file_role', 'file__file_name', 'id')


def _serialize_file_relations(obj, related_type):
    accession = obj.accession if related_type == 'assembly' else obj.assembly.accession
    assembly_id = obj.id if related_type == 'assembly' else obj.assembly_id
    annotation_id = obj.id if related_type == 'annotation' else None
    payload = []
    for relation in _file_relations_for(obj, related_type):
        data_file = relation.file
        payload.append({
            'id': data_file.id,
            'name': data_file.file_name,
            'organism': accession.accession,
            'category': relation.file_role,
            'file_type_name': data_file.file_type.name if data_file.file_type else None,
            'file_path': data_file.file_path,
            'size': data_file.file_size,
            'created_at': data_file.created_at,
            'accession_id': accession.id,
            'assembly_id': assembly_id,
            'annotation_id': annotation_id,
            'scope': classify_file_scope(relation.file_role),
        })
    return payload


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
        return _serialize_file_relations(obj, 'annotation')

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
        return _serialize_file_relations(obj, 'assembly')

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
        assemblies = filter_visible_assemblies(assemblies)
        return AssemblyDetailSerializer(assemblies, many=True).data
