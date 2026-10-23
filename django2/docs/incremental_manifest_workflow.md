# Incremental Assembly/Annotation manifest workflow

Use this workflow when real files arrive gradually under `manual_files`.

1. Copy the two TSV templates from `metadata/templates/` into a batch directory.
2. Add one Assembly row per Accession. An Annotation row is optional, but when
   present its `assembly_code` must reference the Assembly manifest.
3. `file_name` is relative to `MANUAL_FILES_DIR`. Names must follow the normal
   rules, for example `genome.MH63.fasta` and `annotation.MH63.gff`.
4. Run the default dry-run:

   ```powershell
   python manage.py import_incremental_hierarchy_manifest `
     --assembly-file metadata/batches/20260922/assembly.tsv `
     --annotation-file metadata/batches/20260922/annotation.tsv `
     --batch-id 20260922-public-import
   ```

5. Review the generated `incremental_hierarchy_batch_*.txt` and `.tsv` reports.
6. Apply the exact same batch only after the dry-run returns `status READY`:

   ```powershell
   python manage.py import_incremental_hierarchy_manifest `
     --assembly-file metadata/batches/20260922/assembly.tsv `
     --annotation-file metadata/batches/20260922/annotation.tsv `
     --batch-id 20260922-public-import `
     --apply
   ```

The command is atomic and idempotent. It validates physical files before any
write, binds files using explicit manifest identities, selects the imported
records as defaults, and only removes safe placeholders for Accessions present
in the current batch. A failed preflight makes no database changes.
