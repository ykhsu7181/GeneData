from django.contrib import admin
from .models import FileType, GenomeFile, Accession


@admin.register(FileType)
class FileTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'extension', 'description')
    search_fields = ('name', 'extension')


@admin.register(GenomeFile)
class GenomeFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'archive_status', 'organism', 'category', 'file_type', 'size', 'created_at')
    list_filter = ('organism', 'category', 'file_type')
    search_fields = ('name', 'description')
    readonly_fields = tuple(field.name for field in GenomeFile._meta.fields)

    def archive_status(self, obj):
        return 'archived'
    archive_status.short_description = 'Archive status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


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
