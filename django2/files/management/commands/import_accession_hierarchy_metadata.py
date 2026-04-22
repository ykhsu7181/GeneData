import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from files.models import Accession, Annotation, Assembly


class Command(BaseCommand):
    help = (
        "Import assembly/annotation display metadata from "
        "assembly_metadata.tsv and annotation_metadata.tsv."
    )

    @staticmethod
    def normalize_header(value):
        return str(value or "").strip().lower().replace(" ", "").replace("_", "")

    def add_arguments(self, parser):
        parser.add_argument(
            "--assembly-file",
            default=os.path.join(settings.MANUAL_FILES_DIR, "assembly_metadata.tsv"),
            help="Path to the assembly metadata TSV/CSV file.",
        )
        parser.add_argument(
            "--annotation-file",
            default=os.path.join(settings.MANUAL_FILES_DIR, "annotation_metadata.tsv"),
            help="Path to the annotation metadata TSV/CSV file.",
        )

    def load_rows(self, file_path):
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f"Metadata file not found: {file_path}"))
            return []

        with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(2048)
            handle.seek(0)
            delimiter = "\t"
            if file_path.lower().endswith(".csv"):
                delimiter = ","
            else:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
                    delimiter = dialect.delimiter
                except csv.Error:
                    delimiter = "\t"

            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                return []

            normalized_fieldnames = [self.normalize_header(item) for item in reader.fieldnames]
            rows = []
            for row in reader:
                normalized_row = {}
                for original_key, normalized_key in zip(reader.fieldnames, normalized_fieldnames):
                    normalized_row[normalized_key] = (row.get(original_key) or "").strip()
                rows.append(normalized_row)
            return rows

    @staticmethod
    def coalesce(row, *keys):
        for key in keys:
            value = (row.get(key) or "").strip()
            if value:
                return value
        return ""

    @transaction.atomic
    def handle(self, *args, **options):
        assembly_rows = self.load_rows(options["assembly_file"])
        annotation_rows = self.load_rows(options["annotation_file"])

        assembly_updated = 0
        annotation_updated = 0
        skipped = 0

        for row in assembly_rows:
            accession_code = self.coalesce(row, "accession")
            assembly_name = self.coalesce(row, "assembly_name", "assemblyname", "name")

            if not accession_code or not assembly_name:
                skipped += 1
                continue

            accession = Accession.objects.filter(accession=accession_code).first()
            if not accession:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Assembly metadata skipped: accession not found ({accession_code})"
                    )
                )
                continue

            assembly = Assembly.objects.filter(accession=accession, name=assembly_name).first()
            if not assembly:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Assembly metadata skipped: assembly not found "
                        f"({accession_code}:{assembly_name})"
                    )
                )
                continue

            assembly.display_name = self.coalesce(
                row, "display_name", "displayname"
            ) or assembly.display_name
            assembly.standard_id = self.coalesce(
                row, "standard_id", "standardid", "assembly_accession", "assemblyaccession"
            ) or assembly.standard_id
            assembly.bio_project = self.coalesce(
                row, "bio_project", "bioproject", "ncbibioproject"
            ) or assembly.bio_project
            assembly.reference = self.coalesce(row, "reference") or assembly.reference
            assembly.save(
                update_fields=[
                    "display_name",
                    "standard_id",
                    "bio_project",
                    "reference",
                    "updated_at",
                ]
            )
            assembly_updated += 1

        for row in annotation_rows:
            accession_code = self.coalesce(row, "accession")
            assembly_name = self.coalesce(row, "assembly_name", "assemblyname")
            annotation_name = self.coalesce(row, "annotation_name", "annotationname", "name")

            if not accession_code or not assembly_name or not annotation_name:
                skipped += 1
                continue

            accession = Accession.objects.filter(accession=accession_code).first()
            if not accession:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Annotation metadata skipped: accession not found ({accession_code})"
                    )
                )
                continue

            assembly = Assembly.objects.filter(accession=accession, name=assembly_name).first()
            if not assembly:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Annotation metadata skipped: assembly not found "
                        f"({accession_code}:{assembly_name})"
                    )
                )
                continue

            annotation = Annotation.objects.filter(assembly=assembly, name=annotation_name).first()
            if not annotation:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Annotation metadata skipped: annotation not found "
                        f"({accession_code}:{assembly_name}:{annotation_name})"
                    )
                )
                continue

            annotation.display_name = self.coalesce(
                row, "display_name", "displayname"
            ) or annotation.display_name
            annotation.standard_id = self.coalesce(
                row, "standard_id", "standardid", "annotation_standard_id", "annotationstandardid"
            ) or annotation.standard_id
            annotation.source_name = self.coalesce(
                row, "source_name", "sourcename"
            ) or annotation.source_name
            annotation.release_version = self.coalesce(
                row, "release_version", "releaseversion", "version"
            ) or annotation.release_version
            annotation.save(
                update_fields=[
                    "display_name",
                    "standard_id",
                    "source_name",
                    "release_version",
                    "updated_at",
                ]
            )
            annotation_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Hierarchy metadata import completed. "
                f"Assemblies updated: {assembly_updated}, "
                f"Annotations updated: {annotation_updated}, "
                f"Skipped: {skipped}"
            )
        )
