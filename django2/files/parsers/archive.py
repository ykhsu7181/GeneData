import os
import tarfile
import zipfile
from io import TextIOWrapper

from files.parsers.bed import parse_lines as parse_bed_lines
from files.parsers.bed import iter_lines as iter_bed_lines
from files.parsers.fasta import open_text_file
from files.parsers.gff import parse_lines as parse_gff_lines
from files.parsers.gff import iter_lines as iter_gff_lines


def safe_extract_zip(file_path, destination):
    """Extract a ZIP after rejecting members outside the destination."""
    destination = os.path.realpath(destination)
    with zipfile.ZipFile(file_path, "r") as archive:
        for member in archive.infolist():
            target = os.path.realpath(os.path.join(destination, member.filename))
            if os.path.commonpath((destination, target)) != destination:
                raise ValueError(f"Unsafe ZIP member path: {member.filename}")
        archive.extractall(destination)


def parse_feature_file(file_path, chromosome=None, feature_type=None, chromosome_aliases=None):
    lower_path = file_path.lower()
    if lower_path.endswith((".gff", ".gff3", ".gff.gz", ".gff3.gz")):
        with open_text_file(file_path) as handle:
            return parse_gff_lines(
                handle,
                chromosome=chromosome,
                feature_type=feature_type,
                chromosome_aliases=chromosome_aliases,
            )

    if lower_path.endswith((".bed", ".bed.gz", ".txt", ".tsv")):
        with open_text_file(file_path) as handle:
            return parse_bed_lines(
                handle,
                chromosome=chromosome,
                chromosome_aliases=chromosome_aliases,
            )

    if lower_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(file_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                member_name = member.name.lower()
                if not member_name.endswith((".gff", ".gff3", ".bed", ".txt", ".tsv")):
                    continue
                extracted = archive.extractfile(member)
                if not extracted:
                    continue
                if member_name.endswith((".gff", ".gff3")):
                    return parse_gff_lines(
                        TextIOWrapper(extracted, encoding="utf-8"),
                        chromosome=chromosome,
                        feature_type=feature_type,
                        chromosome_aliases=chromosome_aliases,
                    )
                if member_name.endswith((".bed", ".txt", ".tsv")):
                    return parse_bed_lines(
                        TextIOWrapper(extracted, encoding="utf-8"),
                        chromosome=chromosome,
                        chromosome_aliases=chromosome_aliases,
                    )
    return []


def iter_feature_file(file_path, chromosome_aliases=None):
    """Stream normalized features from a supported annotation file.

    This iterator is intended for offline index construction. Request handlers
    must query ``AnnotationFeature`` instead of consuming source files.
    """
    lower_path = file_path.lower()
    if lower_path.endswith((".gff", ".gff3", ".gff.gz", ".gff3.gz")):
        with open_text_file(file_path) as handle:
            yield from iter_gff_lines(handle, chromosome_aliases=chromosome_aliases)
        return

    if lower_path.endswith((".bed", ".bed.gz", ".txt", ".tsv")):
        with open_text_file(file_path) as handle:
            yield from iter_bed_lines(handle, chromosome_aliases=chromosome_aliases)
        return

    if lower_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(file_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                member_name = member.name.lower()
                if not member_name.endswith((".gff", ".gff3", ".bed", ".txt", ".tsv")):
                    continue
                extracted = archive.extractfile(member)
                if not extracted:
                    continue
                text_handle = TextIOWrapper(extracted, encoding="utf-8")
                if member_name.endswith((".gff", ".gff3")):
                    yield from iter_gff_lines(text_handle, chromosome_aliases=chromosome_aliases)
                elif member_name.endswith((".bed", ".txt", ".tsv")):
                    yield from iter_bed_lines(text_handle, chromosome_aliases=chromosome_aliases)


def read_text_members(file_path, suffixes):
    """Return text from regular members whose lowercase names match suffixes."""
    members = []
    with tarfile.open(file_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.lower().endswith(tuple(suffixes)):
                continue
            extracted = archive.extractfile(member)
            if extracted:
                members.append((member.name, extracted.read().decode("utf-8", errors="ignore")))
    return members
