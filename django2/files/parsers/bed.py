from files.parsers.fasta import resolve_sequence_alias


def parse_lines(lines, chromosome=None, chromosome_aliases=None):
    results = []
    resolved_chromosome = resolve_sequence_alias(chromosome, chromosome_aliases)
    for index, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        seqid = resolve_sequence_alias(parts[0], chromosome_aliases)
        if resolved_chromosome and seqid != resolved_chromosome:
            continue
        start = int(parts[1])
        end = int(parts[2])
        results.append(
            {
                "id": f"{seqid}:{start}-{end}:{index}",
                "seqid": seqid,
                "start": start,
                "end": end,
                "length": max(end - start, 0),
                "name": parts[3] if len(parts) > 3 else None,
                "score": parts[4] if len(parts) > 4 else None,
                "strand": parts[5] if len(parts) > 5 else None,
                "phase": None,
                "attributes": {},
            }
        )
    return results
