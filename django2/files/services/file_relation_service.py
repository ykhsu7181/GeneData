import logging

from files.models import FileRelation


logger = logging.getLogger(__name__)

PRIMARY_GENOME_FILE_ROLE = "genome_fasta"


class GenomeFileSelectionError(ValueError):
    """Raised when an Assembly has no deterministic current genome FASTA."""


def get_files_for_object(related_type, related_id, file_role=None):
    return _get_relation_files(related_type, related_id, file_role=file_role)


def get_files_for_accession(accession_id, file_role=None):
    return get_files_for_object("accession", accession_id, file_role=file_role)


def get_files_for_assembly(assembly_id, file_role=None):
    return get_files_for_object("assembly", assembly_id, file_role=file_role)


def get_files_for_annotation(annotation_id, file_role=None):
    return get_files_for_object("annotation", annotation_id, file_role=file_role)


def get_primary_file(related_type, related_id, file_role=None):
    relation_files = _get_relation_files(
        related_type,
        related_id,
        file_role=file_role,
        primary_first=True,
    )
    if relation_files:
        return relation_files[0]
    return None


def get_primary_genome_file_for_assembly(assembly_id):
    """Return the deterministic current genome FASTA for an Assembly.

    A marked primary wins. Without one, the sole current candidate is accepted.
    Multiple primaries or multiple unmarked candidates are data errors rather
    than an invitation to pick a file by insertion order.
    """
    relations = list(
        FileRelation.objects.select_related("file").filter(
            related_type="assembly",
            related_id=str(assembly_id),
            file_role=PRIMARY_GENOME_FILE_ROLE,
            file__is_current=True,
        ).order_by("id")
    )
    primary_relations = [relation for relation in relations if relation.is_primary]

    if len(primary_relations) > 1:
        message = (
            f"Assembly {assembly_id} has multiple current primary "
            f"{PRIMARY_GENOME_FILE_ROLE} files"
        )
        logger.error(message)
        raise GenomeFileSelectionError(message)
    if primary_relations:
        return _format_relation_file(primary_relations[0])
    if len(relations) == 1:
        return _format_relation_file(relations[0])
    if len(relations) > 1:
        message = (
            f"Assembly {assembly_id} has multiple current unmarked "
            f"{PRIMARY_GENOME_FILE_ROLE} files"
        )
        logger.error(message)
        raise GenomeFileSelectionError(message)
    return None


def _get_relation_files(related_type, related_id, file_role=None, primary_first=False):
    queryset = FileRelation.objects.select_related("file").filter(
        related_type=related_type,
        related_id=str(related_id),
    )
    if file_role:
        queryset = queryset.filter(file_role=file_role)

    if primary_first:
        queryset = queryset.order_by("-is_primary", "id")
    else:
        queryset = queryset.order_by("id")

    return [_format_relation_file(relation) for relation in queryset]


def _format_relation_file(relation):
    data_file = relation.file
    return {
        "file_id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "file_path": data_file.file_path,
        "file_size": data_file.file_size,
        "md5": data_file.md5,
        "file_role": relation.file_role,
        "related_type": relation.related_type,
        "related_id": relation.related_id,
        "source": "new_relation",
    }
