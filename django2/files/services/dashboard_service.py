from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q

from files.models import Accession, Annotation, Assembly, DataFile, Dataset, FileRelation, Sample, Species


DEFAULT_HOT_KEYWORDS = [
    {"label": "Accession", "type": "module", "target": "/accession-card"},
    {"label": "Genome", "type": "module", "target": "/genome-card"},
    {"label": "Annotation", "type": "module", "target": "/annotation"},
    {"label": "Transcriptome", "type": "module", "target": "/transcriptome-overview"},
]

SPECIES_CARD_COLORS = [
    "#1d4ed8",
    "#0f766e",
    "#b45309",
    "#be123c",
    "#4338ca",
    "#15803d",
]


def _normalize_label(value, fallback="Unknown"):
    value = (value or "").strip()
    return value or fallback


def _sum_file_size(file_ids):
    if not file_ids:
        return 0
    total = 0
    for file_size in DataFile.objects.filter(id__in=file_ids).values_list("file_size", flat=True):
        total += int(file_size or 0)
    return total


def _format_bytes(num_bytes):
    size = Decimal(num_bytes or 0)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= Decimal(1024)
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size.quantize(Decimal('0.01'))} {units[unit_index]}"


def _related_datafile_ids():
    return list(
        DataFile.objects.filter(relations__isnull=False)
        .order_by()
        .distinct()
        .values_list("id", flat=True)
    )


def _collect_species_file_ids(species):
    accession_ids = [str(value) for value in species.accessions.values_list("id", flat=True)]
    sample_ids = [str(value) for value in species.samples.values_list("id", flat=True)]
    dataset_ids = [str(value) for value in species.datasets.values_list("id", flat=True)]
    assembly_ids = [
        str(value)
        for value in Assembly.objects.filter(accession__species=species).values_list("id", flat=True)
    ]
    annotation_ids = [
        str(value)
        for value in Annotation.objects.filter(assembly__accession__species=species).values_list("id", flat=True)
    ]

    relation_filter = Q()
    if accession_ids:
        relation_filter |= Q(related_type="accession", related_id__in=accession_ids)
    if sample_ids:
        relation_filter |= Q(related_type="sample", related_id__in=sample_ids)
    if dataset_ids:
        relation_filter |= Q(related_type="dataset", related_id__in=dataset_ids)
    if assembly_ids:
        relation_filter |= Q(related_type="assembly", related_id__in=assembly_ids)
    if annotation_ids:
        relation_filter |= Q(related_type="annotation", related_id__in=annotation_ids)

    if not relation_filter:
        return []

    return list(
        FileRelation.objects.filter(relation_filter)
        .order_by()
        .values_list("file_id", flat=True)
        .distinct()
    )


def build_dashboard_payload():
    related_datafile_ids = _related_datafile_ids()
    total_size = _sum_file_size(related_datafile_ids)

    payload = {
        "summary": {
            "species_count": Species.objects.count(),
            "accession_count": Accession.objects.count(),
            "sample_count": Sample.objects.count(),
            "dataset_count": Dataset.objects.count(),
            "datafile_count": len(related_datafile_ids),
            "total_size": total_size,
            "total_size_display": _format_bytes(total_size),
        },
        "species_cards": _build_species_cards(),
        "sub_population_distribution": _build_sub_population_distribution(),
        "xi_distribution": _build_xi_distribution(),
        "dataset_type_summary": _build_dataset_type_summary(),
        "file_role_summary": _build_file_role_summary(),
        "geo_distribution": _build_geo_distribution(),
        "hot_keywords": _build_hot_keywords(),
    }
    return payload


def _build_species_cards():
    cards = []
    species_list = list(
        Species.objects.all()
        .annotate(
            accession_count=Count("accessions", distinct=True),
            sample_count=Count("samples", distinct=True),
            dataset_count=Count("datasets", distinct=True),
        )
        .order_by("-accession_count", "species_code")
    )

    for index, species in enumerate(species_list):
        file_ids = _collect_species_file_ids(species)
        total_size = _sum_file_size(file_ids)
        cards.append(
            {
                "species_id": species.id,
                "species_code": species.species_code,
                "name_cn": species.chinese_name or species.common_name or species.species_code,
                "latin_name": species.scientific_name or species.common_name or species.species_code,
                "accession_count": species.accession_count,
                "sample_count": species.sample_count,
                "dataset_count": species.dataset_count,
                "datafile_count": len(file_ids),
                "total_size": total_size,
                "total_size_display": _format_bytes(total_size),
                "accent_color": SPECIES_CARD_COLORS[index % len(SPECIES_CARD_COLORS)],
                "cover_image": None,
            }
        )
    return cards


