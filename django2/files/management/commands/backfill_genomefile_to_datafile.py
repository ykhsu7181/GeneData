import hashlib
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from files.models import DataFile, FileRelation, GenomeFile


FILE_CODE_PATTERN = re.compile(r"^FILE(\d+)$")


class Command(BaseCommand):
    help = "Backfill legacy GenomeFile records into DataFile and FileRelation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes and write reports without creating or updating records.",
        )
        parser.add_argument(
            "--with-md5",
            action="store_true",
            help="Calculate md5 for files that exist on disk.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of GenomeFile records processed.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for migration_log.txt and unmapped_files.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with_md5 = options["with_md5"]
        limit = options["limit"]
        output_dir = options["output_dir"] or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)

        log_path = os.path.join(output_dir, "migration_log.txt")
        unmapped_path = os.path.join(output_dir, "unmapped_files.tsv")
        stats = {
            "scanned": 0,
            "datafile_created": 0,
            "datafile_reused": 0,
            "datafile_updated": 0,
            "relation_created": 0,
            "relation_reused": 0,
            "unmapped": 0,
            "missing_files": 0,
        }
        log_lines = []
        unmapped_rows = [
            [
                "genome_file_id",
                "name",
                "file_path",
                "organism",
                "category",
                "warnings",
            ]
        ]

        queryset = (
            GenomeFile.objects.select_related("file_type", "accession", "assembly", "annotation")
            .order_by("id")
        )
        if limit is not None:
            queryset = queryset[:limit]

        next_file_number = self.get_next_file_number()

        log_lines.append(f"started_at\t{timezone.now().isoformat()}")
        log_lines.append(f"dry_run\t{dry_run}")
        log_lines.append(f"with_md5\t{with_md5}")
        log_lines.append(f"limit\t{limit if limit is not None else ''}")

        for genome_file in queryset:
            stats["scanned"] += 1
            warnings = []
            file_exists = bool(genome_file.file_path and os.path.exists(genome_file.file_path))
            file_size = None
            md5 = None

            if file_exists:
                file_size = self.safe_get_file_size(genome_file.file_path, warnings)
                if with_md5:
                    md5 = self.calculate_md5(genome_file.file_path, warnings)
            else:
                stats["missing_files"] += 1
                warnings.append("missing_file")

            data_file, created, updated, next_file_number = self.get_or_create_data_file(
                genome_file=genome_file,
                file_size=file_size,
                md5=md5,
                next_file_number=next_file_number,
                dry_run=dry_run,
            )
            if created:
                stats["datafile_created"] += 1
            else:
                stats["datafile_reused"] += 1
            if updated:
                stats["datafile_updated"] += 1

            relations = self.build_relation_specs(genome_file)
            if not relations:
                stats["unmapped"] += 1
                warnings.append("no_explicit_relation")

            for relation in relations:
                relation_created = self.ensure_relation(data_file, relation, dry_run)
                if relation_created:
                    stats["relation_created"] += 1
                else:
                    stats["relation_reused"] += 1

            if warnings:
                unmapped_rows.append(
                    [
                        str(genome_file.id),
                        genome_file.name or "",
                        genome_file.file_path or "",
                        genome_file.organism or "",
                        genome_file.category or "",
                        ";".join(warnings),
                    ]
                )

        log_lines.extend(
            [
                f"scanned\t{stats['scanned']}",
                f"datafile_created\t{stats['datafile_created']}",
                f"datafile_reused\t{stats['datafile_reused']}",
                f"datafile_updated\t{stats['datafile_updated']}",
                f"relation_created\t{stats['relation_created']}",
                f"relation_reused\t{stats['relation_reused']}",
                f"unmapped\t{stats['unmapped']}",
                f"missing_files\t{stats['missing_files']}",
                f"finished_at\t{timezone.now().isoformat()}",
            ]
        )

        self.write_log(log_path, log_lines)
        self.write_unmapped(unmapped_path, unmapped_rows)

        self.stdout.write(
            self.style.SUCCESS(
                "Backfill completed. "
                f"Scanned: {stats['scanned']}, "
                f"DataFiles created: {stats['datafile_created']}, "
                f"Relations created: {stats['relation_created']}, "
                f"Unmapped: {stats['unmapped']}, "
                f"Missing files: {stats['missing_files']}. "
                f"Reports: {log_path}, {unmapped_path}"
            )
        )

    def get_next_file_number(self):
        max_number = 0
        for file_code in DataFile.objects.values_list("file_code", flat=True):
            match = FILE_CODE_PATTERN.match(file_code or "")
            if match:
                max_number = max(max_number, int(match.group(1)))
        return max_number + 1

    def make_file_code(self, number):
        return f"FILE{number:06d}"

    def safe_get_file_size(self, file_path, warnings):
        try:
            return os.path.getsize(file_path)
        except OSError:
            warnings.append("file_size_read_failed")
            return None

    def calculate_md5(self, file_path, warnings):
        digest = hashlib.md5()
        try:
            with open(file_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            warnings.append("md5_read_failed")
            return None
        return digest.hexdigest()

    def get_or_create_data_file(self, *, genome_file, file_size, md5, next_file_number, dry_run):
        data_file = DataFile.objects.filter(file_path=genome_file.file_path).first()
        if data_file:
            updated = False
            update_fields = []

            if file_size is not None and data_file.file_size is None:
                data_file.file_size = file_size
                update_fields.append("file_size")
            if md5 and not data_file.md5:
                data_file.md5 = md5
                update_fields.append("md5")

            if update_fields:
                updated = True
                if not dry_run:
                    update_fields.append("updated_at")
                    data_file.save(update_fields=update_fields)
            return data_file, False, updated, next_file_number

        file_code = self.make_file_code(next_file_number)
        next_file_number += 1

        data_file = DataFile(
            file_code=file_code,
            file_type=genome_file.file_type,
            file_name=genome_file.name,
            original_name=genome_file.name,
            file_path=genome_file.file_path,
            file_size=file_size,
            md5=md5,
        )

        if not dry_run:
            data_file.save()

        return data_file, True, False, next_file_number

    def build_relation_specs(self, genome_file):
        relations = []
        if genome_file.accession_id:
            relations.append(
                {
                    "related_type": "accession",
                    "related_id": str(genome_file.accession_id),
                    "related_code": genome_file.accession.accession if genome_file.accession else "",
                    "file_role": genome_file.category,
                }
            )
        if genome_file.assembly_id:
            relations.append(
                {
                    "related_type": "assembly",
                    "related_id": str(genome_file.assembly_id),
                    "related_code": genome_file.assembly.name if genome_file.assembly else "",
                    "file_role": genome_file.category,
                }
            )
        if genome_file.annotation_id:
            relations.append(
                {
                    "related_type": "annotation",
                    "related_id": str(genome_file.annotation_id),
                    "related_code": genome_file.annotation.name if genome_file.annotation else "",
                    "file_role": genome_file.category,
                }
            )
        return relations

    def ensure_relation(self, data_file, relation, dry_run):
        existing = FileRelation.objects.filter(
            file=data_file,
            related_type=relation["related_type"],
            related_id=relation["related_id"],
            file_role=relation["file_role"],
        ).exists()
        if existing:
            return False

        if dry_run:
            return True

        with transaction.atomic():
            _, created = FileRelation.objects.get_or_create(
                file=data_file,
                related_type=relation["related_type"],
                related_id=relation["related_id"],
                file_role=relation["file_role"],
                defaults={
                    "related_code": relation["related_code"],
                    "is_primary": False,
                },
            )
        return created

    def write_log(self, log_path, log_lines):
        with open(log_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(log_lines))
            handle.write("\n")

    def write_unmapped(self, unmapped_path, rows):
        with open(unmapped_path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(row))
                handle.write("\n")
