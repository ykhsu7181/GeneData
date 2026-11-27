"""Format-only FASTA index construction shared by all ownership paths."""

import os
import tempfile


def build_fasta_index(file_path, index_path=None):
    if file_path.lower().endswith(".gz"):
        raise ValueError("Compressed FASTA requires bgzip/samtools and is not supported here")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)
    index_path = index_path or f"{file_path}.fai"
    directory = os.path.dirname(os.path.abspath(index_path))
    os.makedirs(directory, exist_ok=True)
    entries = []
    with open(file_path, "rb") as handle:
        name = None
        length = 0
        sequence_offset = None
        line_bases = None
        line_width = None
        saw_short_line = False
        while True:
            offset = handle.tell()
            raw_line = handle.readline()
            if not raw_line:
                if name is not None:
                    entries.append((name, length, sequence_offset, line_bases or 0, line_width or 0))
                break
            if raw_line.startswith(b">"):
                if name is not None:
                    entries.append((name, length, sequence_offset, line_bases or 0, line_width or 0))
                header = raw_line.decode("utf-8").rstrip("\r\n")
                name = header[1:].strip().split()[0] if header[1:].strip() else None
                if not name:
                    raise ValueError(f"Invalid FASTA header at byte {offset}")
                length = 0
                sequence_offset = handle.tell()
                line_bases = None
                line_width = None
                saw_short_line = False
                continue
            if name is None:
                if raw_line.strip():
                    raise ValueError("FASTA sequence encountered before the first header")
                continue
            bases = len(raw_line.rstrip(b"\r\n"))
            if bases == 0:
                continue
            if saw_short_line:
                raise ValueError(f"Non-terminal short FASTA line for sequence {name}")
            if line_bases is None:
                line_bases = bases
                line_width = len(raw_line)
            elif bases > line_bases or len(raw_line) > line_width:
                raise ValueError(f"Inconsistent FASTA line width for sequence {name}")
            elif bases < line_bases or len(raw_line) < line_width:
                saw_short_line = True
            length += bases

    fd, temporary_path = tempfile.mkstemp(prefix=".fai-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write("\t".join(str(value) for value in entry) + "\n")
        os.replace(temporary_path, index_path)
    except Exception:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise
    return index_path, entries
