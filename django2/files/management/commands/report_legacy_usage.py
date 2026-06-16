import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from files.models import Accession, DataFile, FileRelation, GenomeFile


class Command(BaseCommand):
    help = "Report current GenomeFile / organism fallback usage candidates without changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for legacy_usage_report_YYYYMMDD_HHMMSS.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"legacy_usage_report_{timestamp}.tsv")

        rows = [[
            "fallback_type",
            "related_type",
            "related_id",
            "accession_code",
            "file_role",
            "file_path",
            "fallback_source",
            "suggested_action",
        ]]
        for genome_file in GenomeFile.objects.select_related("accession", "assembly", "annotation").order_by("id"):
            row = self.build_usage_row(genome_file)
            if row:
                rows.append(row)

        self.write_tsv(report_path, rows)
        self.stdout.write(f"legacy_usage_count\t{len(rows) - 1}")
        self.stdout.write(f"report\t{report_path}")

    def build_usage_row(self, genome_file):
        relation = self.suggest_relation(genome_file)
        if not relation:
            return [
                "unresolved_legacy",
                "",
                "",
                genome_file.organism or "",
                genome_file.category or "",
                genome_file.file_path or "",
                self.current_source(genome_file),
                "resolve_accession_or_related_object",
            ]

        data_file = DataFile.objects.filter(file_path=genome_file.file_path).first()
        has_relation = False
        if data_file:
            has_relation = FileRelation.objects.filter(
                file=data_file,
                related_type=relation["related_type"],
                related_id=str(relation["related_id"]),
                file_role=genome_file.category,
            ).exists()

        if data_file and has_relation:
            return None

        return [
            "legacy_query_dependency",
            relation["related_type"],
            relation["related_id"],
            relation["accession_code"],
            genome_file.category or "",
            genome_file.file_path or "",
            self.current_source(genome_file),
            "backfill_to_datafile_filerelation",
        ]

    def suggest_relation(self, genome_file):
        if genome_file.annotation_id:
            return {
                "related_type": "annotation",
                "related_id": genome_file.annotation_id,
                "accession_code": genome_file.annotation.assembly.accession.accession,
            }
        if genome_file.assembly_id:
            return {
                "related_type": "assembly",
                "related_id": genome_file.assembly_id,
                "accession_code": genome_file.assembly.accession.accession,
            }
        if genome_file.accession_id:
            return {
                "related_type": "accession",
                "related_id": genome_file.accession_id,
                "accession_code": genome_file.accession.accession,
            }

        accession = Accession.objects.filter(accession=genome_file.organism).first()
        if accession:
            return {
                "related_type": "accession",
                "related_id": accession.id,
                "accession_code": accession.accession,
            }
        return None

    def current_source(self, genome_file):
        if genome_file.accession_id or genome_file.assembly_id or genome_file.annotation_id:
            return "legacy_genomefile"
        if Accession.objects.filter(accession=genome_file.organism).exists():
            return "organism_fallback"
        return "legacy_genomefile"

    def write_tsv(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")
