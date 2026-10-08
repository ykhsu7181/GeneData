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

    # Samtools indexes conventionally append ``.fai`` to the complete FASTA
    # name (for example ``genome.IR64.fasta.fai``).  Parse the FASTA name
    # first so ``fasta`` is not mistaken for part of the accession code.
    if basename.lower().endswith(".fai"):
        fasta_name = basename[:-4]
        parsed_fasta = parse_ingestion_filename(fasta_name)
        if parsed_fasta and parsed_fasta["file_role"] in {"genome", "genome_fasta"}:
            return {
                "category": "genome_index",
                "file_role": "genome_index",
                "accession_code": parsed_fasta["accession_code"],
                "extension": f"{parsed_fasta['extension']}.fai",
            }
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
