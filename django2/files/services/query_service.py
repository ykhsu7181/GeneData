"""Central query service facade for page-level API payloads.

Views should stay thin: parse request params, call one service function, and
return the payload. The concrete builders remain split by page to keep each
query path small and testable.
"""

from files.services.data_overview_service import (
    build_data_overview_files_payload,
    build_data_overview_payload,
)
from files.services.genome_list_service import (
    build_genome_files_payload,
    build_genome_list_payload,
)
from files.services.raw_data_service import build_raw_data_payload
from files.services.transcriptome_list_service import (
    build_transcriptome_files_payload,
    build_transcriptome_list_payload,
)


def get_data_overview_payload(params):
    return build_data_overview_payload(params)


def get_data_overview_files_payload(params):
    return build_data_overview_files_payload(params)


def get_raw_data_payload(params):
    return build_raw_data_payload(params)


def get_genome_list_payload(params):
    return build_genome_list_payload(params)


def get_genome_files_payload(params):
    return build_genome_files_payload(params)


def get_transcriptome_list_payload(params):
    return build_transcriptome_list_payload(params)


def get_transcriptome_files_payload(params):
    return build_transcriptome_files_payload(params)
