from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from files.management.external_data_command import write_tsv
from files.models import (
    Accession,
    Annotation,
    Assembly,
    DataFile,
    Dataset,
    DatasetAccession,
    FileRelation,
    Sample,
)
from files.services.data_overview_service import categorize_file_role


SUMMARY_FIELDS = ("metric", "value")
FILE_FIELDS = (
    "data_file_id",
    "file_code",
    "direct_dataset_code",
    "current_dataset_codes",
    "relation_types",
    "file_roles",
    "role_categories",
    "accession_codes",
    "accession_dataset_candidates",
    "type_compatible_candidates",
    "classification",
    "issues",
)
RELATION_FIELDS = (
    "relation_id",
    "data_file_id",
    "file_code",
    "related_type",
    "related_id",
    "file_role",
    "role_category",
    "accession_codes",
    "resolution",
    "issues",
)
REPORT_NAMES = {
    "summary": "datafile_t1_summary.tsv",
    "files": "datafile_t1_files.tsv",
    "relations": "datafile_t1_relations.tsv",
}

# These are deliberately conservative audit hints, not migration rules. Categories
# without an exact Dataset type equivalent remain for manual semantic review.
CATEGORY_TO_DATASET_TYPE = {
    "genome": "genome",
    "annotation": "annotation",
    "transcriptome": "transcriptome",
    "hic": "hic",
}
RESOLVED_RELATION_TYPES = {"accession", "assembly", "annotation", "dataset", "sample"}


