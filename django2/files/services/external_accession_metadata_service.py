"""Stable read models for external-tool accession discovery."""

from files.models import Assembly
from files.services.assembly_visibility import public_assembly_list_queryset


def serialize_external_accession(accession):
    species = accession.species
    return {
        "accession": accession.accession,
        "species": str(species) if species else None,
        "sub_population": accession.sub_population,
        "country": accession.country,
        "region": accession.region,
    }


def list_external_accession_assemblies(accession):
    assemblies = public_assembly_list_queryset(
        Assembly.objects.filter(accession=accession)
    ).order_by("-is_default", "id")
    rows = [
        {
            "assembly_id": assembly.id,
            "assembly_code": assembly.assembly_code,
            "assembly_name": (
                assembly.assembly_name
                or assembly.display_name
                or assembly.name
            ),
            "assembly_accession": (
                assembly.assembly_accession or assembly.standard_id
            ),
            "assembly_level": assembly.assembly_level,
            "is_default": assembly.is_default,
        }
        for assembly in assemblies
    ]
    return {
        "accession": accession.accession,
        "count": len(rows),
        "assemblies": rows,
    }
