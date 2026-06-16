import os
import re

from django.db import transaction

from files.models import DataFile, FileRelation


FILE_CODE_PATTERN = re.compile(r"^FILE(\d+)$")


def normalize_file_path(file_path):
    return os.path.abspath(os.path.normpath(file_path))


def create_or_get_datafile_from_path(
    *,
    file_path,
    file_name=None,
    file_type=None,
    md5=None,
    dry_run=False,
):
    normalized_path = normalize_file_path(file_path)
    data_file = DataFile.objects.filter(file_path=normalized_path).first()
    if data_file:
        updated = False
        update_fields = []
        file_size = safe_get_file_size(normalized_path)

        if file_size is not None and data_file.file_size is None:
            data_file.file_size = file_size
            update_fields.append("file_size")
        if md5 and not data_file.md5:
            data_file.md5 = md5
            update_fields.append("md5")

        if update_fields:
            updated = True
            if not dry_run:
                update_fields.append("updated_at")
                data_file.save(update_fields=update_fields)
        return data_file, False, True, updated

    file_size = safe_get_file_size(normalized_path)
    data_file = DataFile(
        file_code=make_next_file_code(),
        file_type=file_type,
        file_name=file_name or os.path.basename(normalized_path),
        original_name=file_name or os.path.basename(normalized_path),
        file_path=normalized_path,
        file_size=file_size,
        md5=md5,
    )
    if not dry_run:
        data_file.save()
    return data_file, True, False, False


def create_or_get_file_relation(
    *,
    data_file,
    related_type,
    related_id,
    file_role,
    related_code="",
    dry_run=False,
):
    related_id = str(related_id)
    if data_file.pk:
        existing = FileRelation.objects.filter(
            file=data_file,
            related_type=related_type,
            related_id=related_id,
            file_role=file_role,
        ).first()
        if existing:
            return existing, False, True

    relation = FileRelation(
        file=data_file,
        related_type=related_type,
        related_id=related_id,
        related_code=related_code,
        file_role=file_role,
        is_primary=False,
    )
    if not dry_run:
        with transaction.atomic():
            relation, created = FileRelation.objects.get_or_create(
                file=data_file,
                related_type=related_type,
                related_id=related_id,
                file_role=file_role,
                defaults={
                    "related_code": related_code,
                    "is_primary": False,
                },
            )
        return relation, created, not created
    return relation, True, False


def make_next_file_code():
    max_number = 0
    for file_code in DataFile.objects.values_list("file_code", flat=True):
        match = FILE_CODE_PATTERN.match(file_code or "")
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"FILE{max_number + 1:06d}"


def safe_get_file_size(file_path):
    try:
        return os.path.getsize(file_path)
    except OSError:
        return None
