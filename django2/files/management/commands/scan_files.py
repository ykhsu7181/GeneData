import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from files.models import Accession, FileType
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
    normalize_file_path,
)

SCAN_FILE_CATEGORIES = {
    "variableBlocks",
    "genome",
    "transcriptome.all",
    "transcriptome.root",
    "transcriptome.stem",
    "transcriptome.leaf",
    "transcriptome.panicles",
    "transcriptome.shoot",
    "miRNA",
    "tRNA",
    "rRNA",
    "codon",
    "centromere",
    "TEs",
    "annotation",
    "coreBlocks",
    "other",
}

TISSUE_TYPES = {"all", "root", "stem", "leaf", "panicles", "shoot"}


class Command(BaseCommand):
    help = 'Scan manual files directory and sync file records.'

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="Directory to scan. Defaults to settings.MANUAL_FILES_DIR.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of filesystem files processed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes and write reports without changing database rows.",
        )
        parser.add_argument(
            "--write-mode",
            choices=["new"],
            default="new",
            help="Only 'new' is supported. scan_files writes DataFile/FileRelation only.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for scan_files reports. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        directory = options["path"] or settings.MANUAL_FILES_DIR
        directory = normalize_file_path(directory)
        write_mode = options["write_mode"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        output_dir = options["output_dir"] or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)

        if limit is not None and limit < 1:
            raise CommandError("--limit must be greater than 0.")

        if write_mode != "new":
            raise CommandError(
                f"--write-mode {write_mode} is unsupported. "
                "scan_files is new-only; use --write-mode new or omit the option."
            )

        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Manual files directory not found: {directory}'))
            return

        stats = {
            "scanned_count": 0,
            "created_datafile_count": 0,
            "reused_datafile_count": 0,
            "created_filerelation_count": 0,
            "reused_filerelation_count": 0,
            "unmapped_count": 0,
            "warnings": 0,
        }
        log_lines = [
            f"started_at\t{timezone.now().isoformat()}",
            f"path\t{directory}",
            f"write_mode\t{write_mode}",
            f"dry_run\t{dry_run}",
            f"limit\t{limit if limit is not None else ''}",
        ]
        unmapped_rows = [["file_path", "file_name", "category", "accession_code", "warnings"]]

        self.stdout.write(f'Scanning manual files in: {directory}')

        existing_files = self.collect_existing_files(directory, limit=limit)

        extension_map = {ft.extension: ft for ft in FileType.objects.all()}

        for file_path in existing_files:
            stats["scanned_count"] += 1
            filename = os.path.basename(file_path)
            parsed = self.parse_file(filename)
            if not parsed:
                stats["warnings"] += 1
                stats["unmapped_count"] += 1
                unmapped_rows.append([file_path, filename, "", "", "invalid_name_or_category"])
                continue

            category = parsed["category"]
            accession_code = parsed["accession_code"]
            file_type = self.get_file_type(filename, extension_map, dry_run=dry_run)
            context = self.resolve_context(accession_code, category)

            if not context["accession"]:
                stats["unmapped_count"] += 1
                unmapped_rows.append([file_path, filename, category, accession_code, "no_related_object"])

            self.write_new_records(
                file_path=file_path,
                filename=filename,
                category=category,
                file_type=file_type,
                context=context,
                dry_run=dry_run,
                stats=stats,
            )

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(output_dir, f"scan_files_log_{timestamp}.txt")
        unmapped_path = os.path.join(output_dir, f"scan_files_unmapped_{timestamp}.tsv")

        log_lines.extend(
            [
                f"scanned_count\t{stats['scanned_count']}",
                f"created_datafile_count\t{stats['created_datafile_count']}",
                f"reused_datafile_count\t{stats['reused_datafile_count']}",
                f"created_filerelation_count\t{stats['created_filerelation_count']}",
                f"reused_filerelation_count\t{stats['reused_filerelation_count']}",
                f"unmapped_count\t{stats['unmapped_count']}",
                f"warnings\t{stats['warnings']}",
                f"finished_at\t{timezone.now().isoformat()}",
            ]
        )
        self.write_report(log_path, log_lines)
        self.write_tsv(unmapped_path, unmapped_rows)

        self.stdout.write(
            self.style.SUCCESS(
                "Scan completed. "
                f"scanned_count={stats['scanned_count']}, "
                f"created_datafile_count={stats['created_datafile_count']}, "
                f"created_filerelation_count={stats['created_filerelation_count']}, "
                f"unmapped_count={stats['unmapped_count']}. "
                f"Reports: {log_path}, {unmapped_path}"
            )
        )

    def collect_existing_files(self, directory, limit=None):
        existing_files = []
        for root, _, files in os.walk(directory):
            for filename in sorted(files):
                existing_files.append(normalize_file_path(os.path.join(root, filename)))
                if limit is not None and len(existing_files) >= limit:
                    return existing_files
        return existing_files

    def parse_file(self, filename):
        parts = filename.split('.')
        if len(parts) < 3:
            return None

        if parts[0] == 'transcriptome' and parts[1] in TISSUE_TYPES and len(parts) >= 4:
            category = f"transcriptome.{parts[1]}"
            accession_code = parts[2]
        else:
            category = parts[0]
            accession_code = parts[1]

        if category not in SCAN_FILE_CATEGORIES or not accession_code:
            return None
        return {"category": category, "accession_code": accession_code}

    def get_file_type(self, filename, extension_map, *, dry_run):
        parts = filename.split('.')
        extension = parts[-1] if len(parts) > 1 else ''
        if extension in ['gz', 'zip', 'bz2', 'xz'] and len(parts) > 2:
            extension = f"{parts[-2]}.{parts[-1]}"

        file_type = extension_map.get(extension)
        if file_type:
            return file_type

        file_type = FileType(
            name=extension.upper() if extension else 'UNKNOWN',
            extension=extension,
        )
        if not dry_run:
            file_type.save()
        extension_map[extension] = file_type
        return file_type

    def resolve_context(self, accession_code, category):
        accession = Accession.objects.filter(accession=accession_code).first()
        assembly = None
        annotation = None
        if accession:
            assembly = accession.default_assembly or accession.assemblies.first()
            if assembly and category == "annotation":
                annotation = assembly.default_annotation or assembly.annotations.first()
        return {
            "accession": accession,
            "assembly": assembly,
            "annotation": annotation,
        }

    def write_new_records(
        self,
        *,
        file_path,
        filename,
        category,
        file_type,
        context,
        dry_run,
        stats,
    ):
        data_file, created, reused, _ = create_or_get_datafile_from_path(
            file_path=file_path,
            file_name=filename,
            file_type=file_type,
            dry_run=dry_run,
        )
        if created:
            stats["created_datafile_count"] += 1
        elif reused:
            stats["reused_datafile_count"] += 1

        relation_specs = self.build_relation_specs(context, category)
        if not relation_specs:
            return

        for relation in relation_specs:
            _, relation_created, relation_reused = create_or_get_file_relation(
                data_file=data_file,
                related_type=relation["related_type"],
                related_id=relation["related_id"],
                related_code=relation["related_code"],
                file_role=category,
                dry_run=dry_run,
            )
            if relation_created:
                stats["created_filerelation_count"] += 1
            elif relation_reused:
                stats["reused_filerelation_count"] += 1

    def build_relation_specs(self, context, category):
        relations = []
        accession = context["accession"]
        assembly = context["assembly"]
        annotation = context["annotation"]

        if accession:
            relations.append(
                {
                    "related_type": "accession",
                    "related_id": accession.id,
                    "related_code": accession.accession,
                }
            )
        if assembly:
            relations.append(
                {
                    "related_type": "assembly",
                    "related_id": assembly.id,
                    "related_code": assembly.name,
                }
            )
        if annotation and category == "annotation":
            relations.append(
                {
                    "related_type": "annotation",
                    "related_id": annotation.id,
                    "related_code": annotation.name,
                }
            )
        return relations

    def write_report(self, log_path, log_lines):
        with open(log_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(log_lines))
            handle.write("\n")

    def write_tsv(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")
