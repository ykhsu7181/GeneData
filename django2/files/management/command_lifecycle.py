"""Lifecycle classification for every files Django management command."""

ACTIVE = "active"
RETAIN_AUDIT = "retain_audit"
LEGACY_REPAIR = "legacy_repair"
RETIRE_PENDING_USAGE_CONFIRMATION = "retire_pending_usage_confirmation"


COMMAND_LIFECYCLE = {
    "audit_file_migration": RETAIN_AUDIT,
    "audit_file_relations": ACTIVE,
    "audit_genome_transcriptome_readiness": ACTIVE,
    "audit_legacy_fallback": RETAIN_AUDIT,
    "backfill_assembly_fasta_statistics": ACTIVE,
    "backfill_assembly_from_genome_relations": LEGACY_REPAIR,
    "backfill_genomefile_to_datafile": LEGACY_REPAIR,
    "bind_manual_files": ACTIVE,
    "cleanup_data": RETIRE_PENDING_USAGE_CONFIRMATION,
    "cleanup_placeholder_hierarchy": LEGACY_REPAIR,
    "compare_accession_files": RETAIN_AUDIT,
    "compare_annotation_files": RETAIN_AUDIT,
    "compare_overview_files": RETAIN_AUDIT,
    "generate_legacy_fix_todo": RETAIN_AUDIT,
    "generate_hierarchy_manifests_from_file_list": ACTIVE,
    "import_accession_external_mapping_manifest": ACTIVE,
    "import_accession_hierarchy_metadata": LEGACY_REPAIR,
    "import_accession_manifest": ACTIVE,
    "import_accessions": LEGACY_REPAIR,
    "import_annotation_manifest": ACTIVE,
    "import_assembly_manifest": ACTIVE,
    "import_data_batch": ACTIVE,
    "import_dataset_accession_manifest": ACTIVE,
    "import_dataset_manifest": ACTIVE,
    "import_incremental_hierarchy_manifest": ACTIVE,
    "import_raw_data_manifest": ACTIVE,
    "import_sample_manifest": ACTIVE,
    "link_genomefiles_to_accessions": LEGACY_REPAIR,
    "reconcile_assembly_annotation_context": LEGACY_REPAIR,
    "refresh_dashboard_cache": ACTIVE,
    "quarantine_invalid_manual_files": LEGACY_REPAIR,
    "report_genomefile_archive_status": RETAIN_AUDIT,
    "report_legacy_usage": RETAIN_AUDIT,
    "scan_files": ACTIVE,
    "seed_ir64_demo_hierarchy": RETIRE_PENDING_USAGE_CONFIRMATION,
    "validate_new_file_structure": ACTIVE,
    "validate_hierarchy_manifest_package": ACTIVE,
    "validate_manual_files": ACTIVE,
    "validate_prjeb73710_relationships": RETAIN_AUDIT,
}
