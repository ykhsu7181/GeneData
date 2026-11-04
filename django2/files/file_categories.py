"""File-role compatibility labels independent of the retired GenomeFile model."""


FILE_CATEGORY_CHOICES = (
    ('variableBlocks', 'Variable Blocks'),
    ('genome', 'Genome'),
    ('transcriptome.all', 'Transcriptome-All'),
    ('transcriptome.root', 'Transcriptome-Root'),
    ('transcriptome.stem', 'Transcriptome-Stem'),
    ('transcriptome.leaf', 'Transcriptome-Leaf'),
    ('transcriptome.panicles', 'Transcriptome-Panicles'),
    ('transcriptome.shoot', 'Transcriptome-Shoot'),
    ('miRNA', 'miRNA'),
    ('tRNA', 'tRNA'),
    ('rRNA', 'rRNA'),
    ('codon', 'Codon'),
    ('centromere', 'Centromere'),
    ('TEs', 'TEs'),
    ('annotation', 'Annotation'),
    ('coreBlocks', 'Core Blocks'),
    ('other', 'Other'),
)

FILE_CATEGORY_CODES = tuple(code for code, _label in FILE_CATEGORY_CHOICES)
