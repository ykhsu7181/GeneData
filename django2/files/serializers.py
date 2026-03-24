from rest_framework import serializers
from .models import FileType, GenomeFile, Organism, FileCategory

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