import logging
import os

from django.db import transaction

from files.models import DataFile, FileRelation
from files.services.fasta_index_core import build_fasta_index


logger = logging.getLogger(__name__)

INDEX_ROLES = ("genome_index", "fai", "other")


class FastaIndexUnavailable(RuntimeError):
    pass


def find_current_fasta_index(*, genome_file, related_type, related_id):
    """Return a fresh, explicitly related .fai path for the selected genome."""
    if not genome_file or not related_type or related_id is None:
        return None
    if not genome_file.file_path or not os.path.isfile(genome_file.file_path):
        return None

    file_name = getattr(genome_file, "file_name", None) or getattr(genome_file, "name", None)
    expected_names = {
        f"{file_name}.fai" if file_name else "",
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


@transaction.atomic
def build_and_link_fasta_index(*, genome_file, related_type, related_id, related_code=None):
    index_path, entries = build_fasta_index(genome_file.file_path)
    stat = os.stat(index_path)
    index_file, _ = DataFile.objects.update_or_create(
        file_path=index_path,
        defaults={
            'file_code': f'FAI_{genome_file.id}',
            'file_name': f'{genome_file.file_name}.fai',
            'original_name': f'{genome_file.file_name}.fai',
            'file_size': stat.st_size,
            'is_current': True,
            'description': f'FASTA index for DataFile {genome_file.id}',
        },
    )
    FileRelation.objects.update_or_create(
        file=index_file,
        related_type=related_type,
        related_id=str(related_id),
        file_role='genome_index',
        defaults={
            'related_code': related_code,
            'is_primary': False,
            'description': f'Index for genome DataFile {genome_file.id}',
        },
    )
    return index_file, len(entries)
