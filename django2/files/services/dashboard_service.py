from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum

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

RAW_DATA_ROLES = [
    "raw_data",
    "raw",
    "fastq",
    "wgs",
    "resequencing",
    "rnaseq_raw",
]


def _normalize_label(value, fallback="Unknown"):
    value = (value or "").strip()
    return value or fallback


def _get_species_display_name(species):
    if not species:
        return "Unknown"
    return (
        species.chinese_name
        or species.common_name
        or species.scientific_name
        or species.species_code
        or "Unknown"
    )


def _sum_file_size(file_ids):
    if not file_ids:
        return 0
    total = DataFile.objects.filter(id__in=file_ids).aggregate(total=Sum("file_size"))["total"]
    return int(total or 0)


def _file_ids_for_roles(roles):
    return list(
        FileRelation.objects.filter(file_role__in=roles)
        .order_by()
        .values_list("file_id", flat=True)
        .distinct()
    )


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
        "resource_summary": _build_resource_summary(related_datafile_ids, total_size),
        "recent_updates": _build_recent_updates(),
        "geo_distribution": _build_geo_distribution(),
        "hot_keywords": _build_hot_keywords(),
    }
    return payload


def _resource_item(key, title, count, unit, route, *, query=None, status="normal", icon="database", count_display=None):
    return {
        "key": key,
        "title": title,
        "count": count,
        "count_display": count_display if count_display is not None else str(count),
        "unit": unit,
        "route": route,
        "query": query or {},
        "status": status,
        "icon": icon,
    }


def _build_resource_summary(related_datafile_ids, total_size):
    raw_file_count = len(_file_ids_for_roles(RAW_DATA_ROLES))
    transcriptome_count = Dataset.objects.filter(dataset_type="transcriptome").count()
    population_count = Dataset.objects.filter(dataset_type="population_genetics").count()

    return [
        _resource_item(
            "raw_data",
            "原始数据",
            raw_file_count,
            "文件数",
            "/raw-data",
            icon="raw",
        ),
        _resource_item(
            "genome",
            "基因组",
            Assembly.objects.count(),
            "组装数",
            "/genome-card",
            icon="genome",
        ),
        _resource_item(
            "annotation",
            "注释",
            Annotation.objects.count(),
            "记录数",
            "/annotation",
            icon="annotation",
        ),
        _resource_item(
            "transcriptome",
            "转录组",
            transcriptome_count,
            "数据集",
            "/transcriptome-overview",
            query={"dataset_type": "transcriptome"},
            icon="transcriptome",
        ),
        _resource_item(
            "population_genetics",
            "群体遗传",
            population_count,
            "数据集",
            "/data-overview",
            query={"dataset_type": "population_genetics"},
            status="coming_soon" if population_count == 0 else "normal",
            icon="population",
        ),
        _resource_item(
            "download",
            "下载",
            total_size,
            "可用数据量",
            "/data-overview",
            query={"download_mode": "by_type"},
            icon="download",
            count_display=_format_bytes(total_size),
        ),
    ]


def _build_recent_updates(limit=4):
    updates = []
    for dataset in Dataset.objects.order_by("-created_at", "-id")[:limit]:
        updates.append(
            {
                "title": f"新增数据集 {dataset.dataset_name or dataset.dataset_code}",
                "date": dataset.created_at.date().isoformat(),
                "type": "dataset",
                "route": "/data-overview",
                "query": {"dataset_type": dataset.dataset_type},
                "created_at": dataset.created_at,
            }
        )

    for data_file in DataFile.objects.filter(relations__isnull=False).distinct().order_by("-created_at", "-id")[:limit]:
        updates.append(
            {
                "title": f"新增文件 {data_file.file_name}",
                "date": data_file.created_at.date().isoformat(),
                "type": "datafile",
                "route": "/data-overview",
                "query": {},
                "created_at": data_file.created_at,
            }
        )

    updates.sort(key=lambda item: item["created_at"], reverse=True)
    return [
        {key: value for key, value in item.items() if key != "created_at"}
        for item in updates[:limit]
    ]


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

    unassigned_card = _build_unassigned_species_card()
    if unassigned_card:
        cards.append(unassigned_card)
    return cards


