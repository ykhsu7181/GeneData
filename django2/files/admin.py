from django.contrib import admin
from .models import FileType, GenomeFile, Accession


@admin.register(FileType)
class FileTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'extension', 'description')
    search_fields = ('name', 'extension')


@admin.register(GenomeFile)
class GenomeFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'organism', 'category', 'file_type', 'size', 'created_at')
    list_filter = ('organism', 'category', 'file_type')
    search_fields = ('name', 'description')
    readonly_fields = ('size', 'created_at', 'updated_at')


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = (
        'accession',
        'sub_population',
        'seq_data',
        'longitude',
        'latitude',
        'updated_at',
    )
    search_fields = ('accession', 'sub_population', 'seq_data')
    list_filter = ('sub_population',)
    readonly_fields = ('created_at', 'updated_at')
