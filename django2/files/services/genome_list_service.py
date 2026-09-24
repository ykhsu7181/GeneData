import json

from files.models import Accession, Assembly, FileRelation, Species
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.data_overview_service import datafile_download_url, file_role_display, format_size


GENOME_FILE_ROLES = {
    "genome",
    "genome_fasta",
    "genome_index",
    "fasta",
    "fa",
    "fai",
    "chrom_sizes",
    "statistics",
    "checksum",
}


def _param(params, key, default=""):
    value = params.get(key, default)
    return value.strip() if isinstance(value, str) else value


def _page_params(params):
    page = int(params.get("page", 1) or 1)
    page_size = int(params.get("page_size", 20) or 20)
    return max(page, 1), max(page_size, 1)


def _metadata(assembly):
    raw = assembly.description or ""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _metadata_value(assembly, *keys):
    metadata = _metadata(assembly)
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return None


def _species_name(species):
    if not species:
        return "未归属物种"
    return species.chinese_name or species.common_name or species.scientific_name or species.species_code


def _latin_name(species):
    if not species:
        return "-"
    return species.scientific_name or species.common_name or species.species_code or "-"


def _assembly_level(assembly):
    return _metadata_value(assembly, "assembly_level", "level") or "-"


def _chromosome_count(assembly):
    return _metadata_value(assembly, "chromosome_count", "chromosome_number") or "-"


def _genome_size_display(assembly, primary_file):
    metadata_size = _metadata_value(assembly, "genome_size_display", "genome_size")
    if metadata_size:
        return str(metadata_size)
    if primary_file and primary_file.file_size:
        return format_size(primary_file.file_size)
    return "-"


def _file_type_display(data_file):
    file_type = data_file.file_type
    if not file_type:
        return "-"
    return file_type.name or file_type.format or file_type.extension or "-"


def _genome_relation_queryset(*, assembly=None, accession=None, include_accession=False):
    related_filters = []
    if assembly:
        related_filters.append(("assembly", str(assembly.id)))
    if include_accession and accession:
        related_filters.append(("accession", str(accession.id)))

    if not related_filters:
        return FileRelation.objects.none()

    queryset = FileRelation.objects.select_related("file", "file__file_type").filter(
        file_role__in=GENOME_FILE_ROLES,
    )
    relation_query = None
    from django.db.models import Q

    for related_type, related_id in related_filters:
        clause = Q(related_type=related_type, related_id=related_id)
        relation_query = clause if relation_query is None else relation_query | clause
    return queryset.filter(relation_query).order_by("-is_primary", "file_role", "id")


def _dedupe_relations(relations):
    seen = set()
    deduped = []
    for relation in relations:
        if relation.file_id in seen:
            continue
        seen.add(relation.file_id)
        deduped.append(relation)
    return deduped


def _primary_relation(relations):
    for relation in relations:
        if relation.is_primary:
            return relation
    return relations[0] if relations else None


def _file_payload(relation):
    data_file = relation.file
    return {
        "file_id": data_file.id,
        "file_code": data_file.file_code,
        "file_name": data_file.file_name,
        "file_path": data_file.file_path,
        "file_role": relation.file_role,
        "file_role_display": file_role_display(relation.file_role),
        "file_type": _file_type_display(data_file),
        "file_size": data_file.file_size,
        "file_size_display": format_size(data_file.file_size),
        "md5": data_file.md5 or "-",
        "related_type": relation.related_type,
        "related_id": relation.related_id,
        "related_code": relation.related_code or "",
        "is_primary": relation.is_primary,
        "download_url": datafile_download_url(data_file.id),
    }


def _assembly_row(assembly):
    accession = assembly.accession
    species = accession.species if accession else None
    # The Genome list is an Assembly view.  Do not expose placeholder/default
    # assemblies unless they have their own assembly-level genome relation.
    relations = _dedupe_relations(_genome_relation_queryset(assembly=assembly))
    primary = _primary_relation(relations)
    primary_file = primary.file if primary else None
    return {
        "species_id": species.id if species else None,
        "species_name": _species_name(species),
        "latin_name": _latin_name(species),
        "accession_id": accession.id if accession else None,
        "accession": accession.accession if accession else "-",
        "assembly_id": assembly.id,
        "assembly_name": assembly.display_name or assembly.name or "-",
        "assembly_code": assembly.standard_id or assembly.name or "-",
        "assembly_level": _assembly_level(assembly),
        "chromosome_count": _chromosome_count(assembly),
        "genome_size_display": _genome_size_display(assembly, primary_file),
        "file_count": len(relations),
        "primary_file_id": primary_file.id if primary_file else None,
        "download_url": datafile_download_url(primary_file.id) if primary_file else None,
    }


def build_genome_list_payload(params):
    page, page_size = _page_params(params)
    species_id = _param(params, "species_id")
    accession_id = _param(params, "accession_id")
    assembly_level = _param(params, "assembly_level")

    assemblies = visible_assembly_queryset(
        Assembly.objects.select_related("accession", "accession__species").all()
    )
    if species_id:
        assemblies = assemblies.filter(accession__species_id=species_id)
    if accession_id:
        assemblies = assemblies.filter(accession_id=accession_id)

    rows = [
        row
        for row in (_assembly_row(assembly) for assembly in assemblies)
        if row["primary_file_id"] is not None
    ]
    if assembly_level:
        rows = [row for row in rows if row["assembly_level"] == assembly_level]

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "results": rows[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        "filters": {
            "species": [
                {
                    "id": species.id,
                    "label": _species_name(species),
                    "latin_name": _latin_name(species),
                }
                for species in Species.objects.all().order_by("species_code")
            ],
            "accessions": [
                {
                    "id": accession.id,
                    "label": accession.accession,
                    "species_id": accession.species_id,
                }
                for accession in Accession.objects.all().order_by("accession")
            ],
            "assembly_levels": ["Chromosome", "Scaffold", "Contig"],
        },
    }


def build_genome_files_payload(params):
    assembly_id = _param(params, "assembly_id")
    accession_id = _param(params, "accession_id")

    assembly = None
    accession = None
    if assembly_id:
        assembly = Assembly.objects.select_related("accession", "accession__species").filter(id=assembly_id).first()
        accession = assembly.accession if assembly else None
    elif accession_id:
        accession = Accession.objects.select_related("species").filter(id=accession_id).first()

    relations = _dedupe_relations(_genome_relation_queryset(assembly=assembly, accession=accession))
    assembly_name = assembly.display_name or assembly.name if assembly else "-"
    return {
        "assembly_id": assembly.id if assembly else None,
        "assembly_name": assembly_name,
        "accession_id": accession.id if accession else None,
        "accession": accession.accession if accession else "-",
        "files": [_file_payload(relation) for relation in relations],
    }