class Command(BaseCommand):
    help = "Write a read-only T1 audit of DataFile ownership and Dataset candidates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            required=True,
            help="Private directory for deterministic DataFile T1 TSV reports.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        paths = {name: output_dir / filename for name, filename in REPORT_NAMES.items()}
        existing = [path for path in paths.values() if path.exists()]
        if existing:
            raise CommandError(
                "Refusing to overwrite existing DataFile T1 reports: "
                + ", ".join(str(path) for path in existing)
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        with transaction.atomic():
            reports = self.collect_reports()
            transaction.set_rollback(True)

        write_tsv(paths["summary"], SUMMARY_FIELDS, reports["summary"])
        write_tsv(paths["files"], FILE_FIELDS, reports["files"])
        write_tsv(paths["relations"], RELATION_FIELDS, reports["relations"])

        self.stdout.write("mode\tREAD_ONLY")
        for name in ("summary", "files", "relations"):
            self.stdout.write(f"{name}\t{len(reports[name])}\t{paths[name]}")

    def collect_reports(self):
        datasets = list(Dataset.objects.order_by("id"))
        dataset_by_id = {dataset.id: dataset for dataset in datasets}
        dataset_accessions = defaultdict(set)
        datasets_by_accession = defaultdict(set)
        for link in DatasetAccession.objects.values("dataset_id", "accession_id"):
            dataset_accessions[link["dataset_id"]].add(link["accession_id"])
            datasets_by_accession[link["accession_id"]].add(link["dataset_id"])

        data_files = list(
            DataFile.objects.values("id", "file_code", "dataset_id").order_by("id")
        )
        file_by_id = {data_file["id"]: data_file for data_file in data_files}
        relations = list(
            FileRelation.objects.values(
                "id", "file_id", "related_type", "related_id", "file_role"
            ).order_by("file_id", "id")
        )
        relations_by_file = defaultdict(list)
        for relation in relations:
            relations_by_file[relation["file_id"]].append(relation)

        related_ids = defaultdict(set)
        for relation in relations:
            if relation["related_type"] not in RESOLVED_RELATION_TYPES:
                continue
            try:
                related_ids[relation["related_type"]].add(int(relation["related_id"]))
            except (TypeError, ValueError):
                pass

        object_maps = self.load_related_objects(related_ids)
        accession_codes = dict(Accession.objects.values_list("id", "accession"))
        relation_rows = []
        relation_results = {}
        resolution_counts = Counter()

        for relation in relations:
            result = self.resolve_relation(relation, object_maps, dataset_accessions)
            relation_results[relation["id"]] = result
            resolution_counts[result["resolution"]] += 1
            relation_rows.append(
                {
                    "relation_id": relation["id"],
                    "data_file_id": relation["file_id"],
                    "file_code": file_by_id[relation["file_id"]]["file_code"],
                    "related_type": relation["related_type"],
                    "related_id": relation["related_id"],
                    "file_role": relation["file_role"],
                    "role_category": self.role_category(relation["file_role"]),
                    "accession_codes": self.join_accession_codes(
                        result["accession_ids"], accession_codes
                    ),
                    "resolution": result["resolution"],
                    "issues": ",".join(result["issues"]),
                }
            )

        file_rows = []
        classification_counts = Counter()
        issue_counts = Counter()
        for data_file in data_files:
            file_relations = relations_by_file[data_file["id"]]
            current_dataset_ids = set()
            accession_ids = set()
            issues = []
            if data_file["dataset_id"] is not None:
                current_dataset_ids.add(data_file["dataset_id"])
                accession_ids.update(dataset_accessions[data_file["dataset_id"]])

            for relation in file_relations:
                result = relation_results[relation["id"]]
                accession_ids.update(result["accession_ids"])
                issues.extend(result["issues"])
                if result["dataset_id"] is not None:
                    current_dataset_ids.add(result["dataset_id"])

            role_categories = {
                self.role_category(relation["file_role"]) for relation in file_relations
            }
            candidate_ids = set()
            for accession_id in accession_ids:
                candidate_ids.update(datasets_by_accession[accession_id])
            compatible_types = {
                CATEGORY_TO_DATASET_TYPE[category]
                for category in role_categories
                if category in CATEGORY_TO_DATASET_TYPE
            }
            compatible_ids = {
                dataset_id
                for dataset_id in candidate_ids
                if dataset_by_id[dataset_id].dataset_type in compatible_types
            }

            if not file_relations and data_file["dataset_id"] is None:
                issues.append("no_ownership_relation")
            if len(accession_ids) > 1:
                issues.append("multiple_accession_contexts")
            if len(current_dataset_ids) > 1:
                issues.append("multiple_current_datasets")
            if current_dataset_ids - candidate_ids and accession_ids:
                issues.append("current_dataset_outside_accession_context")

            issues = self.unique(issues)
            classification = self.classify_file(
                current_dataset_ids=current_dataset_ids,
                accession_ids=accession_ids,
                candidate_ids=candidate_ids,
                compatible_ids=compatible_ids,
                issues=issues,
            )
            classification_counts[classification] += 1
            issue_counts.update(issues)
            file_rows.append(
                {
                    "data_file_id": data_file["id"],
                    "file_code": data_file["file_code"],
                    "direct_dataset_code": self.dataset_code(
                        dataset_by_id, data_file["dataset_id"]
                    ),
                    "current_dataset_codes": self.join_dataset_codes(
                        current_dataset_ids, dataset_by_id
                    ),
                    "relation_types": ",".join(
                        sorted({relation["related_type"] for relation in file_relations})
                    ),
                    "file_roles": ",".join(
                        sorted({relation["file_role"] for relation in file_relations})
                    ),
                    "role_categories": ",".join(sorted(role_categories)),
                    "accession_codes": self.join_accession_codes(
                        accession_ids, accession_codes
                    ),
                    "accession_dataset_candidates": self.join_dataset_codes(
                        candidate_ids, dataset_by_id
                    ),
                    "type_compatible_candidates": self.join_dataset_codes(
                        compatible_ids, dataset_by_id
                    ),
                    "classification": classification,
                    "issues": ",".join(issues),
                }
            )

        summary = [
            {"metric": "datafile_total", "value": len(data_files)},
            {"metric": "file_relation_total", "value": len(relations)},
            {"metric": "dataset_total", "value": len(datasets)},
        ]
        for classification in (
            "current_context_aligned",
            "current_requires_review",
            "current_conflict",
            "unique_type_candidate",
            "multiple_type_candidates",
            "needs_semantic_rule",
            "no_dataset_candidate",
            "no_accession_context",
            "invalid_context",
        ):
            summary.append(
                {
                    "metric": f"file_classification:{classification}",
                    "value": classification_counts[classification],
                }
            )
        for resolution, count in sorted(resolution_counts.items()):
            summary.append({"metric": f"relation_resolution:{resolution}", "value": count})
        for issue, count in sorted(issue_counts.items()):
            summary.append({"metric": f"file_issue:{issue}", "value": count})

        return {"summary": summary, "files": file_rows, "relations": relation_rows}

    @staticmethod
    def load_related_objects(related_ids):
        return {
            "accession": {
                row["id"]: row
                for row in Accession.objects.filter(
                    id__in=related_ids["accession"]
                ).values("id")
            },
            "assembly": {
                row["id"]: row
                for row in Assembly.objects.filter(id__in=related_ids["assembly"]).values(
                    "id", "accession_id"
                )
            },
            "annotation": {
                row["id"]: row
                for row in Annotation.objects.filter(
                    id__in=related_ids["annotation"]
                ).values("id", "accession_id", "assembly__accession_id")
            },
            "sample": {
                row["id"]: row
                for row in Sample.objects.filter(id__in=related_ids["sample"]).values(
                    "id", "accession_id"
                )
            },
            "dataset": {
                row["id"]: row
                for row in Dataset.objects.filter(id__in=related_ids["dataset"]).values("id")
            },
        }

    @staticmethod
    def resolve_relation(relation, object_maps, dataset_accessions):
        related_type = relation["related_type"]
        if related_type not in RESOLVED_RELATION_TYPES:
            return {
                "accession_ids": set(),
                "dataset_id": None,
                "resolution": "unresolved_relation_type",
                "issues": ["unresolved_relation_type"],
            }
        try:
            related_id = int(relation["related_id"])
        except (TypeError, ValueError):
            return {
                "accession_ids": set(),
                "dataset_id": None,
                "resolution": "invalid_related_id",
                "issues": ["invalid_related_id"],
            }
        related_object = object_maps[related_type].get(related_id)
        if related_object is None:
            return {
                "accession_ids": set(),
                "dataset_id": None,
                "resolution": "missing_related_object",
                "issues": ["missing_related_object"],
            }
        if related_type == "accession":
            return Command.resolved({related_id}, "accession")
        if related_type == "assembly":
            return Command.resolved({related_object["accession_id"]}, "assembly_accession")
        if related_type == "sample":
            accession_id = related_object["accession_id"]
            if accession_id is None:
                return Command.resolved(set(), "sample_without_accession")
            return Command.resolved({accession_id}, "sample_accession")
        if related_type == "dataset":
            return Command.resolved(
                dataset_accessions[related_id], "dataset_accessions", dataset_id=related_id
            )

        direct_id = related_object["accession_id"]
        assembly_id = related_object["assembly__accession_id"]
        if direct_id is not None and direct_id != assembly_id:
            result = Command.resolved(
                {direct_id, assembly_id}, "annotation_accession_conflict"
            )
            result["issues"].append("annotation_accession_conflict")
            return result
        return Command.resolved(
            {direct_id or assembly_id},
            "annotation_accession" if direct_id else "annotation_assembly_accession",
        )

    @staticmethod
    def resolved(accession_ids, resolution, dataset_id=None):
        return {
            "accession_ids": {value for value in accession_ids if value is not None},
            "dataset_id": dataset_id,
            "resolution": resolution,
            "issues": [],
        }

    @staticmethod
    def role_category(file_role):
        value = (file_role or "").strip().lower()
        if "hi-c" in value or "hic" in value:
            return "hic"
        return categorize_file_role(value)

    @staticmethod
    def classify_file(
        *, current_dataset_ids, accession_ids, candidate_ids, compatible_ids, issues
    ):
        invalid_issues = {
            "invalid_related_id",
            "missing_related_object",
            "annotation_accession_conflict",
        }
        if invalid_issues.intersection(issues):
            return "invalid_context"
        if len(current_dataset_ids) > 1:
            return "current_conflict"
        if current_dataset_ids:
            if current_dataset_ids.issubset(candidate_ids):
                return "current_context_aligned"
            return "current_requires_review"
        if not accession_ids:
            return "no_accession_context"
        if not candidate_ids:
            return "no_dataset_candidate"
        if len(compatible_ids) == 1:
            return "unique_type_candidate"
        if len(compatible_ids) > 1:
            return "multiple_type_candidates"
        return "needs_semantic_rule"

    @staticmethod
    def dataset_code(dataset_by_id, dataset_id):
        dataset = dataset_by_id.get(dataset_id)
        return dataset.dataset_code if dataset else ""

    @staticmethod
    def join_dataset_codes(dataset_ids, dataset_by_id):
        return ",".join(
            sorted(
                dataset_by_id[dataset_id].dataset_code
                for dataset_id in dataset_ids
                if dataset_id in dataset_by_id
            )
        )

    @staticmethod
    def join_accession_codes(accession_ids, accession_codes):
        return ",".join(
            sorted(
                accession_codes[accession_id]
                for accession_id in accession_ids
                if accession_id in accession_codes
            )
        )

    @staticmethod
    def unique(values):
        return list(dict.fromkeys(values))
