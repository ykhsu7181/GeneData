from django.urls import path

from files.api_v1.accession_views import accession_files
from files.api_v1.file_views import file_content, file_metadata


app_name = "files-api-v1"

urlpatterns = [
    path("accessions/<str:accession>/files/", accession_files, name="accession-files"),
    path("files/<int:file_id>/", file_metadata, name="file-metadata"),
    path("files/<int:file_id>/content/", file_content, name="file-content"),
]
