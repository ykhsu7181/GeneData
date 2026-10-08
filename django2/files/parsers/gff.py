from files.parsers.fasta import resolve_sequence_alias


def parse_attributes(raw_attributes):
    attributes = {}
    for item in (raw_attributes or "").split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
            attributes[key.strip()] = value.strip()
        elif " " in item:
            key, value = item.split(" ", 1)
            attributes[key.strip()] = value.strip().strip('"')
    return attributes


def iter_lines(lines, chromosome=None, feature_type=None, chromosome_aliases=None):
    resolved_chromosome = resolve_sequence_alias(chromosome, chromosome_aliases)
    for line_number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        seqid = resolve_sequence_alias(parts[0], chromosome_aliases)
        feature = parts[2]
        if resolved_chromosome and seqid != resolved_chromosome:
            continue
        if feature_type and feature != feature_type:
            continue
        start = int(parts[3])
        end = int(parts[4])
        attributes = parse_attributes(parts[8])
        yield {
                "seqid": seqid,
                "source": parts[1],
                "feature": feature,
                "start": start,
                "end": end,
                "length": end - start + 1,
                "score": None if parts[5] == "." else parts[5],
                "strand": parts[6],
                "phase": None if parts[7] == "." else parts[7],
                "attributes": attributes,
                "line_number": line_number,
                "sequence_ontology": feature,
                "name": attributes.get("Name") or attributes.get("ID"),
            }


def parse_lines(lines, chromosome=None, feature_type=None, chromosome_aliases=None):
    return list(iter_lines(lines, chromosome, feature_type, chromosome_aliases))
