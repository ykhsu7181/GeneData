from files.models import FileRelation


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
