"""Shared serializers for Assembly and Annotation read models."""


def serialize_assembly(assembly, *, include_detail=False):
    """Return the stable Assembly payload shared by read-only services."""
    payload = {
        "id": assembly.id,
        "name": assembly.name,
        "assembly_code": assembly.assembly_code,
        "assembly_name": assembly.assembly_name or assembly.display_name or assembly.name,
        "assembly_accession": assembly.assembly_accession or assembly.standard_id,
        "assembly_level": assembly.assembly_level,
        "display_name": assembly.display_name,
        "standard_id": assembly.standard_id,
        "bio_project": assembly.bio_project,
        "reference": assembly.reference,
        "source_database": assembly.source_database,
        "external_project": assembly.external_project,
        "file_name": assembly.file_name,
        "file_type": assembly.file_type,
        "description": assembly.description,
        "is_default": assembly.is_default,
    }
    if include_detail:
        payload.update({
            "biosample_accession": assembly.biosample_accession,
            "assembly_type": assembly.assembly_type,
            "assembly_method": assembly.assembly_method,
            "sequencing_technology": assembly.sequencing_technology,
            "genome_size": assembly.genome_size,
            "chromosome_count": assembly.chromosome_count,
            "contig_count": assembly.contig_count,
            "n50": assembly.n50,
            "gc_content": assembly.gc_content,
        })
    return payload


def serialize_annotation(annotation, *, assembly=None):
    """Return the stable Annotation payload shared by read-only services."""
    assembly = assembly or annotation.assembly
    return {
        "id": annotation.id,
        "name": annotation.name,
        "annotation_code": annotation.annotation_code,
        "annotation_name": annotation.annotation_name or annotation.display_name or annotation.name,
        "annotation_version": annotation.annotation_version or annotation.release_version,
        "display_name": annotation.display_name,
        "standard_id": annotation.standard_id,
        "source_name": annotation.source_name,
        "release_version": annotation.release_version,
        "source_database": annotation.source_database,
        "external_project": annotation.external_project,
        "file_name": annotation.file_name,
        "file_type": annotation.file_type,
        "description": annotation.description,
        "is_default": annotation.is_default,
        "assembly_id": assembly.id,
        "assembly_name": assembly.display_name or assembly.name,
    }