def _build_sub_population_distribution():
    total_accessions = Accession.objects.count() or 1
    grouped = defaultdict(int)
    for sub_population in Accession.objects.values_list("sub_population", flat=True):
        grouped[_normalize_label(sub_population)] += 1

    rows = []
    for name, accession_count in grouped.items():
        rows.append(
            {
                "name": name,
                "accession_count": accession_count,
                "percentage": round((accession_count / total_accessions) * 100, 2),
            }
        )
    rows.sort(key=lambda item: (-item["accession_count"], item["name"]))
    return rows


def _build_xi_distribution():
    grouped = defaultdict(int)
    queryset = Accession.objects.exclude(genetic_stock_id__isnull=True).exclude(genetic_stock_id="")
    for accession in queryset:
        grouped[accession.genetic_stock_id.strip()] += 1

    rows = [
        {"name": name, "accession_count": accession_count}
        for name, accession_count in grouped.items()
    ]
    rows.sort(key=lambda item: (-item["accession_count"], item["name"]))
    return rows[:10]


def _build_dataset_type_summary():
    rows = []
    dataset_groups = (
        Dataset.objects.values("dataset_type")
        .annotate(dataset_count=Count("id"))
        .order_by("dataset_type")
    )

    for group in dataset_groups:
        dataset_type = group["dataset_type"] or "other"
        data_files = DataFile.objects.filter(dataset__dataset_type=dataset_type)
        file_ids = list(data_files.values_list("id", flat=True))
        total_size = _sum_file_size(file_ids)
        rows.append(
            {
                "dataset_type": dataset_type,
                "dataset_count": group["dataset_count"],
                "datafile_count": len(file_ids),
                "total_size": total_size,
                "total_size_display": _format_bytes(total_size),
            }
        )
    return rows


def _build_file_role_summary():
    rows = []
    grouped = (
        FileRelation.objects.values("file_role")
        .annotate(datafile_count=Count("file_id", distinct=True))
        .order_by("file_role")
    )
    for group in grouped:
        file_role = group["file_role"] or "other"
        file_ids = list(
            FileRelation.objects.filter(file_role=file_role)
            .order_by()
            .values_list("file_id", flat=True)
            .distinct()
        )
        total_size = _sum_file_size(file_ids)
        rows.append(
            {
                "file_role": file_role,
                "datafile_count": len(file_ids),
                "total_size": total_size,
                "total_size_display": _format_bytes(total_size),
            }
        )
    rows.sort(key=lambda item: (-item["datafile_count"], item["file_role"]))
    return rows


def _build_geo_distribution():
    grouped = {}
    accession_queryset = Accession.objects.filter(
        longitude__isnull=False,
        latitude__isnull=False,
    ).order_by("accession")

    for accession in accession_queryset:
        key = (
            _normalize_label(accession.region, fallback=_normalize_label(accession.country, fallback="Unknown")),
            float(accession.latitude),
            float(accession.longitude),
        )
        if key not in grouped:
            grouped[key] = {
                "region": key[0],
                "latitude": key[1],
                "longitude": key[2],
                "accession_ids": set(),
                "sample_ids": set(),
                "dataset_ids": set(),
            }
        bucket = grouped[key]
        bucket["accession_ids"].add(accession.id)
        bucket["sample_ids"].update(accession.samples.values_list("id", flat=True))
        if accession.species_id:
            bucket["dataset_ids"].update(
                Dataset.objects.filter(species_id=accession.species_id).values_list("id", flat=True)
            )

    rows = []
    for bucket in grouped.values():
        rows.append(
            {
                "region": bucket["region"],
                "latitude": bucket["latitude"],
                "longitude": bucket["longitude"],
                "accession_count": len(bucket["accession_ids"]),
                "sample_count": len(bucket["sample_ids"]),
                "dataset_count": len(bucket["dataset_ids"]),
            }
        )
    rows.sort(key=lambda item: (-item["accession_count"], item["region"]))
    return rows


def _build_hot_keywords():
    keywords = list(DEFAULT_HOT_KEYWORDS)
    for species in Species.objects.order_by("species_code")[:4]:
        keywords.append(
            {
                "label": species.chinese_name or species.scientific_name or species.species_code,
                "type": "species",
                "target": species.species_code,
            }
        )
    return keywords
