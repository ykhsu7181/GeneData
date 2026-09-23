from files.parsers.fasta import resolve_sequence_alias


def iter_lines(lines, chromosome=None, chromosome_aliases=None):
    resolved_chromosome = resolve_sequence_alias(chromosome, chromosome_aliases)
    for index, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        # Most files use standard BED columns (chromosome, start, end, ...).
        # The production miRNA tables use a legacy eight-column layout:
        # name, RFAM, chromosome, start, end, strand, score, E-value.
        # Detect that layout by its numeric coordinate columns instead of by
        # filename so the parser remains usable for streamed/archive members.
        legacy_mirna = (
            len(parts) >= 6
            and not _is_integer(parts[1])
            and _is_integer(parts[3])
            and _is_integer(parts[4])
        )
        if legacy_mirna:
            raw_start = int(parts[3])
            raw_end = int(parts[4])
            seqid = resolve_sequence_alias(parts[2], chromosome_aliases)
            start = min(raw_start, raw_end)
            end = max(raw_start, raw_end)
            name = parts[0] or None
            score = parts[6] if len(parts) > 6 else None
            strand = parts[5] if len(parts) > 5 else None
            attributes = {
                "rfam": parts[1],
                "evalue": parts[7] if len(parts) > 7 else None,
            }
        else:
            if not _is_integer(parts[1]) or not _is_integer(parts[2]):
                continue
            seqid = resolve_sequence_alias(parts[0], chromosome_aliases)
            start = int(parts[1])
            end = int(parts[2])
            name = parts[3] if len(parts) > 3 else None
            score = parts[4] if len(parts) > 4 else None
            strand = parts[5] if len(parts) > 5 else None
            attributes = {}

        if resolved_chromosome and seqid != resolved_chromosome:
            continue
        yield {
                "id": f"{seqid}:{start}-{end}:{index}",
                "seqid": seqid,
                "start": start,
                "end": end,
                "length": max(end - start, 0),
                "name": name,
                "score": score,
                "strand": strand,
                "phase": None,
                "attributes": attributes,
            }


def parse_lines(lines, chromosome=None, chromosome_aliases=None):
    return list(iter_lines(lines, chromosome, chromosome_aliases))


def _is_integer(value):
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True
