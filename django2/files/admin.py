from django.contrib import admin
from .models import FileType, GenomeFile

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
