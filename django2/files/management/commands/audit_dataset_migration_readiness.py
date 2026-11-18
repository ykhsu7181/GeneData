from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.management.external_data_command import write_tsv
from files.models import DataFile, Dataset, DatasetAccession, FileRelation


SUMMARY_FIELDS = ("metric", "value")
DATASET_FIELDS = (
    "dataset_id",
    "dataset_code",
    "dataset_type",
    "status",
    "visibility",
    "project_code",
    "species_code",
    "bioproject_accession",
    "version",
    "accession_count",
    "direct_file_count",
    "relation_file_count",
    "shared_file_count",
    "direct_only_file_count",
    "relation_only_file_count",
    "multi_dataset_file_count",
    "issues",
)
ACCESSION_FIELDS = (
    "dataset_code",
    "accession",
    "relation_role",
)
FILE_LINK_FIELDS = (
    "data_file_id",
    "file_code",
    "direct_dataset_code",
    "relation_dataset_codes",
    "invalid_related_ids",
    "classification",
    "issues",
)
DUPLICATE_FIELDS = ("issue", "group_key", "dataset_codes", "count")
REPORT_NAMES = {
    "summary": "dataset_t0_summary.tsv",
    "datasets": "dataset_t0_datasets.tsv",
    "accessions": "dataset_t0_accessions.tsv",
    "file_links": "dataset_t0_file_links.tsv",
    "duplicates": "dataset_t0_duplicates.tsv",
}


