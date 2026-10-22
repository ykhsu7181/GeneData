from django.urls import path

from files.api_v1.accession_views import (
    accession_assemblies,
    accession_files,
    accession_metadata,
)
from files.api_v1.dataset_views import dataset_manifest, dataset_manifest_tsv
from files.api_v1.file_views import file_catalog, file_content, file_metadata
from files.api_v1.sequence_views import assembly_sequence
from files.api_v1.schema_views import openapi_schema


app_name = "files-api-v1"

urlpatterns = [
    path("openapi.json", openapi_schema, name="openapi-schema"),
    path(
        "assemblies/<str:assembly>/sequence/",
        assembly_sequence,
        name="assembly-sequence",
    ),
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
    path("files/", file_catalog, name="file-catalog"),
    path("files/<str:file_identifier>/", file_metadata, name="file-metadata"),
    path(
        "files/<str:file_identifier>/content/",
        file_content,
        name="file-content",
    ),
]
