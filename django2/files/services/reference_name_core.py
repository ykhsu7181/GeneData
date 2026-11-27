"""Format-only reference-name parsing shared by legacy and DataAsset paths."""


class ReferenceNameError(RuntimeError):
    def __init__(self, message, *, code="mapping_unavailable"):
        super().__init__(message)
        self.code = code


def read_fasta_reference_names(file_path):
    seqids = set()
    aliases = {}
    lengths = {}
    current_seqid = None
    sequence_bases = 0
    with open(file_path, "rt", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if line.startswith(">"):
                if current_seqid is not None and sequence_bases == 0:
                    raise ValueError(f"FASTA sequence has no bases: {current_seqid}")
                if current_seqid is not None:
                    lengths[current_seqid] = sequence_bases
                header = line[1:].strip()
                seqid = header.split()[0] if header else ""
                if not seqid:
                    raise ValueError(f"empty FASTA header at line {line_number}")
                if seqid in seqids:
                    raise ValueError(f"duplicate FASTA sequence ID: {seqid}")
                seqids.add(seqid)
                aliases.setdefault(seqid, set()).add(seqid)
                for token in header.split():
                    if token.startswith("OriSeqID=") and token[9:]:
                        aliases.setdefault(token[9:], set()).add(seqid)
                current_seqid = seqid
                sequence_bases = 0
                continue
            if current_seqid is None:
                raise ValueError(
                    f"FASTA sequence encountered before header at line {line_number}"
                )
            sequence_bases += len(stripped)
    if not seqids:
        raise ValueError("FASTA contains no sequence headers")
    if current_seqid is not None and sequence_bases == 0:
        raise ValueError(f"FASTA sequence has no bases: {current_seqid}")
    lengths[current_seqid] = sequence_bases
    return seqids, aliases, lengths


def read_fai_reference_lengths(file_path):
    lengths = {}
    with open(file_path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 2 or not columns[0]:
                raise ValueError(f"invalid FAI row at line {line_number}")
            try:
                length = int(columns[1])
            except ValueError as exc:
                raise ValueError(f"invalid FAI length at line {line_number}") from exc
            if length < 1 or columns[0] in lengths:
                raise ValueError(f"invalid or duplicate FAI refName at line {line_number}")
            lengths[columns[0]] = length
    if not lengths:
        raise ValueError("FAI contains no reference rows")
    return lengths


def build_reference_name_payload(genome_file, fasta_index):
    """Build a validated in-memory alias map from one FASTA/FAI pair."""
    try:
        fasta_seqids, aliases, fasta_lengths = read_fasta_reference_names(
            genome_file.file_path
        )
        fai_lengths = read_fai_reference_lengths(fasta_index.file_path)
    except OSError as exc:
        raise ReferenceNameError(
            "The FASTA or FAI cannot be read", code="reference_missing"
        ) from exc
    except (UnicodeError, ValueError) as exc:
        raise ReferenceNameError(
            "The FASTA or FAI is invalid", code="reference_invalid"
        ) from exc
    if fasta_seqids != set(fai_lengths):
        raise ReferenceNameError(
            "FASTA first-token refNames do not match the FAI first column",
            code="fasta_fai_mismatch",
        )
    if any(fasta_lengths[name] != fai_lengths[name] for name in fasta_seqids):
        raise ReferenceNameError(
            "FASTA sequence lengths do not match the FAI",
            code="fasta_fai_length_mismatch",
        )
    alias_records = {}
    for alias, candidates in sorted(aliases.items()):
        ref_names = sorted(candidates)
        alias_records[alias] = {
            "status": "resolved" if len(ref_names) == 1 else "ambiguous",
            "ref_names": ref_names,
        }
    return {"aliases": alias_records, "reference_lengths": fai_lengths}


def resolve_refname(payload, alias):
    record = (payload.get("aliases") or {}).get(alias)
    if not record:
        raise ReferenceNameError("No JBrowse refName exists for this seqid", code="alias_missing")
    ref_names = record.get("ref_names") or []
    if record.get("status") == "ambiguous" or len(ref_names) != 1:
        raise ReferenceNameError(
            "The seqid maps to multiple JBrowse refNames", code="alias_ambiguous"
        )
    ref_name = ref_names[0]
    length = (payload.get("reference_lengths") or {}).get(ref_name)
    if not isinstance(length, int) or length < 1:
        raise ReferenceNameError(
            "The mapped refName has no valid FAI length", code="mapping_invalid"
        )
    return ref_name, length
