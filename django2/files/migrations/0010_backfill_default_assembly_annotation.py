from django.db import migrations


DEFAULT_ASSEMBLY_NAME = 'default'
DEFAULT_ANNOTATION_NAME = 'default-annotation'

ASSEMBLY_LEVEL_CATEGORIES = {
    'genome',
    'centromere',
    'coreBlocks',
    'TEs',
    'miRNA',
    'tRNA',
    'rRNA',
}

ANNOTATION_LEVEL_CATEGORIES = {
    'annotation',
}

COMPATIBILITY_ASSEMBLY_CATEGORIES = {
    'codon',
    'other',
    'transcriptome.all',
    'transcriptome.root',
    'transcriptome.stem',
    'transcriptome.leaf',
    'transcriptome.panicles',
    'transcriptome.shoot',
}


def get_or_create_default_assembly(Assembly, accession):
    assembly = Assembly.objects.filter(accession_id=accession.id, is_default=True).first()
    if assembly:
        return assembly

    assembly = Assembly.objects.filter(accession_id=accession.id, name=DEFAULT_ASSEMBLY_NAME).first()
    if assembly:
        assembly.is_default = True
        assembly.save(update_fields=['is_default', 'updated_at'])
        return assembly

    return Assembly.objects.create(
        accession_id=accession.id,
        name=DEFAULT_ASSEMBLY_NAME,
        is_default=True,
    )


def get_or_create_default_annotation(Annotation, assembly):
    annotation = Annotation.objects.filter(assembly_id=assembly.id, is_default=True).first()
    if annotation:
        return annotation

    annotation = Annotation.objects.filter(assembly_id=assembly.id, name=DEFAULT_ANNOTATION_NAME).first()
    if annotation:
        annotation.is_default = True
        annotation.save(update_fields=['is_default', 'updated_at'])
        return annotation

    return Annotation.objects.create(
        assembly_id=assembly.id,
        name=DEFAULT_ANNOTATION_NAME,
        is_default=True,
    )


def forward(apps, schema_editor):
    Accession = apps.get_model('files', 'Accession')
    Assembly = apps.get_model('files', 'Assembly')
    Annotation = apps.get_model('files', 'Annotation')
    GenomeFile = apps.get_model('files', 'GenomeFile')

    accession_default_assembly = {}
    assembly_default_annotation = {}

    for accession in Accession.objects.all().order_by('id'):
        assembly = get_or_create_default_assembly(Assembly, accession)
        accession_default_assembly[accession.id] = assembly

    for assembly in Assembly.objects.all().order_by('id'):
        annotation = get_or_create_default_annotation(Annotation, assembly)
        assembly_default_annotation[assembly.id] = annotation

    for genome_file in GenomeFile.objects.all().order_by('id'):
        accession_id = genome_file.accession_id

        if not accession_id and genome_file.organism:
            accession = Accession.objects.filter(accession=genome_file.organism).first()
            if accession:
                accession_id = accession.id
                genome_file.accession_id = accession.id

        if not accession_id:
            save_fields = []
            if genome_file.accession_id:
                save_fields.append('accession')
            if save_fields:
                genome_file.save(update_fields=save_fields)
            continue

        assembly = accession_default_assembly.get(accession_id)
        if not assembly:
            accession = Accession.objects.filter(id=accession_id).first()
            if not accession:
                continue
            assembly = get_or_create_default_assembly(Assembly, accession)
            accession_default_assembly[accession_id] = assembly

        default_annotation = assembly_default_annotation.get(assembly.id)
        if not default_annotation:
            default_annotation = get_or_create_default_annotation(Annotation, assembly)
            assembly_default_annotation[assembly.id] = default_annotation

        genome_file.assembly_id = assembly.id

        if genome_file.category in ANNOTATION_LEVEL_CATEGORIES:
            genome_file.annotation_id = default_annotation.id
        elif genome_file.category in ASSEMBLY_LEVEL_CATEGORIES:
            genome_file.annotation_id = None
        elif genome_file.category in COMPATIBILITY_ASSEMBLY_CATEGORIES:
            # Compatibility mapping only. These categories are not yet finalized.
            genome_file.annotation_id = None
        else:
            # Fallback for legacy or uncategorized files: keep them reachable from
            # the default assembly without claiming final business ownership.
            genome_file.annotation_id = None

        genome_file.save(update_fields=['accession', 'assembly', 'annotation'])


def backward(apps, schema_editor):
    GenomeFile = apps.get_model('files', 'GenomeFile')
    Annotation = apps.get_model('files', 'Annotation')
    Assembly = apps.get_model('files', 'Assembly')

    GenomeFile.objects.all().update(assembly=None, annotation=None)
    Annotation.objects.filter(name=DEFAULT_ANNOTATION_NAME, is_default=True).delete()
    Assembly.objects.filter(name=DEFAULT_ASSEMBLY_NAME, is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0009_assembly_annotation_genomefile_links'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
