"""Streaming statistics for an Assembly's primary genome FASTA."""

import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP

from files.parsers.fasta import open_text_file


PERCENT_QUANTUM = Decimal("0.001")
N_RUN_PATTERN = re.compile(r"N+")


def _percentage(numerator, denominator):
    if not denominator:
        return None
    return (
        Decimal(numerator) * Decimal(100) / Decimal(denominator)
    ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_fasta_statistics(file_path):
    """Calculate wrapping-independent sequence statistics without loading the FASTA into memory.

    GC and AT percentages use canonical A/C/G/T bases as their denominator.
    N percentage uses total sequence length. A gap is one contiguous N run and
    cannot span two FASTA records. The sequence MD5 ignores headers and line
    wrapping, preserves record order/boundaries, and normalizes bases to upper
    case.
    """
    lengths = []
    sequence_count = 0
    current_length = None
    canonical_count = 0
    gc_count = 0
    at_count = 0
    n_count = 0
    gap_count = 0
    in_gap = False
    sequence_md5 = hashlib.md5()

    with open_text_file(str(file_path)) as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                if current_length is not None:
                    lengths.append(current_length)
                    sequence_md5.update(b"\n")
                sequence_count += 1
                current_length = 0
                in_gap = False
                continue
            if current_length is None:
                raise ValueError(
                    f"Invalid FASTA: sequence data before first header at line {line_number}"
                )

            sequence = "".join(stripped.split()).upper()
            if not sequence:
                continue
            try:
                encoded = sequence.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError(
                    f"Invalid FASTA: non-ASCII sequence data at line {line_number}"
                ) from exc

            sequence_md5.update(encoded)
            current_length += len(sequence)
            a_count = sequence.count("A")
            c_count = sequence.count("C")
            g_count = sequence.count("G")
            t_count = sequence.count("T")
            line_n_count = sequence.count("N")
            canonical_count += a_count + c_count + g_count + t_count
            gc_count += g_count + c_count
            at_count += a_count + t_count
            n_count += line_n_count

            line_gap_count = len(N_RUN_PATTERN.findall(sequence))
            if in_gap and sequence.startswith("N"):
                line_gap_count -= 1
            gap_count += line_gap_count
            in_gap = sequence.endswith("N")

    if current_length is None:
        raise ValueError("Invalid FASTA: no sequence records found")
    lengths.append(current_length)
    sequence_md5.update(b"\n")

    genome_size = sum(lengths)
    cumulative_length = 0
    n50 = 0
    for length in sorted(lengths, reverse=True):
        cumulative_length += length
        if cumulative_length * 2 >= genome_size:
            n50 = length
            break

    return {
        "genome_size": genome_size,
        "n50": n50,
        "gc_content": _percentage(gc_count, canonical_count),
        "at_content": _percentage(at_count, canonical_count),
        "n_count": n_count,
        "n_percentage": _percentage(n_count, genome_size),
        "sequence_count": sequence_count,
        "sequence_md5": sequence_md5.hexdigest(),
        "gap_count": gap_count,
    }
