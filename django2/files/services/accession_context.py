from types import SimpleNamespace

from files.models import Accession, Annotation, Assembly
from files.services.file_relation_service import get_primary_file


DEFAULT_ASSEMBLY_NAME = 'default'
DEFAULT_ANNOTATION_NAME = 'default-annotation'


class AmbiguousContextError(ValueError):
    """Raised when a query context cannot be selected without guessing."""

    code = 'ambiguous_context'

    def __init__(self, related_type, parent_code):
        self.related_type = related_type
        self.parent_code = str(parent_code)
        super().__init__(
            f"Multiple {related_type} records match {self.parent_code}; "
            "provide an explicit context id or configure exactly one default."
        )

ASSEMBLY_LEVEL_CATEGORIES = {
    'genome',
    'centromere',
    'coreBlocks',
    'variableBlocks',
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


def classify_file_scope(category):
    if category in ANNOTATION_LEVEL_CATEGORIES:
        return 'annotation'
    if category in ASSEMBLY_LEVEL_CATEGORIES:
        return 'assembly'
    if category in COMPATIBILITY_ASSEMBLY_CATEGORIES:
        return 'compatibility_assembly'
    return 'compatibility_assembly'


def get_default_assembly(accession):
    if not accession:
        return None
    defaults = list(accession.assemblies.filter(is_default=True).order_by('id')[:2])
    if len(defaults) > 1:
        raise AmbiguousContextError('assembly', accession.accession)
    return defaults[0] if defaults else None


def get_default_annotation(assembly):
    if not assembly:
        return None
    defaults = list(assembly.annotations.filter(is_default=True).order_by('id')[:2])
    if len(defaults) > 1:
        raise AmbiguousContextError('annotation', assembly.id)
    return defaults[0] if defaults else None


def resolve_preferred_assembly(accession):
    if not accession:
        return None
    default = get_default_assembly(accession)
    if default:
        return default
    assemblies = list(accession.assemblies.all().order_by('id')[:2])
    if len(assemblies) > 1:
        raise AmbiguousContextError('assembly', accession.accession)
    return assemblies[0] if assemblies else None


def resolve_preferred_annotation(assembly):
    if not assembly:
        return None
    default = get_default_annotation(assembly)
    if default:
        return default
    annotations = list(assembly.annotations.all().order_by('id')[:2])
    if len(annotations) > 1:
        raise AmbiguousContextError('annotation', assembly.id)
    return annotations[0] if annotations else None


def resolve_accession(accession=None, organism=None):
    accession_code = accession or organism
    if not accession_code:
        return None
    return Accession.objects.filter(accession=accession_code).first()


def resolve_assembly_context(*, assembly_id=None, accession=None, organism=None):
    assembly = None
    accession_obj = None

    if assembly_id:
        assembly = Assembly.objects.filter(id=assembly_id).select_related('accession').first()
        if assembly:
            accession_obj = assembly.accession
            return accession_obj, assembly
        return None, None

    accession_obj = resolve_accession(accession=accession, organism=organism)
    if not accession_obj:
        return None, None

    assembly = resolve_preferred_assembly(accession_obj)
    return accession_obj, assembly


def resolve_annotation_context(*, annotation_id=None, assembly_id=None, accession=None, organism=None):
    annotation = None

    if annotation_id:
        annotation = Annotation.objects.filter(id=annotation_id).select_related('assembly__accession').first()
        if annotation:
            return annotation.assembly.accession, annotation.assembly, annotation
        return None, None, None

    accession_obj, assembly = resolve_assembly_context(
        assembly_id=assembly_id,
        accession=accession,
        organism=organism,
    )
    if not assembly:
        return accession_obj, assembly, None

    annotation = resolve_preferred_annotation(assembly)
    return accession_obj, assembly, annotation


def get_context_organism(*, annotation_id=None, assembly_id=None, accession=None, organism=None):
    accession_obj, assembly, annotation = resolve_annotation_context(
        annotation_id=annotation_id,
        assembly_id=assembly_id,
        accession=accession,
        organism=organism,
    )
    if annotation:
        return annotation.assembly.accession.accession, accession_obj, assembly, annotation
    if assembly:
        return assembly.accession.accession, accession_obj, assembly, None
    if accession_obj:
        return accession_obj.accession, accession_obj, None, None
    return organism or accession, None, None, None


def get_context_genome_file(*, assembly_id=None, accession=None, organism=None):
    accession_obj, assembly = resolve_assembly_context(
        assembly_id=assembly_id,
        accession=accession,
        organism=organism,
    )

    if assembly:
        genome_file = _service_file_to_context_file(
            get_primary_file('assembly', assembly.id, file_role='genome')
        )
        return accession_obj, assembly, genome_file

    if not accession_obj:
        return accession_obj, assembly, None

    genome_file = _service_file_to_context_file(
        get_primary_file('accession', accession_obj.id, file_role='genome')
    )
    return accession_obj, assembly, genome_file


def _service_file_to_context_file(service_file):
    if not service_file:
        return None
    return SimpleNamespace(
        id=service_file.get('file_id'),
        name=service_file.get('file_name'),
        file_path=service_file.get('file_path'),
        category=service_file.get('file_role'),
        source=service_file.get('source'),
        file_code=service_file.get('file_code'),
        file_size=service_file.get('file_size'),
        md5=service_file.get('md5'),
    )
