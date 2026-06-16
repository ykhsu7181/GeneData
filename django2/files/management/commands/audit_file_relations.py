import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from files.models import Accession, Annotation, Assembly, DataFile, Dataset, FileRelation


RELATED_MODEL_BY_TYPE = {
    "accession": Accession,
    "assembly": Assembly,
    "annotation": Annotation,
    "dataset": Dataset,
}


class Command(BaseCommand):
    help = "Audit FileRelation rows for broken generic references and duplicate relation keys."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for broken_file_relations_YYYYMMDD_HHMMSS.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"broken_file_relations_{timestamp}.tsv")

        rows, issue_counts = self.collect_broken_rows()
        duplicate_rows = self.collect_duplicate_rows()
        rows.extend(duplicate_rows)

        self.write_tsv(report_path, rows)

        broken_relation_count = sum(count for issue, count in issue_counts.items() if issue != "duplicate_relation")
        duplicate_relation_count = len(duplicate_rows)
        lines = [
            f"filerelation_total\t{FileRelation.objects.count()}",
            f"broken_relation_count\t{broken_relation_count}",
            f"duplicate_relation_count\t{duplicate_relation_count}",
            f"report\t{report_path}",
        ]
        for issue, count in sorted(issue_counts.items()):
            lines.append(f"issue_{issue}\t{count}")
        for line in lines:
            self.stdout.write(line)

    def collect_broken_rows(self):
        rows = [["issue", "relation_id", "file_id", "related_type", "related_id", "file_role", "details"]]
        issue_counts = Counter()
        datafile_ids = set(DataFile.objects.values_list("id", flat=True))

        for relation in FileRelation.objects.all().order_by("id"):
            issues = []
            if not relation.file_id or relation.file_id not in datafile_ids:
                issues.append("missing_datafile")
            if not relation.related_type:
                issues.append("empty_related_type")
            if not relation.related_id:
                issues.append("empty_related_id")
            if not relation.file_role:
                issues.append("empty_file_role")

            related_model = RELATED_MODEL_BY_TYPE.get(relation.related_type)
            if related_model and relation.related_id:
                if not related_model.objects.filter(id=relation.related_id).exists():
                    issues.append("missing_related_object")

            for issue in issues:
                issue_counts[issue] += 1
                rows.append(
                    [
                        issue,
                        relation.id,
                        relation.file_id,
                        relation.related_type or "",
                        relation.related_id or "",
                        relation.file_role or "",
                        relation.related_code or "",
                    ]
                )
        return rows, issue_counts

    def collect_duplicate_rows(self):
        rows = []
        duplicates = (
            FileRelation.objects.values("file_id", "related_type", "related_id", "file_role")
            .annotate(row_count=Count("id"))
            .filter(row_count__gt=1)
            .order_by("file_id", "related_type", "related_id", "file_role")
        )
        for item in duplicates:
            rows.append(
                [
                    "duplicate_relation",
                    "",
                    item["file_id"],
                    item["related_type"] or "",
                    item["related_id"] or "",
                    item["file_role"] or "",
                    f"count={item['row_count']}",
                ]
            )
        return rows

    def write_tsv(self, report_path, rows):
        with open(report_path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")
