from django.urls import path

from files.api_v1.accession_views import (
    accession_assemblies,
    accession_files,
    accession_metadata,
)
from files.api_v1.dataset_views import dataset_manifest, dataset_manifest_tsv
from files.api_v1.file_views import file_content, file_metadata


app_name = "files-api-v1"

urlpatterns = [
    path(
        "datasets/<str:dataset>/manifest/",
        dataset_manifest,
        name="dataset-manifest",
    ),
    path(
        "datasets/<str:dataset>/manifest.tsv",
        dataset_manifest_tsv,
        name="dataset-manifest-tsv",
    ),
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
