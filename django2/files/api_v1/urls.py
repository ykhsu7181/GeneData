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
from files.api_v1.batch_views import (
    create_file_batch,
    file_batch_detail,
    file_batch_manifest,
    file_batch_manifest_tsv,
    resolve_file_batch,
)
from files.api_v1.archive_views import (
    create_file_archive,
    file_archive_content,
    file_archive_status,
)


app_name = "files-api-v1"

urlpatterns = [
    path("openapi.json", openapi_schema, name="openapi-schema"),
    path("file-batches/resolve/", resolve_file_batch, name="file-batch-resolve"),
    path("file-batches/", create_file_batch, name="file-batch-create"),
    path("file-batches/<str:batch_id>/", file_batch_detail, name="file-batch-detail"),
    path("file-batches/<str:batch_id>/manifest/", file_batch_manifest, name="file-batch-manifest"),
    path("file-batches/<str:batch_id>/manifest.tsv", file_batch_manifest_tsv, name="file-batch-manifest-tsv"),
    path("file-batches/<str:batch_id>/archives/", create_file_archive, name="file-archive-create"),
    path("file-archives/<str:archive_id>/", file_archive_status, name="file-archive-status"),
    path("file-archives/<str:archive_id>/content/", file_archive_content, name="file-archive-content"),
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
