# External Data API production publication manifests

These manifests use stable codes only. Never copy development database primary keys into production commands.

- `datafile_publication.ir64.tsv` is consumed by `publish_datafiles`.
- `dataset_publication.ir64.tsv` is consumed by `publish_external_datasets`.
- Files ending in `.template.tsv` contain headers only and are the starting point for later approved materials.

Run every command without `--apply` first and retain its TSV report:

```bash
python manage.py publish_datafiles \
  --manifest metadata/external_api_release_template/datafile_publication.ir64.tsv \
  --output-dir /home/labuser/rdcheng/gd/audit_reports/external_api/canary

python manage.py publish_external_datasets \
  --manifest metadata/external_api_release_template/dataset_publication.ir64.tsv \
  --output-dir /home/labuser/rdcheng/gd/audit_reports/external_api/canary

python manage.py audit_external_api_readiness \
  --output-dir /home/labuser/rdcheng/gd/audit_reports/external_api/canary/readiness \
  --require-file FILE000013 --require-file FAI_14 --require-file FILE000001 \
  --require-dataset DS_IR64_REFERENCE_V1 --require-assembly ASM_IR64
```

Only after the dry-run reports have zero blockers may the first two commands be repeated with their required operator arguments and `--apply`. A production SHA-256 mismatch is a stop condition; do not edit a checksum merely to make the gate pass.
