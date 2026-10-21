from django.urls import path

from files.api_v1.accession_views import (
    accession_assemblies,
    accession_files,
    accession_metadata,
)
from files.api_v1.file_views import file_content, file_metadata


app_name = "files-api-v1"

urlpatterns = [
    path(
        "accessions/<str:accession>/assemblies/",
        accession_assemblies,
        name="accession-assemblies",
    ),
    path("accessions/<str:accession>/files/", accession_files, name="accession-files"),
    path("accessions/<str:accession>/", accession_metadata, name="accession-metadata"),
    path("files/<int:file_id>/", file_metadata, name="file-metadata"),
    path("files/<int:file_id>/content/", file_content, name="file-content"),
]