class Command(BaseCommand):
    help = "Write a read-only Dataset-to-DataAsset migration readiness audit."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            required=True,
            help="Private directory for deterministic Dataset T0 TSV reports.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        paths = {name: output_dir / filename for name, filename in REPORT_NAMES.items()}
        existing = [path for path in paths.values() if path.exists()]
        if existing:
            raise CommandError(
                "Refusing to overwrite existing Dataset T0 reports: "
                + ", ".join(str(path) for path in existing)
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        with transaction.atomic():
            reports = self.collect_reports()
            transaction.set_rollback(True)

        write_tsv(paths["summary"], SUMMARY_FIELDS, reports["summary"])
        write_tsv(paths["datasets"], DATASET_FIELDS, reports["datasets"])
        write_tsv(paths["accessions"], ACCESSION_FIELDS, reports["accessions"])
        write_tsv(paths["file_links"], FILE_LINK_FIELDS, reports["file_links"])
        write_tsv(paths["duplicates"], DUPLICATE_FIELDS, reports["duplicates"])

        self.stdout.write("mode\tREAD_ONLY")
        for name in ("summary", "datasets", "accessions", "file_links", "duplicates"):
            self.stdout.write(f"{name}\t{len(reports[name])}\t{paths[name]}")

    def collect_reports(self):
        datasets = list(
            Dataset.objects.select_related("project", "species").order_by("id")
        )
        dataset_by_id = {dataset.id: dataset for dataset in datasets}

        accession_links = list(
            DatasetAccession.objects.select_related("dataset", "accession")
            .order_by("dataset__dataset_code", "accession__accession", "id")
        )
        accessions_by_dataset = defaultdict(list)
        role_counts = Counter()
        accession_rows = []
        for link in accession_links:
            accessions_by_dataset[link.dataset_id].append(link)
            role_counts[link.relation_role] += 1
            accession_rows.append(
                {
                    "dataset_code": link.dataset.dataset_code,
                    "accession": link.accession.accession,
                    "relation_role": link.relation_role,
                }
            )

        relation_values = list(
            FileRelation.objects.filter(related_type="dataset")
            .values("file_id", "related_id")
            .order_by("file_id", "related_id", "id")
        )
        relation_ids_by_file = defaultdict(list)
        for relation in relation_values:
            relation_ids_by_file[relation["file_id"]].append(relation["related_id"])

        direct_files_by_dataset = defaultdict(set)
        relation_files_by_dataset = defaultdict(set)
        multi_dataset_files_by_dataset = defaultdict(set)
        file_classifications = Counter()
        file_rows = []
        invalid_relation_count = 0

        data_files = DataFile.objects.values("id", "file_code", "dataset_id").order_by("id")
        for data_file in data_files.iterator():
            file_id = data_file["id"]
            direct_id = data_file["dataset_id"]
            if direct_id is not None:
                direct_files_by_dataset[direct_id].add(file_id)

            valid_relation_ids = set()
            invalid_related_ids = []
            for raw_related_id in relation_ids_by_file.get(file_id, []):
                try:
                    related_id = int(raw_related_id)
                except (TypeError, ValueError):
                    invalid_related_ids.append(str(raw_related_id))
                    continue
                if related_id not in dataset_by_id:
                    invalid_related_ids.append(str(raw_related_id))
                    continue
                valid_relation_ids.add(related_id)
                relation_files_by_dataset[related_id].add(file_id)

            invalid_relation_count += len(invalid_related_ids)
            effective_ids = set(valid_relation_ids)
            if direct_id is not None:
                effective_ids.add(direct_id)

            raw_relations_present = bool(relation_ids_by_file.get(file_id))
            if direct_id is None and not raw_relations_present:
                classification = "datasetless"
            elif direct_id is not None and not raw_relations_present:
                classification = "direct_only"
            elif direct_id is None and valid_relation_ids and not invalid_related_ids:
                classification = "relation_only"
            elif (
                direct_id is not None
                and valid_relation_ids == {direct_id}
                and not invalid_related_ids
            ):
                classification = "aligned"
            else:
                classification = "conflict"
            file_classifications[classification] += 1

            issues = []
            if invalid_related_ids:
                issues.append("invalid_dataset_relation")
            if len(valid_relation_ids) > 1:
                issues.append("multiple_relation_datasets")
            if len(effective_ids) > 1:
                issues.append("multiple_effective_datasets")
            if classification in {"direct_only", "relation_only", "conflict"}:
                issues.append(classification)

            if len(effective_ids) > 1:
                for dataset_id in effective_ids:
                    multi_dataset_files_by_dataset[dataset_id].add(file_id)

            file_rows.append(
                {
                    "data_file_id": file_id,
                    "file_code": data_file["file_code"],
                    "direct_dataset_code": self.dataset_code(dataset_by_id, direct_id),
                    "relation_dataset_codes": ",".join(
                        self.dataset_code(dataset_by_id, dataset_id)
                        for dataset_id in sorted(valid_relation_ids)
                    ),
                    "invalid_related_ids": ",".join(sorted(set(invalid_related_ids))),
                    "classification": classification,
                    "issues": ",".join(issues),
                }
            )

        dataset_rows = []
        status_counts = Counter()
        visibility_counts = Counter()
        type_counts = Counter()
        missing_counts = Counter()
        accession_cardinality = Counter()
        bioproject_groups = defaultdict(list)
        project_version_groups = defaultdict(list)

        for dataset in datasets:
            status_counts[dataset.status] += 1
            visibility_counts[dataset.visibility] += 1
            type_counts[dataset.dataset_type] += 1
            links = accessions_by_dataset[dataset.id]
            if not links:
                accession_cardinality["none"] += 1
            elif len(links) == 1:
                accession_cardinality["one"] += 1
            else:
                accession_cardinality["multiple"] += 1

            issues = []
            for field_name, value in (
                ("project", dataset.project_id),
                ("species", dataset.species_id),
                ("bioproject", (dataset.bioproject_accession or "").strip()),
            ):
                if not value:
                    missing_counts[field_name] += 1
                    issues.append(f"missing_{field_name}")
            if not links:
                issues.append("no_accession")
            elif len(links) > 1:
                issues.append("multiple_accessions")

            bioproject = (dataset.bioproject_accession or "").strip()
            if bioproject:
                bioproject_groups[bioproject.upper()].append(dataset)
            version = (dataset.version or "").strip()
            if dataset.project_id and version:
                key = (dataset.project.project_code, dataset.dataset_type, version)
                project_version_groups[key].append(dataset)

            direct_files = direct_files_by_dataset[dataset.id]
            relation_files = relation_files_by_dataset[dataset.id]
            dataset_rows.append(
                {
                    "dataset_id": dataset.id,
                    "dataset_code": dataset.dataset_code,
                    "dataset_type": dataset.dataset_type,
                    "status": dataset.status,
                    "visibility": dataset.visibility,
                    "project_code": dataset.project.project_code if dataset.project_id else "",
                    "species_code": dataset.species.species_code if dataset.species_id else "",
                    "bioproject_accession": bioproject,
                    "version": version,
                    "accession_count": len(links),
                    "direct_file_count": len(direct_files),
                    "relation_file_count": len(relation_files),
                    "shared_file_count": len(direct_files & relation_files),
                    "direct_only_file_count": len(direct_files - relation_files),
                    "relation_only_file_count": len(relation_files - direct_files),
                    "multi_dataset_file_count": len(multi_dataset_files_by_dataset[dataset.id]),
                    "issues": ",".join(issues),
                }
            )

        duplicate_rows = []
        self.add_duplicate_rows(
            duplicate_rows, "duplicate_bioproject", bioproject_groups
        )
        self.add_duplicate_rows(
            duplicate_rows,
            "duplicate_project_type_version",
            project_version_groups,
        )

        summary = [
            {"metric": "dataset_total", "value": len(datasets)},
            {"metric": "dataset_missing_project", "value": missing_counts["project"]},
            {"metric": "dataset_missing_species", "value": missing_counts["species"]},
            {"metric": "dataset_missing_bioproject", "value": missing_counts["bioproject"]},
            {"metric": "dataset_accessions_none", "value": accession_cardinality["none"]},
            {"metric": "dataset_accessions_one", "value": accession_cardinality["one"]},
            {"metric": "dataset_accessions_multiple", "value": accession_cardinality["multiple"]},
            {"metric": "dataset_accession_link_total", "value": len(accession_links)},
            {"metric": "datafile_total", "value": len(file_rows)},
            {"metric": "dataset_relation_invalid_total", "value": invalid_relation_count},
            {"metric": "duplicate_group_total", "value": len(duplicate_rows)},
        ]
        self.extend_choice_counts(summary, "dataset_status", Dataset.STATUS_CHOICES, status_counts)
        self.extend_choice_counts(
            summary, "dataset_visibility", Dataset.VISIBILITY_CHOICES, visibility_counts
        )
        self.extend_choice_counts(summary, "dataset_type", Dataset.DATASET_TYPE_CHOICES, type_counts)
        self.extend_choice_counts(
            summary,
            "dataset_accession_role",
            DatasetAccession.RELATION_ROLE_CHOICES,
            role_counts,
        )
        for classification in (
            "datasetless",
            "direct_only",
            "relation_only",
            "aligned",
            "conflict",
        ):
            summary.append(
                {
                    "metric": f"datafile_link_{classification}",
                    "value": file_classifications[classification],
                }
            )

        return {
            "summary": summary,
            "datasets": dataset_rows,
            "accessions": accession_rows,
            "file_links": file_rows,
            "duplicates": duplicate_rows,
        }

    @staticmethod
    def dataset_code(dataset_by_id, dataset_id):
        if dataset_id is None:
            return ""
        dataset = dataset_by_id.get(dataset_id)
        return dataset.dataset_code if dataset else ""

    @staticmethod
    def extend_choice_counts(rows, prefix, choices, counts):
        known = set()
        for value, _label in choices:
            known.add(value)
            rows.append({"metric": f"{prefix}:{value}", "value": counts[value]})
        for value in sorted(set(counts) - known):
            rows.append({"metric": f"{prefix}:{value}", "value": counts[value]})

    @staticmethod
    def add_duplicate_rows(rows, issue, groups):
        for key, grouped_datasets in sorted(groups.items(), key=lambda item: str(item[0])):
            if len(grouped_datasets) < 2:
                continue
            group_key = "|".join(key) if isinstance(key, tuple) else str(key)
            codes = sorted(dataset.dataset_code for dataset in grouped_datasets)
            rows.append(
                {
                    "issue": issue,
                    "group_key": group_key,
                    "dataset_codes": ",".join(codes),
                    "count": len(codes),
                }
            )
