from files.models import DataFile, FileRelation, GenomeFile


LEGACY_FIELD_BY_RELATED_TYPE = {
    "accession": "accession_id",
    "assembly": "assembly_id",
    "annotation": "annotation_id",
}


def get_files_for_object(related_type, related_id, file_role=None):
    relation_files = _get_relation_files(related_type, related_id, file_role=file_role)
    if relation_files:
        return relation_files
    return _get_legacy_genome_files(related_type, related_id, file_role=file_role)


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

    legacy_files = _get_legacy_genome_files(related_type, related_id, file_role=file_role)
    if legacy_files:
        return legacy_files[0]
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


def _get_legacy_genome_files(related_type, related_id, file_role=None):
    field_name = LEGACY_FIELD_BY_RELATED_TYPE.get(related_type)
    if not field_name:
        return []

    filters = {field_name: related_id}
    if file_role:
        filters["category"] = file_role

    queryset = (
        GenomeFile.objects.select_related("file_type", "accession", "assembly", "annotation")
        .filter(**filters)
        .order_by("id")
    )
    return [
        _format_legacy_file(
            genome_file,
            related_type=related_type,
            related_id=related_id,
        )
        for genome_file in queryset
    ]


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


def _format_legacy_file(genome_file, related_type, related_id):
    return {
        "file_id": genome_file.id,
        "file_code": None,
        "file_name": genome_file.name,
        "file_path": genome_file.file_path,
        "file_size": genome_file.size,
        "md5": None,
        "file_role": genome_file.category,
        "related_type": related_type,
        "related_id": str(related_id),
        "source": "legacy_genomefile",
    }
