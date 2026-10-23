# Phase E verified checksum import

This procedure imports SHA-256 values already produced by the production
read-only audit. It does not hash the warehouse again.

## Fixed evidence

- Full validation report SHA-256:
  `1164c6cafa1a8e88094bb7aabf7edc79cb6230e5433dc121f59c9cfe765fa217`
- Transcriptome exception report SHA-256:
  `b81a0ececa804cbe18d980133efb159d32020c8e9d43fa4a09c1f6d7e9a52913`
- Production-ready selection SHA-256:
  `d114c9c017bf3859f0ef867e8f49cb7f73ef0a346752b16f70f9854276e2be49`
- Validation start cutoff: `2026-10-22T15:21:19+08:00`

The ready selection contains 2240 files. The two confirmed empty BED files are
not selected. The exception report contains the 96 transcriptome archives that
passed a second tar-header validation. The original validator routed the
`tar.gz` extension through the gzip-text branch; the corrected validator routes
it through tar structural validation and treats header names as byte-preserving
Latin-1 because filename semantics are not part of this check.

If operators choose to move the two empty files into the recoverable
quarantine, they must first run
`quarantine_invalid_manual_files --only-empty --dry-run` and confirm exactly
two candidates. Apply is optional; exclusion from the ready and publication
manifests is sufficient to keep them closed.

## Dry-run

Run this after migrations and the 2240-row hierarchy registration apply:

```bash
python manage.py import_verified_datafile_checksums \
  --settings=filemanager.settings_production \
  --audit-report=/path/to/validate_manual_files_20261022_171654.tsv \
  --audit-report-sha256=1164c6cafa1a8e88094bb7aabf7edc79cb6230e5433dc121f59c9cfe765fa217 \
  --selection-manifest=/path/to/files.registration.ready.tsv \
  --selection-manifest-sha256=d114c9c017bf3859f0ef867e8f49cb7f73ef0a346752b16f70f9854276e2be49 \
  --exception-report=/path/to/transcriptome_quick_validation_20261023_091407.tsv \
  --exception-report-sha256=b81a0ececa804cbe18d980133efb159d32020c8e9d43fa4a09c1f6d7e9a52913 \
  --audit-started-at=2026-10-22T15:21:19+08:00 \
  --output-dir=/path/to/audit-output \
  --dry-run
```

Required gate:

```text
total	2240
ready	2240
blocked	0
```

## Apply

Only after the dry-run report is retained and `blocked=0`, repeat the same
command with `--apply`. Required gate:

```text
total	2240
applied	2240
blocked	0
```

If any selected file has changed size or has a modification time after the
audit began,
the command blocks the entire apply. If a DataFile already has a different
SHA-256, it also blocks rather than overwriting it.
