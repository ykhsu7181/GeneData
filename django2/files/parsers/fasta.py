import gzip
import os
import time


class FastaScanLimitExceeded(RuntimeError):
    """Raised when an unindexed FASTA exceeds the configured fallback budget."""


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
                raise ValueError(f"Invalid FASTA index length at line {line_number}") from exc
    return entries


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
