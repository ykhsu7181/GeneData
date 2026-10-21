from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.management.external_data_command import (
    add_safe_mode_arguments,
    is_apply_mode,
    make_report_path,
    read_tsv,
    write_tsv,
)
from files.models import Accession, DataFile, Dataset, DatasetAccession, FileRelation
from files.services.external_data_operations import inspect_datafile_readiness


REQUIRED_FIELDS = {
    "dataset_code", "dataset_name", "dataset_type", "accession", "relation_role",
    "file_code", "file_role", "is_primary", "sha256",
}
REPORT_FIELDS = (
    "line", "dataset_code", "accession", "file_code", "file_role", "status", "issues",
)


class Command(BaseCommand):
    help = "Publish public external API Datasets and stable-code relations from a TSV manifest."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--output-dir", default=None)
        add_safe_mode_arguments(parser)

    def handle(self, *args, **options):
        apply_mode = is_apply_mode(options)
        rows = read_tsv(options["manifest"], REQUIRED_FIELDS)
        if not rows:
            raise CommandError("Manifest contains no data rows")
        prepared, report_rows = self._prepare(rows)
        blocked = sum(row["status"] == "blocked" for row in report_rows)
        if apply_mode and not blocked:
            self._apply(prepared, report_rows)
        elif apply_mode:
            for row in report_rows:
                if row["status"] == "ready":
                    row["status"] = "ready_not_applied"

        report_path = make_report_path(options["output_dir"], "external_dataset_publication")
        write_tsv(report_path, REPORT_FIELDS, report_rows)
        self.stdout.write(f"mode\t{'APPLY' if apply_mode else 'DRY_RUN'}")
        self.stdout.write(f"total\t{len(report_rows)}")
        self.stdout.write(f"ready\t{sum(row['status'] == 'ready' for row in report_rows)}")
        self.stdout.write(f"applied\t{sum(row['status'] == 'applied' for row in report_rows)}")
        self.stdout.write(f"blocked\t{blocked}")
        self.stdout.write(f"report\t{report_path}")
        if blocked:
            raise CommandError("Dataset publication blocked; no changes were applied.")

    def _prepare(self, rows):
        prepared = []
        reports = []
        dataset_metadata = defaultdict(set)
        seen_relations = set()
        for line, row in enumerate(rows, start=2):
            issues = []
            dataset_code = row["dataset_code"]
            file_code = row["file_code"]
            dataset_metadata[dataset_code].add(
                (row["dataset_name"], row["dataset_type"])
            )
            if row["dataset_type"] not in {item[0] for item in Dataset.DATASET_TYPE_CHOICES}:
                issues.append("invalid_dataset_type")
            if row["relation_role"] not in {
                item[0] for item in DatasetAccession.RELATION_ROLE_CHOICES
            }:
                issues.append("invalid_relation_role")
            primary = self._parse_boolean(row["is_primary"])
            if primary is None:
                issues.append("invalid_is_primary")
            accession = Accession.objects.filter(accession=row["accession"]).first()
            if accession is None:
                issues.append("accession_not_found")
            existing = Dataset.objects.filter(dataset_code=dataset_code).first()
            data_file = DataFile.objects.filter(file_code=file_code).first()
            if data_file is None:
                issues.append("datafile_not_found")
            else:
                if (data_file.sha256 or "").lower() != row["sha256"].lower():
                    issues.append("sha256_manifest_mismatch")
                readiness = inspect_datafile_readiness(
                    data_file, access_level=DataFile.ACCESS_LEVEL_PUBLIC
                )
                non_policy_issues = set(readiness.issues) - {
                    "no_inherited_access_policy",
                    "dataset_policy_denied",
                    "file_or_dataset_policy_denied",
                    "policy_integrity_error",
                }
                if (
                    non_policy_issues
                    or not self._public_under_proposed_dataset(data_file, existing)
                    or data_file.publication_status != DataFile.PUBLICATION_RELEASED
                    or data_file.published_at is None
                ):
                    issues.append("datafile_not_publicly_ready")
            relation_key = (dataset_code, file_code, row["file_role"])
            if relation_key in seen_relations:
                issues.append("duplicate_file_relation")
            seen_relations.add(relation_key)
            if existing and (
                existing.dataset_name not in (None, "", row["dataset_name"])
                or existing.dataset_type != row["dataset_type"]
            ):
                issues.append("dataset_metadata_conflict")
            if existing and accession:
                accession_link = DatasetAccession.objects.filter(
                    dataset=existing, accession=accession
                ).first()
                if accession_link and accession_link.relation_role != row["relation_role"]:
                    issues.append("dataset_accession_role_conflict")
            if existing and data_file and primary is not None:
                file_relation = FileRelation.objects.filter(
                    file=data_file,
                    related_type="dataset",
                    related_id=str(existing.id),
                    file_role=row["file_role"],
                ).first()
                if file_relation and file_relation.is_primary != primary:
                    issues.append("dataset_file_primary_conflict")
            report = {
                "line": line,
                "dataset_code": dataset_code,
                "accession": row["accession"],
                "file_code": file_code,
                "file_role": row["file_role"],
                "status": "blocked" if issues else "ready",
                "issues": ",".join(dict.fromkeys(issues)),
            }
            reports.append(report)
            if not issues:
                prepared.append((row, accession, data_file, primary, report))
        for dataset_code, values in dataset_metadata.items():
            if len(values) <= 1:
                continue
            for report in reports:
                if report["dataset_code"] == dataset_code:
                    report["status"] = "blocked"
                    report["issues"] = ",".join(filter(None, [report["issues"], "dataset_metadata_inconsistent"]))
            prepared = [item for item in prepared if item[0]["dataset_code"] != dataset_code]
        return prepared, reports

    @transaction.atomic
    def _apply(self, prepared, report_rows):
        datasets = {}
        for row, accession, data_file, primary, report in prepared:
            dataset = datasets.get(row["dataset_code"])
            if dataset is None:
                dataset, _created = Dataset.objects.get_or_create(
                    dataset_code=row["dataset_code"],
                    defaults={
                        "dataset_name": row["dataset_name"],
                        "dataset_type": row["dataset_type"],
                        "species": accession.species,
                        "visibility": "public",
                        "status": "released",
                    },
                )
                update_fields = []
                if not dataset.dataset_name:
                    dataset.dataset_name = row["dataset_name"]
                    update_fields.append("dataset_name")
                if dataset.visibility != "public":
                    dataset.visibility = "public"
                    update_fields.append("visibility")
                if dataset.status != "released":
                    dataset.status = "released"
                    update_fields.append("status")
                if update_fields:
                    dataset.save(update_fields=[*update_fields, "updated_at"])
                datasets[row["dataset_code"]] = dataset
            DatasetAccession.objects.get_or_create(
                dataset=dataset,
                accession=accession,
                defaults={"relation_role": row["relation_role"], "source": "external_api_manifest"},
            )
            relation, created = FileRelation.objects.get_or_create(
                file=data_file,
                related_type="dataset",
                related_id=str(dataset.id),
                file_role=row["file_role"],
                defaults={
                    "related_code": dataset.dataset_code,
                    "is_primary": primary,
                    "description": "External Data API dataset publication manifest",
                },
            )
            if not created and relation.is_primary != primary:
                raise CommandError(
                    f"Existing relation primary flag conflicts: {dataset.dataset_code}/{data_file.file_code}"
                )
            report["status"] = "applied"

    @staticmethod
    def _parse_boolean(value):
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
        return None

    @staticmethod
    def _public_under_proposed_dataset(data_file, target_dataset):
        if data_file.access_level not in {
            DataFile.ACCESS_LEVEL_INHERITED,
            DataFile.ACCESS_LEVEL_PUBLIC,
        }:
            return False
        dataset_ids = set()
        if data_file.dataset_id:
            dataset_ids.add(data_file.dataset_id)
        for value in data_file.relations.filter(related_type="dataset").values_list(
            "related_id", flat=True
        ):
            try:
                dataset_ids.add(int(value))
            except (TypeError, ValueError):
                return False
        target_id = target_dataset.id if target_dataset else None
        other_ids = dataset_ids - ({target_id} if target_id else set())
        other_datasets = list(Dataset.objects.filter(id__in=other_ids))
        if len(other_datasets) != len(other_ids):
            return False
        return all(
            dataset.visibility == "public" and dataset.status == "released"
            for dataset in other_datasets
        )
