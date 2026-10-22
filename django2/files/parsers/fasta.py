import gzip
import os
import time
from dataclasses import dataclass


class FastaScanLimitExceeded(RuntimeError):
    """Raised when an unindexed FASTA exceeds the configured fallback budget."""


@dataclass(frozen=True)
class FastaIndexEntry:
    name: str
    length: int
    offset: int
    line_bases: int
    line_width: int


def open_text_file(file_path):
    if file_path.lower().endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf-8")
    return open(file_path, "r", encoding="utf-8")


def parse_sequence_id(header_line):
    """Return the canonical sequence ID stored in a FASTA header."""
    header = (header_line or "").strip()
    if header.startswith(">"):
        header = header[1:].strip()
    if not header:
        return None

    tokens = header.split()
    for token in tokens:
        if token.startswith("OriSeqID="):
            sequence_id = token.split("=", 1)[1].strip()
            if sequence_id:
                return sequence_id
    return tokens[0]


def build_sequence_aliases(file_path, *, index_path=None, max_bytes=None, timeout_seconds=None):
    """Map raw FASTA IDs and canonical IDs to the same canonical value."""
    if index_path:
        return {sequence_id: sequence_id for sequence_id in read_fai(index_path)}

    aliases = {}
    if not file_path or not os.path.exists(file_path):
        return aliases

    _ensure_scan_budget(file_path, max_bytes)
    started_at = time.monotonic()
    with open_text_file(file_path) as handle:
        for line in handle:
            _ensure_scan_deadline(started_at, timeout_seconds)
            header = line.strip()
            if not header.startswith(">"):
                continue
            raw_header = header[1:].strip()
            if not raw_header:
                continue
            raw_sequence_id = raw_header.split()[0]
            canonical_sequence_id = parse_sequence_id(header)
            if not canonical_sequence_id:
                continue
            aliases[raw_sequence_id] = canonical_sequence_id
            aliases[canonical_sequence_id] = canonical_sequence_id
    return aliases


def resolve_sequence_alias(sequence_id, aliases):
    sequence_id = (sequence_id or "").strip()
    if not sequence_id:
        return None
    return (aliases or {}).get(sequence_id, sequence_id)


def read_fai(file_path):
    """Read sequence lengths from a standard samtools FASTA index."""
    entries = {}
    with open(file_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 2 or not columns[0]:
                raise ValueError(f"Invalid FASTA index row at line {line_number}")
            try:
                entries[columns[0]] = int(columns[1])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid FASTA index length at line {line_number}"
                ) from exc
    return entries


def read_fai_entries(file_path):
    """Read and validate all five standard random-access FAI columns."""
    entries = {}
    with open(file_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 5 or not columns[0]:
                raise ValueError(f"Invalid FASTA index row at line {line_number}")
            try:
                length, offset, line_bases, line_width = (
                    int(value) for value in columns[1:5]
                )
            except ValueError as exc:
                raise ValueError(
                    f"Invalid FASTA index number at line {line_number}"
                ) from exc
            if (
                columns[0] in entries
                or length < 1
                or offset < 0
                or line_bases < 1
                or line_width < line_bases
            ):
                raise ValueError(f"Invalid FASTA index row at line {line_number}")
            entries[columns[0]] = FastaIndexEntry(
                name=columns[0],
                length=length,
                offset=offset,
                line_bases=line_bases,
                line_width=line_width,
            )
    if not entries:
        raise ValueError("FASTA index contains no sequence rows")
    return entries


def fetch_sequence_region(fasta_path, sequence_id, start, end, index_path):
    """Fetch a 1-based inclusive region from an uncompressed indexed FASTA."""
    if str(fasta_path).lower().endswith(".gz"):
        raise ValueError("Compressed FASTA random access is not supported")
    entries = read_fai_entries(index_path)
    entry = entries.get(sequence_id)
    if entry is None:
        raise KeyError(sequence_id)
    if start < 1 or end < start or end > entry.length:
        raise ValueError("Invalid 1-based inclusive FASTA region")

    start_zero = start - 1
    end_zero = end - 1
    byte_start = (
        entry.offset
        + (start_zero // entry.line_bases) * entry.line_width
        + (start_zero % entry.line_bases)
    )
    byte_end = (
        entry.offset
        + (end_zero // entry.line_bases) * entry.line_width
        + (end_zero % entry.line_bases)
        + 1
    )
    with open(fasta_path, "rb") as handle:
        handle.seek(byte_start)
        raw = handle.read(byte_end - byte_start)
    sequence = raw.replace(b"\n", b"").replace(b"\r", b"")
    expected_length = end - start + 1
    if len(sequence) != expected_length:
        raise ValueError("FASTA content does not match its index")
    return sequence


def _ensure_scan_budget(file_path, max_bytes):
    if max_bytes is not None and os.path.getsize(file_path) > max_bytes:
        raise FastaScanLimitExceeded(
            f"Unindexed FASTA exceeds fallback size limit ({max_bytes} bytes)"
        )


def _ensure_scan_deadline(started_at, timeout_seconds):
    if timeout_seconds is not None and time.monotonic() - started_at > timeout_seconds:
        raise FastaScanLimitExceeded(
            f"Unindexed FASTA scan exceeded fallback timeout ({timeout_seconds} seconds)"
        )


def list_sequence_ids(file_path, *, index_path=None, max_bytes=None, timeout_seconds=None):
    if index_path:
        return list(read_fai(index_path))

    _ensure_scan_budget(file_path, max_bytes)
    started_at = time.monotonic()
    sequence_ids = []
    with open_text_file(file_path) as handle:
        for line in handle:
            _ensure_scan_deadline(started_at, timeout_seconds)
            if line.lstrip().startswith(">"):
                sequence_id = parse_sequence_id(line)
                if sequence_id:
                    sequence_ids.append(sequence_id)
    return sequence_ids


def sequence_length(file_path, sequence_id, *, index_path=None, max_bytes=None, timeout_seconds=None):
    if index_path:
        indexed_lengths = read_fai(index_path)
        return indexed_lengths.get(sequence_id)

    _ensure_scan_budget(file_path, max_bytes)
    started_at = time.monotonic()
    aliases = build_sequence_aliases(
        file_path,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
    )
    requested_id = resolve_sequence_alias(sequence_id, aliases)
    current_id = None
    current_length = 0

    with open_text_file(file_path) as handle:
        for line in handle:
            _ensure_scan_deadline(started_at, timeout_seconds)
            line = line.strip()
            if line.startswith(">"):
                if current_id == requested_id:
                    return current_length
                current_id = parse_sequence_id(line)
                current_length = 0
            elif current_id:
                current_length += len(line)
    return current_length if current_id == requested_id else None
