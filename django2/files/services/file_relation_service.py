import logging

from files.models import FileRelation


logger = logging.getLogger(__name__)

PRIMARY_GENOME_FILE_ROLE = "genome_fasta"
COMPATIBLE_GENOME_FILE_ROLE = "genome"


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

    Canonical ``genome_fasta`` relations take precedence. Existing data that
    uses the ``genome`` role remains eligible only when the file follows the
    ``genome.<accession>.fasta`` naming contract. A marked primary wins;
    otherwise the sole current candidate is accepted. Ambiguity is an error.
    """
    relations = list(
        FileRelation.objects.select_related("file").filter(
            related_type="assembly",
            related_id=str(assembly_id),
            file_role__in=(PRIMARY_GENOME_FILE_ROLE, COMPATIBLE_GENOME_FILE_ROLE),
            file__is_current=True,
        ).order_by("id")
    )
    canonical_relations = [
        relation for relation in relations
        if relation.file_role == PRIMARY_GENOME_FILE_ROLE
    ]
    if canonical_relations:
        relations = canonical_relations
    else:
        relations = [
            relation for relation in relations
            if _is_compatible_genome_fasta(relation.file.file_name)
        ]
    primary_relations = [relation for relation in relations if relation.is_primary]
    selected_role = relations[0].file_role if relations else PRIMARY_GENOME_FILE_ROLE

    if len(primary_relations) > 1:
        message = (
            f"Assembly {assembly_id} has multiple current primary "
            f"genome FASTA files (role={selected_role})"
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
            f"genome FASTA files (role={selected_role})"
        )
        logger.error(message)
        raise GenomeFileSelectionError(message)
    return None


def _is_compatible_genome_fasta(file_name):
    normalized = str(file_name or "").lower()
    return normalized.startswith("genome.") and normalized.endswith(".fasta")


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
