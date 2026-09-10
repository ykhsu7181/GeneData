import os
import re

from django.db import IntegrityError, transaction

from files.models import DataFile, FileRelation
from files.services.ingestion.roles import validate_file_role


FILE_CODE_PATTERN = re.compile(r"^FILE(\d+)$")
FILE_CODE_CREATE_ATTEMPTS = 5


def normalize_file_path(file_path):
    return os.path.abspath(os.path.normpath(file_path))


def create_or_get_datafile_from_path(
    *,
    file_path,
    file_name=None,
    file_type=None,
    file_size=None,
    md5=None,
    description=None,
    normalize_path=True,
    dry_run=False,
):
    normalized_path = normalize_file_path(file_path) if normalize_path else file_path
    data_file = DataFile.objects.filter(file_path=normalized_path).first()
    if data_file:
        return _reuse_datafile(
            data_file,
            file_size=file_size,
            md5=md5,
            normalized_path=normalized_path,
            dry_run=dry_run,
        )

    resolved_size = file_size if file_size is not None else safe_get_file_size(normalized_path)
    create_values = {
        "file_type": file_type,
        "file_name": file_name or os.path.basename(normalized_path),
        "original_name": file_name or os.path.basename(normalized_path),
        "file_path": normalized_path,
        "file_size": resolved_size,
        "md5": md5,
        "description": description,
    }
    if dry_run:
        return DataFile(file_code=make_next_file_code(), **create_values), True, False, False

    for _ in range(FILE_CODE_CREATE_ATTEMPTS):
        try:
            with transaction.atomic():
                data_file = DataFile.objects.filter(file_path=normalized_path).first()
                if data_file:
                    return _reuse_datafile(
                        data_file,
                        file_size=file_size,
                        md5=md5,
                        normalized_path=normalized_path,
                        dry_run=False,
                    )
                data_file = DataFile.objects.create(
                    file_code=make_next_file_code(),
                    **create_values,
                )
            return data_file, True, False, False
        except IntegrityError:
            data_file = DataFile.objects.filter(file_path=normalized_path).first()
            if data_file:
                return _reuse_datafile(
                    data_file,
                    file_size=file_size,
                    md5=md5,
                    normalized_path=normalized_path,
                    dry_run=False,
                )
    raise IntegrityError(
        f"Unable to allocate a unique DataFile.file_code after {FILE_CODE_CREATE_ATTEMPTS} attempts"
    )


def _reuse_datafile(data_file, *, file_size, md5, normalized_path, dry_run):
    updated = False
    update_fields = []
    resolved_size = file_size if file_size is not None else safe_get_file_size(normalized_path)

    if resolved_size is not None and data_file.file_size is None:
        data_file.file_size = resolved_size
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


def create_or_get_file_relation(
    *,
    data_file,
    related_type,
    related_id,
    file_role,
    related_code="",
    dry_run=False,
):
    validate_file_role(file_role)
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