def _build_unassigned_species_card():
    unassigned_accessions = Accession.objects.filter(species__isnull=True)
    accession_count = unassigned_accessions.count()
    if accession_count == 0:
        return None

    accession_ids = [str(value) for value in unassigned_accessions.values_list("id", flat=True)]
    file_ids = list(
        FileRelation.objects.filter(related_type="accession", related_id__in=accession_ids)
        .order_by()
        .values_list("file_id", flat=True)
        .distinct()
    )
    sample_count = Sample.objects.filter(species__isnull=True).count()
    dataset_count = Dataset.objects.filter(species__isnull=True).count()
    total_size = _sum_file_size(file_ids)

    return {
        "species_id": "unassigned",
        "species_code": "UNASSIGNED",
        "name_cn": "未归属物种",
        "latin_name": "Unassigned accessions",
        "accession_count": accession_count,
        "sample_count": sample_count,
        "dataset_count": dataset_count,
        "datafile_count": len(file_ids),
        "total_size": total_size,
        "total_size_display": _format_bytes(total_size),
        "accent_color": SPECIES_CARD_COLORS[len(SPECIES_CARD_COLORS) - 1],
        "cover_image": None,
    }


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
    dataset_counts = {
        (group["dataset_type"] or "other"): group["dataset_count"]
        for group in Dataset.objects.values("dataset_type").annotate(dataset_count=Count("id"))
    }
    file_groups = defaultdict(lambda: {"file_ids": set(), "total_size": 0})
    for data_file in DataFile.objects.filter(dataset__isnull=False).values(
        "id", "file_size", "dataset__dataset_type"
    ):
        dataset_type = data_file["dataset__dataset_type"] or "other"
        bucket = file_groups[dataset_type]
        bucket["file_ids"].add(data_file["id"])
        bucket["total_size"] += int(data_file["file_size"] or 0)

    rows = []
    for dataset_type, dataset_count in sorted(dataset_counts.items()):
        bucket = file_groups.get(dataset_type, {"file_ids": set(), "total_size": 0})
        rows.append(
            {
                "dataset_type": dataset_type,
                "dataset_count": dataset_count,
                "datafile_count": len(bucket["file_ids"]),
                "total_size": bucket["total_size"],
                "total_size_display": _format_bytes(bucket["total_size"]),
            }
        )
    return rows


def _build_file_role_summary():
    grouped = defaultdict(lambda: {"file_ids": set(), "total_size": 0})
    seen_role_files = set()
    for relation in FileRelation.objects.select_related("file").filter(file__isnull=False).only(
        "file_role", "file_id", "file__file_size"
    ):
        file_role = relation.file_role or "other"
        dedupe_key = (file_role, relation.file_id)
        if dedupe_key in seen_role_files:
            continue
        seen_role_files.add(dedupe_key)
        grouped[file_role]["file_ids"].add(relation.file_id)
        grouped[file_role]["total_size"] += int(relation.file.file_size or 0)

    rows = []
    for file_role, bucket in grouped.items():
        rows.append(
            {
                "file_role": file_role,
                "datafile_count": len(bucket["file_ids"]),
                "total_size": bucket["total_size"],
                "total_size_display": _format_bytes(bucket["total_size"]),
            }
        )
    rows.sort(key=lambda item: (-item["datafile_count"], item["file_role"]))
    return rows


def _build_geo_distribution():
    grouped = {}
    accession_queryset = Accession.objects.filter(
        longitude__isnull=False,
        latitude__isnull=False,
    ).select_related("species").order_by("accession")
    accession_ids = list(accession_queryset.values_list("id", flat=True))
    species_ids = {
        species_id
        for species_id in accession_queryset.values_list("species_id", flat=True)
        if species_id
    }
    sample_ids_by_accession = defaultdict(set)
    for sample in Sample.objects.filter(accession_id__in=accession_ids).values("id", "accession_id"):
        sample_ids_by_accession[sample["accession_id"]].add(sample["id"])

    dataset_ids_by_species = defaultdict(set)
    for dataset in Dataset.objects.filter(species_id__in=species_ids).values("id", "species_id"):
        dataset_ids_by_species[dataset["species_id"]].add(dataset["id"])

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
                "accession_names": set(),
                "sample_ids": set(),
                "dataset_ids": set(),
                "species_names": set(),
            }
        bucket = grouped[key]
        bucket["accession_ids"].add(accession.id)
        bucket["accession_names"].add(accession.accession)
        bucket["sample_ids"].update(sample_ids_by_accession.get(accession.id, set()))
        if accession.species_id:
            bucket["species_names"].add(_get_species_display_name(accession.species))
            bucket["dataset_ids"].update(dataset_ids_by_species.get(accession.species_id, set()))

    rows = []
    for bucket in grouped.values():
        rows.append(
            {
                "region": bucket["region"],
                "latitude": bucket["latitude"],
                "longitude": bucket["longitude"],
                "accession_count": len(bucket["accession_ids"]),
                "accession_names": sorted(bucket["accession_names"]),
                "sample_count": len(bucket["sample_ids"]),
                "dataset_count": len(bucket["dataset_ids"]),
                "species_names": sorted(bucket["species_names"]),
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
