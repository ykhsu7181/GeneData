import csv
import os
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.management.commands.validate_manual_files import Command as ValidationCommand
from files.models import Accession, DataFile, FileRelation, FileType
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)
from files.services.ingestion.file_parser import parse_ingestion_filename


class Command(BaseCommand):
    help = (
        "Conservatively bind valid manual_files to existing unambiguous database "
        "contexts. The default is dry-run; pass --apply to write changes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", default=None)
        parser.add_argument("--output-dir", default=None)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicitly request the default preview-only mode.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the reported DataFile/FileRelation changes.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        root = Path(options["path"] or settings.MANUAL_FILES_DIR).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f"Manual files directory not found: {root}")
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        validator = ValidationCommand()
        rows = []
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            rows.append(self.process_path(path, validator=validator, dry_run=dry_run))

        counts = Counter(row["status"] for row in rows)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"bind_manual_files_{timestamp}.tsv"
        self.write_report(report_path, rows)
        mode = "DRY_RUN" if dry_run else "APPLY"
        self.stdout.write(
            f"mode\t{mode}\n"
            f"total\t{len(rows)}\n"
            f"ready\t{counts['ready']}\n"
            f"applied\t{counts['applied']}\n"
            f"skipped\t{counts['skipped']}\n"
            f"report\t{report_path}"
        )

    def process_path(self, path, *, validator, dry_run):
        parsed = parse_ingestion_filename(path.name)
        row = {
            "status": "skipped",
            "file_path": str(path),
            "file_name": path.name,
            "file_role": parsed["file_role"] if parsed else "",
            "accession": parsed["accession_code"] if parsed else "",
            "assembly_id": "",
            "annotation_id": "",
            "datafile_action": "none",
            "relation_actions": "",
            "primary_actions": "",
            "reason": "",
        }
        if not parsed:
            row["reason"] = "unrecognized_filename"
            return row
        if path.stat().st_size == 0:
            row["reason"] = "empty_file"
            return row
        content_issues = validator.validate_content(path, parsed)
        errors = [issue for severity, issue in content_issues if severity == "error"]
        if errors:
            row["reason"] = ";".join(errors)
            return row

        accession = Accession.objects.filter(accession=parsed["accession_code"]).first()
        if not accession:
            row["reason"] = "unknown_accession"
            return row
        assemblies = list(accession.assemblies.all()[:2])
        if len(assemblies) != 1:
            row["reason"] = "missing_assembly" if not assemblies else "ambiguous_assembly"
            return row
        assembly = assemblies[0]
        row["assembly_id"] = assembly.id

        annotation = None
        if parsed["file_role"] == "annotation":
            annotations = list(assembly.annotations.all()[:2])
            if len(annotations) != 1:
                row["reason"] = (
                    "missing_annotation" if not annotations else "ambiguous_annotation"
                )
                return row
            annotation = annotations[0]
            row["annotation_id"] = annotation.id

        relation_specs = [
            ("accession", accession.id, accession.accession, False),
            (
                "assembly",
                assembly.id,
                assembly.assembly_code or assembly.name,
                parsed["file_role"] in {"genome", "genome_fasta"},
            ),
        ]
        if annotation:
            relation_specs.append(
                (
                    "annotation",
                    annotation.id,
                    annotation.annotation_code or annotation.name,
                    True,
                )
            )

        existing = DataFile.objects.filter(file_path=os.path.abspath(str(path))).first()
        row["datafile_action"] = "reuse" if existing else "create"
        relation_actions = []
        primary_actions = []
        for related_type, related_id, _, is_primary in relation_specs:
            exists = bool(
                existing
                and FileRelation.objects.filter(
                    file=existing,
                    related_type=related_type,
                    related_id=str(related_id),
                    file_role=parsed["file_role"],
                ).exists()
            )
            relation_actions.append(
                f"{'reuse' if exists else 'create'}:{related_type}:{related_id}"
            )
            if is_primary:
                primary_actions.append(f"set:{related_type}:{related_id}")
        row["relation_actions"] = ";".join(relation_actions)
        row["primary_actions"] = ";".join(primary_actions)

        if dry_run:
            row["status"] = "ready"
            row["reason"] = "dry_run_no_changes"
            return row

        with transaction.atomic():
            file_type = self.get_or_create_file_type(parsed["extension"])
            data_file, _, _, _ = create_or_get_datafile_from_path(
                file_path=str(path),
                file_name=path.name,
                file_type=file_type,
                file_size=path.stat().st_size,
                description=(
                    "Imported from a public database; manual_files is the local "
                    "storage location."
                ),
            )
            if not data_file.is_current:
                data_file.is_current = True
                data_file.save(update_fields=["is_current", "updated_at"])
            for related_type, related_id, related_code, is_primary in relation_specs:
                relation, _, _ = create_or_get_file_relation(
                    data_file=data_file,
                    related_type=related_type,
                    related_id=related_id,
                    related_code=related_code,
                    file_role=parsed["file_role"],
                )
                if is_primary:
                    FileRelation.objects.filter(
                        related_type=related_type,
                        related_id=str(related_id),
                        file_role=parsed["file_role"],
                        is_primary=True,
                    ).exclude(pk=relation.pk).update(is_primary=False)
                    if not relation.is_primary:
                        relation.is_primary = True
                        relation.save(update_fields=["is_primary", "updated_at"])
        row["status"] = "applied"
        row["reason"] = ""
        return row

    @staticmethod
    def get_or_create_file_type(extension):
        file_type = FileType.objects.filter(extension=extension).first()
        if file_type:
            return file_type
        return FileType.objects.create(
            name=extension.upper() if extension else "UNKNOWN",
            extension=extension,
        )

    @staticmethod
    def write_report(path, rows):
        fields = [
            "status", "file_path", "file_name", "file_role", "accession",
            "assembly_id", "annotation_id", "datafile_action",
            "relation_actions", "primary_actions", "reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
