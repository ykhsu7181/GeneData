import os

from files.services.ingestion.roles import CANONICAL_FILE_ROLES, validate_file_role


COMPRESSION_EXTENSIONS = {"bz2", "gz", "xz", "zip"}


def parse_ingestion_filename(filename):
    """Parse ``<canonical role>.<accession>.<extension>`` legacy filenames.

    Roles are matched as complete prefixes, so dotted transcriptome roles and
    accessions containing dots are preserved. The final suffix is treated as
    the file extension; a compression suffix removes one additional suffix.
    """
    basename = os.path.basename(filename)
    role = next(
        (
            candidate
            for candidate in sorted(CANONICAL_FILE_ROLES, key=len, reverse=True)
            if basename.startswith(f"{candidate}.")
        ),
        None,
    )
    if role is None:
        return None

    remainder = basename[len(role) + 1 :]
    accession_code, separator, extension = remainder.rpartition(".")
    if not separator or not accession_code or not extension:
        return None

    if extension.lower() in COMPRESSION_EXTENSIONS:
        accession_code, separator, inner_extension = accession_code.rpartition(".")
        if not separator or not accession_code or not inner_extension:
            return None
        extension = f"{inner_extension}.{extension}"

    validate_file_role(role)
    return {
        "category": role,
        "file_role": role,
        "accession_code": accession_code,
        "extension": extension,
    }
