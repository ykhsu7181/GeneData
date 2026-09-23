from files.models import Accession, Annotation, Assembly, Species


DASHBOARD_CACHE_KEY = "warehouse_dashboard_payload_v3"
POPULAR_ACCESSIONS_LIMIT = 10


def build_dashboard_payload():
    return {
        "summary": {
            "assembly_count": Assembly.objects.count(),
            "species_count": Species.objects.count(),
            "annotation_count": Annotation.objects.count(),
            "accession_count": Accession.objects.count(),
        },
        # Keep the established response key while changing its source from a
        # settings list to measured Accession views.
        "featured_accessions": build_popular_accessions(),
    }


def _first_display_value(instance, field_names):
    if not instance:
        return ""
    for field_name in field_names:
        value = getattr(instance, field_name, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _annotation_display_value(annotation):
    return _first_display_value(
        annotation,
        (
            "display_name",
            "annotation_name",
            "annotation_version",
            "release_version",
            "annotation_code",
            "name",
        ),
    )


def build_popular_accessions(limit=POPULAR_ACCESSIONS_LIMIT):
    try:
        normalized_limit = max(1, min(int(limit), POPULAR_ACCESSIONS_LIMIT))
    except (TypeError, ValueError):
        normalized_limit = POPULAR_ACCESSIONS_LIMIT

    accessions = list(
        Accession.objects.filter(view_count__gt=0)
        .select_related("species")
        .prefetch_related("assemblies__annotations")
        .order_by("-view_count", "-last_viewed_at", "accession")[:normalized_limit]
    )
    rows = []

    for accession in accessions:
        assemblies = sorted(
            accession.assemblies.all(),
            key=lambda item: (not item.is_default, item.id),
        )
        assembly = assemblies[0] if assemblies else None
        annotations = sorted(
            assembly.annotations.all() if assembly else [],
            key=lambda item: (not item.is_default, item.id),
        )
        annotation_datasets = [
            value for value in (_annotation_display_value(item) for item in annotations) if value
        ]
        species = accession.species
        rows.append(
            {
                "accession": accession.accession,
                "species_scientific_name": species.scientific_name if species else None,
                "species_common_name": species.common_name if species else None,
                "country": accession.country or None,
                "assembly": _first_display_value(
                    assembly,
                    ("display_name", "assembly_name", "assembly_code", "name"),
                ),
                "annotation_datasets": annotation_datasets,
                "annotation_dataset_count": len(annotation_datasets),
                "annotation": annotation_datasets[0] if annotation_datasets else "",
                "view_count": accession.view_count,
            }
        )

    return rows
