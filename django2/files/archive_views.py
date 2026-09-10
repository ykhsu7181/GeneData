import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from files.models import GenomeFile


logger = logging.getLogger(__name__)

GENOMEFILE_ARCHIVE_MESSAGE = "GenomeFile API is archived, use DataFile API instead."
GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE = "GenomeFile download is archived, use DataFile download."


class ArchivedGenomeFileViewSet(viewsets.ViewSet):
    """Stable 410 adapter for retired GenomeFile URLs."""

    queryset = GenomeFile._meta.default_manager.none()

    def _gone(self, request, message=GENOMEFILE_ARCHIVE_MESSAGE):
        logger.warning(
            "Archived GenomeFile API called: method=%s path=%s",
            request.method,
            request.path,
        )
        return Response(
            {"success": False, "archived": True, "message": message},
            status=status.HTTP_410_GONE,
        )

    def list(self, request, *args, **kwargs):
        return self._gone(request)

    def retrieve(self, request, *args, **kwargs):
        return self._gone(request)

    def create(self, request, *args, **kwargs):
        return self._gone(request)

    def update(self, request, *args, **kwargs):
        return self._gone(request)

    def partial_update(self, request, *args, **kwargs):
        return self._gone(request)

    def destroy(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=True, methods=["get"])
    def download(self, request, *args, **kwargs):
        return self._gone(request, GENOMEFILE_DOWNLOAD_ARCHIVE_MESSAGE)

    @action(detail=False, methods=["get"], url_path="get_chromosomes")
    def get_chromosomes(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=False, methods=["get"], url_path="get_chromosome_length")
    def get_chromosome_length(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=False, methods=["get"])
    def organisms(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=False, methods=["get"])
    def organisms_with_annotation(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=False, methods=["get"])
    def categories(self, request, *args, **kwargs):
        return self._gone(request)

    @action(detail=False, methods=["get"])
    def scan_directory(self, request, *args, **kwargs):
        return self._gone(request)


def _add_archived_action(name):
    def archived_action(self, request, *args, **kwargs):
        return self._gone(request)

    archived_action.__name__ = name
    return action(detail=False, methods=["get"])(archived_action)


for _action_name in (
    "download_transcriptome",
    "transcriptome_types",
    "get_tes",
    "get_centromere",
    "get_coreblocks",
    "get_variableblocks",
    "get_rna_data",
    "paginated_transcriptome_overview",
    "get_codon_data",
    "get_annotation_data",
    "supplementary_data",
    "paginated_overview",
    "all_files",
    "sub_populations",
):
    setattr(ArchivedGenomeFileViewSet, _action_name, _add_archived_action(_action_name))
