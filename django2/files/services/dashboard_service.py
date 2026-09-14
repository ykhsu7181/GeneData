from django.conf import settings

from files.models import Accession, Annotation, Assembly, Species


FEATURED_ACCESSIONS_LIMIT = 5


def build_dashboard_payload():
    return {
        "summary": {
            "assembly_count": Assembly.objects.count(),
            "species_count": Species.objects.count(),
            "annotation_count": Annotation.objects.count(),
            "accession_count": Accession.objects.count(),
        },
        "featured_accessions": _build_featured_accessions(),
    }


def _first_display_value(instance, field_names):
    if not instance:
        return "-"
    for field_name in field_names:
        value = getattr(instance, field_name, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "-"


def _configured_featured_codes():
    configured_codes = getattr(settings, "DASHBOARD_FEATURED_ACCESSIONS", ())
    return list(dict.fromkeys(configured_codes))[:FEATURED_ACCESSIONS_LIMIT]


def _build_featured_accessions():
    featured_codes = _configured_featured_codes()
    if not featured_codes:
        return []

    accessions = (
        Accession.objects.filter(accession__in=featured_codes)
        .select_related("species")
        .prefetch_related("assemblies__annotations")
    )
    accessions_by_code = {item.accession: item for item in accessions}
    rows = []

    for accession_code in featured_codes:
        accession = accessions_by_code.get(accession_code)
        if not accession:
            continue

        assemblies = list(accession.assemblies.all())
        assembly = next((item for item in assemblies if item.is_default), None)
        if assembly is None and assemblies:
            assembly = assemblies[0]

        annotations = list(assembly.annotations.all()) if assembly else []
        annotation = next((item for item in annotations if item.is_default), None)
        if annotation is None and annotations:
            annotation = annotations[0]

        species = accession.species
        rows.append(
            {
                "accession": accession.accession,
                "species_scientific_name": species.scientific_name if species else None,
                "species_common_name": species.common_name if species else None,
                "assembly": _first_display_value(
                    assembly,
                    ("display_name", "assembly_name", "assembly_code", "name"),
                ),
                "annotation": _first_display_value(
                    annotation,
                    (
                        "annotation_version",
                        "release_version",
                        "annotation_name",
                        "annotation_code",
                        "name",
                    ),
                ),
            }
        )

    return rows
