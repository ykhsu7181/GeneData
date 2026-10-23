"""Public visibility rules for migration-era Assembly placeholders."""

from django.db.models import Exists, OuterRef, Q

from files.models import Assembly


PLACEHOLDER_ASSEMBLY_NAME = "default"


def placeholder_assembly_query():
    """Return the strict signature used by generated legacy placeholders."""
    return Q(name=PLACEHOLDER_ASSEMBLY_NAME) & (
        Q(assembly_code__isnull=True) | Q(assembly_code="")
    )


def is_placeholder_assembly(assembly):
    return (
        assembly.name == PLACEHOLDER_ASSEMBLY_NAME
        and not (assembly.assembly_code or "").strip()
    )


def visible_assembly_queryset(queryset=None):
    """Hide a placeholder when its Accession has a real replacement."""
    queryset = queryset if queryset is not None else Assembly.objects.all()
    real_replacement = (
        Assembly.objects
        .filter(accession_id=OuterRef("accession_id"))
        .exclude(id=OuterRef("id"))
        .exclude(Q(assembly_code__isnull=True) | Q(assembly_code=""))
    )
    return (
        queryset
        .annotate(_has_real_replacement=Exists(real_replacement))
        .exclude(placeholder_assembly_query() & Q(_has_real_replacement=True))
    )


def public_assembly_list_queryset(queryset=None):
    """Never advertise strict migration placeholders in the Assembly catalog."""
    queryset = queryset if queryset is not None else Assembly.objects.all()
    return queryset.exclude(placeholder_assembly_query())


def filter_visible_assemblies(assemblies):
    """Apply the same rule to prefetched or already-materialized objects."""
    items = list(assemblies)
    if not any((item.assembly_code or "").strip() for item in items):
        return items
    return [item for item in items if not is_placeholder_assembly(item)]
