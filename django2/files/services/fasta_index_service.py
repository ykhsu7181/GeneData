import logging
import os

from files.models import FileRelation


logger = logging.getLogger(__name__)

INDEX_ROLES = ("genome_index", "fai", "other")


def find_current_fasta_index(*, genome_file, related_type, related_id):
    """Return a fresh, explicitly related .fai path for the selected genome."""
    if not genome_file or not related_type or related_id is None:
        return None
    if not genome_file.file_path or not os.path.isfile(genome_file.file_path):
        return None

    expected_names = {
        f"{genome_file.name}.fai" if genome_file.name else "",
        f"{os.path.basename(genome_file.file_path)}.fai" if genome_file.file_path else "",
    }
    relations = (
        FileRelation.objects.select_related("file")
        .filter(
            related_type=related_type,
            related_id=str(related_id),
            file__is_current=True,
            file_role__in=INDEX_ROLES,
        )
        .exclude(file_id=genome_file.id)
        .order_by("id")
    )
    for relation in relations:
        index_file = relation.file
        if not index_file.file_path.lower().endswith(".fai"):
            continue
        if expected_names and index_file.file_name not in expected_names:
            continue
        if not os.path.isfile(index_file.file_path):
            logger.warning("Related FASTA index is missing: %s", index_file.file_path)
            continue
        if os.path.getmtime(index_file.file_path) < os.path.getmtime(genome_file.file_path):
            logger.warning("Related FASTA index is stale: %s", index_file.file_path)
            continue
        return index_file.file_path
    return None
