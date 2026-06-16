import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from files.models import Accession, Annotation, FileRelation, GenomeFile
from files.services.file_relation_service import get_files_for_accession, get_files_for_annotation


class Command(BaseCommand):
    help = "Audit legacy GenomeFile and organism fallback dependency in file queries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit accession records audited.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for legacy_fallback_report_YYYYMMDD_HHMMSS.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")
        if limit is not None and limit < 1:
            raise CommandError("--limit must be greater than 0.")

        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"legacy_fallback_report_{timestamp}.tsv")

        accession_qs = Accession.objects.order_by("accession", "id")
        if limit is not None:
            accession_qs = accession_qs[:limit]

        accession_source_counts = Counter()
        annotation_source_counts = Counter()
        overview_source_counts = Counter()
        legacy_accessions = []
        organism_fallback_accessions = []
        rows = [[
            "scope",
            "accession",
            "object_type",
            "object_id",
            "source",
            "file_count",
            "details",
        ]]

        for accession in accession_qs:
            accession_files = get_files_for_accession(accession.id)
            if accession_files:
                source_counts = Counter(
                    item.get("fallback_source") or item["source"]
                    for item in accession_files
                )
                accession_source_counts.update(source_counts)
                for source, count in sorted(source_counts.items()):
                    rows.append(["accession", accession.accession, "Accession", accession.id, source, count, ""])
                if "legacy_genomefile" in source_counts:
                    legacy_accessions.append(accession.accession)
            else:
                accession_source_counts["no_files"] += 1
                rows.append(["accession", accession.accession, "Accession", accession.id, "no_files", 0, ""])

            overview_source, overview_count = self.resolve_overview_source(accession)
            overview_source_counts[overview_source] += overview_count
            rows.append([
                "overview",
                accession.accession,
                "Accession",
                accession.id,
                overview_source,
                overview_count,
                "",
            ])
            if overview_source == "legacy_genomefile":
                if accession.accession not in legacy_accessions:
                    legacy_accessions.append(accession.accession)
            if overview_source == "organism_fallback":
                organism_fallback_accessions.append(accession.accession)

            for annotation in Annotation.objects.filter(assembly__accession=accession).order_by("id"):
                annotation_files = get_files_for_annotation(annotation.id)
                if annotation_files:
                    source_counts = Counter(
                        item.get("fallback_source") or item["source"]
                        for item in annotation_files
                    )
                    annotation_source_counts.update(source_counts)
                    for source, count in sorted(source_counts.items()):
                        rows.append([
                            "annotation",
                            accession.accession,
                            "Annotation",
                            annotation.id,
                            source,
                            count,
                            annotation.name,
                        ])
                else:
                    annotation_source_counts["no_files"] += 1
                    rows.append([
                        "annotation",
                        accession.accession,
                        "Annotation",
                        annotation.id,
                        "no_files",
                        0,
                        annotation.name,
                    ])

        self.write_tsv(report_path, rows)

        lines = []
        lines.extend(self.format_counter("accession_source", accession_source_counts))
        lines.extend(self.format_counter("annotation_source", annotation_source_counts))
        lines.extend(self.format_counter("overview_source", overview_source_counts))
        lines.append(f"legacy_fallback_accession_count\t{len(set(legacy_accessions))}")
        lines.append(f"organism_fallback_accession_count\t{len(set(organism_fallback_accessions))}")
        lines.append(f"report\t{report_path}")
        for line in lines:
            self.stdout.write(line)

    def resolve_overview_source(self, accession):
        relation_count = FileRelation.objects.filter(
            related_type="accession",
            related_id=str(accession.id),
        ).count()
        if relation_count:
            return "new_relation", relation_count

        legacy_count = GenomeFile.objects.filter(accession=accession).count()
        if legacy_count:
            return "legacy_genomefile", legacy_count

        organism_count = GenomeFile.objects.filter(organism=accession.accession).count()
        if organism_count:
            return "organism_fallback", organism_count

        return "no_files", 0

    def format_counter(self, prefix, counter):
        if not counter:
            return [f"{prefix}_none\t0"]
        return [f"{prefix}_{source}\t{count}" for source, count in sorted(counter.items())]

    def write_tsv(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")
