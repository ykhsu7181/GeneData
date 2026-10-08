CANONICAL_FILE_ROLES = frozenset(
    {
        "genome",
        "genome_fasta",
        "genome_index",
        "annotation",
        "jbrowse_annotation_gff3",
        "jbrowse_annotation_tabix",
        "centromere",
        "telomere",
        "codon",
        "coreBlocks",
        "variableBlocks",
        "miRNA",
        "tRNA",
        "rRNA",
        "TEs",
        "transcriptome.all",
        "transcriptome.root",
        "transcriptome.stem",
        "transcriptome.leaf",
        "transcriptome.panicles",
        "transcriptome.shoot",
        "hifi_reads",
        "raw_reads_R1",
        "raw_reads_R2",
        "rnaseq_raw",
        "wgs_reads",
        "other",
    }
)


def validate_file_role(role):
    """Return the canonical role or reject unknown/empty values."""
    if role not in CANONICAL_FILE_ROLES:
        raise ValueError(f"Unknown file role: {role!r}")
    return role
