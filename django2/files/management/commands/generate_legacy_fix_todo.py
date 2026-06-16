import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from files.models import Accession, DataFile, FileRelation, GenomeFile


class Command(BaseCommand):
    help = "Generate a read-only todo report for reducing GenomeFile/organism fallback dependency."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for legacy_fix_todo_YYYYMMDD_HHMMSS.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"legacy_fix_todo_{timestamp}.tsv")

        rows = [[
            "object_type",
            "object_id",
            "accession_code",
            "file_path",
            "current_source",
            "fallback_reason",
            "suggested_related_type",
            "suggested_related_id",
            "suggested_file_role",
            "action",
        ]]

        for genome_file in GenomeFile.objects.select_related("accession", "assembly", "annotation").order_by("id"):
            todo = self.build_todo_row(genome_file)
            if todo:
                rows.append(todo)

        self.write_tsv(report_path, rows)
        todo_count = len(rows) - 1
        self.stdout.write(f"todo_count\t{todo_count}")
        self.stdout.write(f"report\t{report_path}")

    def build_todo_row(self, genome_file):
        data_file = DataFile.objects.filter(file_path=genome_file.file_path).first()
        relation_spec = self.suggest_relation(genome_file)
        if not relation_spec:
            return [
                "GenomeFile",
                genome_file.id,
                genome_file.accession.accession if genome_file.accession_id else genome_file.organism,
                genome_file.file_path or "",
                self.current_source(genome_file),
                "no_related_object",
                "",
                "",
                genome_file.category or "",
                "resolve_related_object",
            ]

        has_relation = False
        if data_file:
            has_relation = FileRelation.objects.filter(
                file=data_file,
                related_type=relation_spec["related_type"],
                related_id=str(relation_spec["related_id"]),
                file_role=genome_file.category,
            ).exists()

        if data_file and has_relation:
            return None

        fallback_reason = "missing_datafile" if not data_file else "missing_filerelation"
        action = "create_datafile_and_filerelation" if not data_file else "create_filerelation"
        return [
            "GenomeFile",
            genome_file.id,
            relation_spec["accession_code"],
            genome_file.file_path or "",
            self.current_source(genome_file),
            fallback_reason,
            relation_spec["related_type"],
            relation_spec["related_id"],
            genome_file.category or "",
            action,
        ]

    def suggest_relation(self, genome_file):
        if genome_file.annotation_id:
            accession = genome_file.annotation.assembly.accession
            return {
                "related_type": "annotation",
                "related_id": genome_file.annotation_id,
                "accession_code": accession.accession,
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
