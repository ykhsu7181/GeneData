from django.contrib import admin
from .models import FileType, Accession


@admin.register(FileType)
class FileTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'extension', 'description')
    search_fields = ('name', 'extension')


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = (
        'accession',
        'sub_population',
        'seq_data',
        'longitude',
        'latitude',
        'view_count',
        'last_viewed_at',
        'updated_at',
    )
    search_fields = ('accession', 'sub_population', 'seq_data')
    list_filter = ('sub_population',)
    readonly_fields = ('view_count', 'last_viewed_at', 'created_at', 'updated_at')
