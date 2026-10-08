import logging
import os
import tempfile

from django.db import transaction

from files.models import DataFile, FileRelation


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


def build_fasta_index(file_path, index_path=None):
    """Create a standard uncompressed FASTA .fai using an atomic replace."""
    if file_path.lower().endswith('.gz'):
        raise ValueError('Compressed FASTA requires bgzip/samtools and is not supported here')
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)
    index_path = index_path or f'{file_path}.fai'
    directory = os.path.dirname(os.path.abspath(index_path))
    os.makedirs(directory, exist_ok=True)
    entries = []
    with open(file_path, 'rb') as handle:
        name = None
        length = 0
        sequence_offset = None
        line_bases = None
        line_width = None
        saw_short_line = False
        while True:
            offset = handle.tell()
            raw_line = handle.readline()
            if not raw_line:
                if name is not None:
                    entries.append((name, length, sequence_offset, line_bases or 0, line_width or 0))
                break
            if raw_line.startswith(b'>'):
                if name is not None:
                    entries.append((name, length, sequence_offset, line_bases or 0, line_width or 0))
                header = raw_line.decode('utf-8').rstrip('\r\n')
                name = header[1:].strip().split()[0] if header[1:].strip() else None
                if not name:
                    raise ValueError(f'Invalid FASTA header at byte {offset}')
                length = 0
                sequence_offset = handle.tell()
                line_bases = None
                line_width = None
                saw_short_line = False
                continue
            if name is None:
                if raw_line.strip():
                    raise ValueError('FASTA sequence encountered before the first header')
                continue
            bases = len(raw_line.rstrip(b'\r\n'))
            if bases == 0:
                continue
            if saw_short_line:
                raise ValueError(f'Non-terminal short FASTA line for sequence {name}')
            if line_bases is None:
                line_bases = bases
                line_width = len(raw_line)
            elif bases > line_bases or len(raw_line) > line_width:
                raise ValueError(f'Inconsistent FASTA line width for sequence {name}')
            elif bases < line_bases or len(raw_line) < line_width:
                saw_short_line = True
            length += bases

    fd, temporary_path = tempfile.mkstemp(prefix='.fai-', dir=directory, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            for entry in entries:
                handle.write('\t'.join(str(value) for value in entry) + '\n')
        os.replace(temporary_path, index_path)
    except Exception:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise
    return index_path, entries


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
