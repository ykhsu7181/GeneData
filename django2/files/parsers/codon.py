import re

from files.parsers.archive import read_text_members


CODON_TO_AMINO_ACID = {
    "GCU": "Ala", "GCC": "Ala", "GCA": "Ala", "GCG": "Ala",
    "CGU": "Arg", "CGC": "Arg", "CGA": "Arg", "CGG": "Arg", "AGA": "Arg", "AGG": "Arg",
    "AAU": "Asn", "AAC": "Asn", "GAU": "Asp", "GAC": "Asp",
    "UGU": "Cys", "UGC": "Cys", "GAA": "Glu", "GAG": "Glu",
    "CAA": "Gln", "CAG": "Gln", "GGU": "Gly", "GGC": "Gly", "GGA": "Gly", "GGG": "Gly",
    "CAU": "His", "CAC": "His", "AUU": "Ile", "AUC": "Ile", "AUA": "Ile",
    "UUA": "Leu", "UUG": "Leu", "CUU": "Leu", "CUC": "Leu", "CUA": "Leu", "CUG": "Leu",
    "AAA": "Lys", "AAG": "Lys", "AUG": "Met", "UUU": "Phe", "UUC": "Phe",
    "CCU": "Pro", "CCC": "Pro", "CCA": "Pro", "CCG": "Pro",
    "UCU": "Ser", "UCC": "Ser", "UCA": "Ser", "UCG": "Ser", "AGU": "Ser", "AGC": "Ser",
    "ACU": "Thr", "ACC": "Thr", "ACA": "Thr", "ACG": "Thr",
    "UGG": "Trp", "UAU": "Tyr", "UAC": "Tyr",
    "GUU": "Val", "GUC": "Val", "GUA": "Val", "GUG": "Val",
    "UAA": "TER", "UAG": "TER", "UGA": "TER",
}


def parse_blk_content(content):
    matches = re.findall(r"([AUGC]{3})(\d+)\s+([\d.]+)", content)
    return {
        codon: {"count": int(count), "rscu": float(rscu)}
        for codon, count, rscu in matches
    }


def parse_statistics_content(content):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    headers = lines[0].split("\t")
    values = lines[1].split("\t")
    if len(headers) != len(values):
        return None
    result = {}
    for header, value in zip(headers, values):
        try:
            result[header] = float(value) if "." in value else int(value)
        except ValueError:
            result[header] = value
    return result


def format_usage(codon_usage):
    total_codons = sum(item["count"] for item in codon_usage.values())
    return {
        codon: {
            "amino_acid": CODON_TO_AMINO_ACID.get(codon, "Unknown"),
            "codon": codon,
            "count": item["count"],
            "frequency": item["rscu"],
            "global_frequency": item["count"] / total_codons if total_codons else 0,
            "relative_frequency": item["rscu"],
        }
        for codon, item in codon_usage.items()
    }


def group_by_amino_acid(codon_usage):
    amino_acids = {}
    for data in codon_usage.values():
        name = data["amino_acid"]
        bucket = amino_acids.setdefault(name, {"name": name, "codons": [], "total_count": 0})
        bucket["codons"].append(data)
        bucket["total_count"] += data["count"]
    for bucket in amino_acids.values():
        total = bucket["total_count"]
        for codon in bucket["codons"]:
            codon["relative_frequency"] = codon["count"] / total if total else 0
    return amino_acids


def calculate_nucleotide_composition(codon_usage):
    counts = {"A": 0, "T": 0, "G": 0, "C": 0}
    total = 0
    for codon, item in codon_usage.items():
        for nucleotide in codon.replace("U", "T"):
            if nucleotide in counts:
                counts[nucleotide] += item["count"]
                total += item["count"]
    return counts if not total else {key: (value / total) * 100 for key, value in counts.items()}


def load_payload(file_path, organism_name):
    blk_content = None
    stats_content = None
    lower_path = file_path.lower()

    if lower_path.endswith(".blk"):
        with open(file_path, "r", encoding="utf-8") as handle:
            blk_content = handle.read()
    elif lower_path.endswith((".txt", ".out")):
        with open(file_path, "r", encoding="utf-8") as handle:
            stats_content = handle.read()
    elif lower_path.endswith((".tar.gz", ".tgz")):
        for member_name, content in read_text_members(file_path, (".blk", ".txt", ".out")):
            lower_name = member_name.lower()
            if blk_content is None and lower_name.endswith(".blk"):
                blk_content = content
            elif stats_content is None and lower_name.endswith((".txt", ".out")):
                stats_content = content

    if not blk_content:
        return None
    codon_usage = parse_blk_content(blk_content)
    if not codon_usage:
        return None

    formatted = format_usage(codon_usage)
    payload = {
        "organism": organism_name,
        "codon_usage": formatted,
        "amino_acids": group_by_amino_acid(formatted),
        "total_codons": sum(item["count"] for item in codon_usage.values()),
        "nucleotide_composition": calculate_nucleotide_composition(codon_usage),
    }
    statistics = parse_statistics_content(stats_content) if stats_content else None
    if statistics:
        payload["statistics"] = statistics
    return payload
