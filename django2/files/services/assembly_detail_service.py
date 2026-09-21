"""Read-only query helpers for the Assembly detail page."""

from urllib.parse import quote

from files.models import Assembly
from files.services.file_relation_service import get_primary_genome_file_for_assembly
from files.services.resource_serializers import serialize_annotation, serialize_assembly


def get_assembly_detail(assembly_id):
    assembly = (
        Assembly.objects
        .select_related("accession", "accession__species")
        .get(id=assembly_id)
    )
    accession = assembly.accession
    species = accession.species

    annotations = assembly.annotations.all().order_by("-is_default", "name", "id")
    related_assemblies = accession.assemblies.all().order_by("-is_default", "name", "id")
    primary_genome_file = get_primary_genome_file_for_assembly(assembly.id)

    assembly_payload = serialize_assembly(assembly, include_detail=True)
    assembly_payload["accession"] = accession.accession

    return {
        "assembly": assembly_payload,
        "species": {
            "id": species.id,
            "species_code": species.species_code,
            "scientific_name": species.scientific_name,
            "chinese_name": species.chinese_name,
            "common_name": species.common_name,
        } if species else None,
        "sub_population": accession.sub_population,
        "statistics": {
            "genome_size": assembly.genome_size,
            "n50": assembly.n50,
            "gc_content": assembly.gc_content,
            "at_content": assembly.at_content,
            "n_count": assembly.n_count,
            "n_percentage": assembly.n_percentage,
            "chromosome_count": assembly.chromosome_count,
            "sequence_count": assembly.sequence_count,
            "sequence_md5": assembly.sequence_md5,
            "gap_count": assembly.gap_count,
            "assembly_level": assembly.assembly_level,
        },
        "annotations": [
            serialize_annotation(annotation, assembly=assembly)
            for annotation in annotations
        ],
        "related_assemblies": [
            serialize_assembly(item)
            for item in related_assemblies
        ],
        "genome_download_url": (
            f"/gd/api/files/data-files/{primary_genome_file['file_id']}/download/"
            if primary_genome_file else None
        ),
        "related_files_url": (
            f"/gd/api/files/accessions/{quote(accession.accession, safe='')}/files/"
        ),
    }
