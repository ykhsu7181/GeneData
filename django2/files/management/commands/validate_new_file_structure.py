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
    help = "Validate whether file data is ready for DataFile/FileRelation new-only mode."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for validate_new_file_structure reports. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        txt_path = os.path.join(output_dir, f"validate_new_file_structure_{timestamp}.txt")
        tsv_path = os.path.join(output_dir, f"validate_new_file_structure_{timestamp}.tsv")

        detail_rows = [[
            "check_type",
            "object_type",
            "object_id",
            "file_path",
            "related_type",
            "related_id",
            "file_role",
            "issue",
            "suggested_action",
        ]]

        stats = {
            "genomefile_total_count": GenomeFile.objects.count(),
            "datafile_total_count": DataFile.objects.count(),
            "genomefile_missing_datafile_count": 0,
            "datafile_without_relation_count": 0,
            "broken_filerelation_count": 0,
            "duplicate_filerelation_count": 0,
            "legacy_fallback_count": 0,
            "organism_fallback_count": 0,
        }

        self.check_genomefile_coverage(detail_rows, stats)
        self.check_datafile_relations(detail_rows, stats)
        self.check_filerelation_integrity(detail_rows, stats)
        self.check_legacy_query_dependency(detail_rows, stats)

        passed = self.is_pass(stats)
        summary_lines = self.build_summary(stats, passed, txt_path, tsv_path)
        self.write_lines(txt_path, summary_lines)
        self.write_tsv(tsv_path, detail_rows)

        for line in summary_lines:
            self.stdout.write(line)

    def check_genomefile_coverage(self, detail_rows, stats):
        datafile_paths = {
            self.normalize_path(path)
            for path in DataFile.objects.filter(is_current=True).values_list(
                "file_path", flat=True
            )
        }
        for genome_file in GenomeFile.objects.all().order_by("id"):
            if self.normalize_path(genome_file.file_path) in datafile_paths:
                continue
            stats["genomefile_missing_datafile_count"] += 1
            detail_rows.append([
                "genomefile_coverage",
                "GenomeFile",
                genome_file.id,
                genome_file.file_path or "",
                "",
                "",
                genome_file.category or "",
                "genomefile_missing_datafile",
                "create_or_backfill_datafile_for_file_path",
            ])

    def check_datafile_relations(self, detail_rows, stats):
        related_file_ids = set(FileRelation.objects.values_list("file_id", flat=True))
        # Quarantined and retired rows intentionally have no active relation.
        # New-only readiness concerns files that remain available to readers.
        for data_file in DataFile.objects.filter(is_current=True).order_by("id"):
            if data_file.id in related_file_ids:
                continue
            stats["datafile_without_relation_count"] += 1
            detail_rows.append([
                "datafile_relation",
                "DataFile",
                data_file.id,
                data_file.file_path or "",
                "",
                "",
                "",
                "datafile_without_relation",
                "create_filerelation_for_datafile",
            ])

    def check_filerelation_integrity(self, detail_rows, stats):
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
                stats["broken_filerelation_count"] += 1
                detail_rows.append([
                    "filerelation_integrity",
                    "FileRelation",
                    relation.id,
                    relation.file.file_path if relation.file_id and relation.file_id in datafile_ids else "",
                    relation.related_type or "",
                    relation.related_id or "",
                    relation.file_role or "",
                    issue,
                    "fix_or_remove_broken_filerelation_before_new_only",
                ])

        duplicates = self.collect_duplicate_relation_rows()
        stats["duplicate_filerelation_count"] = len(duplicates)
        detail_rows.extend(duplicates)

    def check_legacy_query_dependency(self, detail_rows, stats):
        for accession in Accession.objects.order_by("accession", "id"):
            if self.has_accession_relation(accession):
                continue

            legacy_files = GenomeFile.objects.filter(accession=accession).order_by("id")
            if legacy_files.exists():
                for genome_file in legacy_files:
                    stats["legacy_fallback_count"] += 1
                    detail_rows.append(self.fallback_row(
                        check_type="accession_detail",
                        accession=accession,
                        genome_file=genome_file,
                        fallback_source="legacy_genomefile",
                    ))
                continue

            organism_files = GenomeFile.objects.filter(organism=accession.accession).order_by("id")
            for genome_file in organism_files:
                stats["organism_fallback_count"] += 1
                detail_rows.append(self.fallback_row(
                    check_type="paginated_overview",
                    accession=accession,
                    genome_file=genome_file,
                    fallback_source="organism_fallback",
                ))

        for annotation in Annotation.objects.select_related("assembly__accession").order_by("id"):
            if FileRelation.objects.filter(
                related_type="annotation",
                related_id=str(annotation.id),
            ).exists():
                continue
            legacy_files = GenomeFile.objects.filter(annotation=annotation).order_by("id")
            for genome_file in legacy_files:
                stats["legacy_fallback_count"] += 1
                detail_rows.append([
                    "annotation",
                    "Annotation",
                    annotation.id,
                    genome_file.file_path or "",
                    "annotation",
                    annotation.id,
                    genome_file.category or "",
                    "legacy_fallback",
                    "create_datafile_and_annotation_filerelation",
                ])

    def has_accession_relation(self, accession):
        return FileRelation.objects.filter(
            related_type="accession",
            related_id=str(accession.id),
        ).exists()

    def fallback_row(self, *, check_type, accession, genome_file, fallback_source):
        issue = "organism_fallback" if fallback_source == "organism_fallback" else "legacy_fallback"
        suggested_action = (
            "create_datafile_and_accession_filerelation_from_organism"
            if fallback_source == "organism_fallback"
            else "create_datafile_and_accession_filerelation"
        )
        return [
            check_type,
            "Accession",
            accession.id,
            genome_file.file_path or "",
            "accession",
            accession.id,
            genome_file.category or "",
            issue,
            suggested_action,
        ]

    def collect_duplicate_relation_rows(self):
        rows = []
        duplicates = (
            FileRelation.objects.values("file_id", "related_type", "related_id", "file_role")
            .annotate(row_count=Count("id"))
            .filter(row_count__gt=1)
            .order_by("file_id", "related_type", "related_id", "file_role")
        )
        for item in duplicates:
            rows.append([
                "filerelation_duplicate",
                "FileRelation",
                "",
                "",
                item["related_type"] or "",
                item["related_id"] or "",
                item["file_role"] or "",
                "duplicate_filerelation",
                f"deduplicate_relation_key file_id={item['file_id']} count={item['row_count']}",
            ])
        return rows

    @staticmethod
    def find_duplicate_relation_keys(relation_rows):
        counts = Counter()
        for row in relation_rows:
            key = (
                row.get("file_id"),
                row.get("related_type"),
                str(row.get("related_id")),
                row.get("file_role"),
            )
            counts[key] += 1

        duplicates = []
        for key, row_count in counts.items():
            if row_count <= 1:
                continue
            duplicates.append(
                {
                    "file_id": key[0],
                    "related_type": key[1],
                    "related_id": key[2],
                    "file_role": key[3],
                    "row_count": row_count,
                }
            )
        return duplicates

    def is_pass(self, stats):
        return all(
            stats[key] == 0
            for key in [
                "genomefile_missing_datafile_count",
                "datafile_without_relation_count",
                "broken_filerelation_count",
                "duplicate_filerelation_count",
                "legacy_fallback_count",
                "organism_fallback_count",
            ]
        )

    def build_summary(self, stats, passed, txt_path, tsv_path):
        result = "PASS" if passed else "FAIL"
        lines = [
            f"genomefile_total_count\t{stats['genomefile_total_count']}",
            f"genomefile_missing_datafile_count\t{stats['genomefile_missing_datafile_count']}",
            f"datafile_total_count\t{stats['datafile_total_count']}",
            f"datafile_without_relation_count\t{stats['datafile_without_relation_count']}",
            f"broken_filerelation_count\t{stats['broken_filerelation_count']}",
            f"duplicate_filerelation_count\t{stats['duplicate_filerelation_count']}",
            f"legacy_fallback_count\t{stats['legacy_fallback_count']}",
            f"organism_fallback_count\t{stats['organism_fallback_count']}",
            f"result\t{result}",
            f"cannot_enter_new_only\t{str(not passed).lower()}",
            f"txt_report\t{txt_path}",
            f"tsv_report\t{tsv_path}",
        ]
        if not passed:
            lines.append("message\tFAIL: cannot enter new-only stage before fixing reported issues.")
        else:
            lines.append("message\tPASS: ready to start file_relation_service new-only refactor.")
        return lines

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
