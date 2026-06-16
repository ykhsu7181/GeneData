import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from files.models import Accession, Annotation, Assembly, DataFile, Dataset, FileRelation, GenomeFile


RELATED_MODEL_BY_TYPE = {
    "accession": Accession,
    "assembly": Assembly,
    "annotation": Annotation,
    "dataset": Dataset,
}


class Command(BaseCommand):
    help = "Audit GenomeFile to DataFile/FileRelation migration coverage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for file_migration_audit reports. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        txt_path = os.path.join(output_dir, f"file_migration_audit_{timestamp}.txt")
        tsv_path = os.path.join(output_dir, f"file_migration_audit_{timestamp}.tsv")

        datafile_paths = {self.normalize_path(path) for path in DataFile.objects.values_list("file_path", flat=True)}
        detail_rows = [["issue", "object_type", "object_id", "file_path", "details"]]

        genomefile_total = GenomeFile.objects.count()
        datafile_total = DataFile.objects.count()
        filerelation_total = FileRelation.objects.count()

        matched_count = 0
        missing_count = 0
        for genome_file in GenomeFile.objects.all().order_by("id"):
            if self.normalize_path(genome_file.file_path) in datafile_paths:
                matched_count += 1
            else:
                missing_count += 1
                detail_rows.append(
                    [
                        "missing_datafile",
                        "GenomeFile",
                        genome_file.id,
                        genome_file.file_path or "",
                        genome_file.name or "",
                    ]
                )

        datafile_without_relation_count = 0
        related_file_ids = set(FileRelation.objects.values_list("file_id", flat=True))
        for data_file in DataFile.objects.all().order_by("id"):
            if data_file.id not in related_file_ids:
                datafile_without_relation_count += 1
                detail_rows.append(
                    [
                        "datafile_without_relation",
                        "DataFile",
                        data_file.id,
                        data_file.file_path or "",
                        data_file.file_name or "",
                    ]
                )

        broken_relation_rows = self.collect_broken_relation_rows()
        detail_rows.extend(broken_relation_rows)
        broken_filerelation_count = len(broken_relation_rows)

        duplicate_file_path_rows = self.collect_duplicate_file_path_rows()
        detail_rows.extend(duplicate_file_path_rows)
        duplicate_file_path_count = len(duplicate_file_path_rows)

        duplicate_relation_rows = self.collect_duplicate_relation_rows()
        detail_rows.extend(duplicate_relation_rows)
        duplicate_filerelation_count = len(duplicate_relation_rows)

        summary = [
            f"genomefile_total\t{genomefile_total}",
            f"datafile_total\t{datafile_total}",
            f"filerelation_total\t{filerelation_total}",
            f"genomefile_matched_datafile_count\t{matched_count}",
            f"genomefile_missing_datafile_count\t{missing_count}",
            f"datafile_without_relation_count\t{datafile_without_relation_count}",
            f"broken_filerelation_count\t{broken_filerelation_count}",
            f"duplicate_file_path_count\t{duplicate_file_path_count}",
            f"duplicate_filerelation_count\t{duplicate_filerelation_count}",
            f"txt_report\t{txt_path}",
            f"tsv_report\t{tsv_path}",
        ]

        self.write_lines(txt_path, summary)
        self.write_tsv(tsv_path, detail_rows)
        for line in summary:
            self.stdout.write(line)

    def collect_broken_relation_rows(self):
        rows = []
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
                rows.append(
                    [
                        "broken_filerelation",
                        "FileRelation",
                        relation.id,
                        relation.file.file_path if relation.file_id and relation.file_id in datafile_ids else "",
                        issue,
                    ]
                )
        return rows

    def collect_duplicate_file_path_rows(self):
        rows = []
        duplicates = (
            GenomeFile.objects.values("file_path")
            .annotate(row_count=Count("id"))
            .filter(row_count__gt=1)
            .order_by("file_path")
        )
        for item in duplicates:
            rows.append(
                [
                    "duplicate_file_path",
                    "GenomeFile",
                    "",
                    item["file_path"] or "",
                    f"count={item['row_count']}",
                ]
            )
        return rows

    def collect_duplicate_relation_rows(self):
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
                    "duplicate_filerelation",
                    "FileRelation",
                    "",
                    "",
                    (
                        f"file_id={item['file_id']};"
                        f"related_type={item['related_type']};"
                        f"related_id={item['related_id']};"
                        f"file_role={item['file_role']};"
                        f"count={item['row_count']}"
                    ),
                ]
            )
        return rows

    def normalize_path(self, file_path):
        return os.path.abspath(os.path.normpath(file_path or ""))

    def write_lines(self, path, lines):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")

    def write_tsv(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")
