import csv
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.management.commands.validate_manual_files import Command as ValidationCommand
from files.models import DataFile
from files.services.ingestion.file_parser import parse_ingestion_filename


class Command(BaseCommand):
    help = (
        "Plan or apply a recoverable move of empty/invalid recognized manual files "
        "to a quarantine directory. Default mode is dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="Manual files directory. Defaults to settings.MANUAL_FILES_DIR.",
        )
        parser.add_argument(
            "--quarantine-root",
            default=None,
            help=(
                "Quarantine base directory. Defaults to a manual_files_quarantine "
                "sibling directory."
            ),
        )
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Move candidate files and mark matching DataFile rows inactive.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        source_root = Path(options["path"] or settings.MANUAL_FILES_DIR).resolve()
        if not source_root.is_dir():
            raise CommandError(f"Manual files directory not found: {source_root}")

        quarantine_base = Path(
            options["quarantine_root"]
            or source_root.parent / "manual_files_quarantine"
        ).resolve()
        if quarantine_base == source_root or source_root in quarantine_base.parents:
            raise CommandError("Quarantine root must be outside the manual files directory.")
        batch_name = timezone.localdate().strftime("%Y%m%d")
        quarantine_batch = quarantine_base / batch_name
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        validator = ValidationCommand()
        rows = []
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            row = self.build_plan_row(
                source,
                source_root=source_root,
                quarantine_batch=quarantine_batch,
                validator=validator,
            )
            if row:
                rows.append(row)

        if not dry_run:
            for row in rows:
                if row["status"] != "candidate":
                    continue
                self.apply_row(row)

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"quarantine_invalid_manual_files_{timestamp}.tsv"
        self.write_report(report_path, rows)
        candidates = sum(row["status"] == "candidate" for row in rows)
        moved = sum(row["status"] == "moved" for row in rows)
        blocked = sum(row["status"] == "blocked" for row in rows)
        self.stdout.write(
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
            f"invalid_files\t{len(rows)}\n"
            f"candidate\t{candidates}\n"
            f"moved\t{moved}\n"
            f"blocked\t{blocked}\n"
            f"quarantine_batch\t{quarantine_batch}\n"
            f"report\t{report_path}"
        )

    def build_plan_row(self, source, *, source_root, quarantine_batch, validator):
        parsed = parse_ingestion_filename(source.name)
        if not parsed:
            return None

        reasons = []
        if source.stat().st_size == 0:
            reasons.append("empty_file")
        else:
            reasons.extend(
                issue
                for severity, issue in validator.validate_content(source, parsed)
                if severity == "error"
            )
        if not reasons:
            return None

        relative_path = source.relative_to(source_root)
        target = quarantine_batch / relative_path
        normalized_source = os.path.abspath(str(source))
        data_file = DataFile.objects.filter(file_path=normalized_source).first()
        blocked_reasons = []
        if target.exists():
            blocked_reasons.append("target_already_exists")
        conflicting_data_file = DataFile.objects.filter(
            file_path=os.path.abspath(str(target))
        ).exclude(id=data_file.id if data_file else None).first()
        if conflicting_data_file:
            blocked_reasons.append(f"target_datafile_exists:{conflicting_data_file.id}")

        return {
            "status": "blocked" if blocked_reasons else "candidate",
            "source_path": str(source),
            "target_path": str(target),
            "file_name": source.name,
            "file_size": source.stat().st_size,
            "file_role": parsed["file_role"],
            "accession": parsed["accession_code"],
            "datafile_id": data_file.id if data_file else "",
            "datafile_is_current": data_file.is_current if data_file else "",
            "reason": ";".join(reasons),
            "blocked_reason": ";".join(blocked_reasons),
            "database_action": (
                "move_path_and_set_inactive" if data_file else "no_matching_datafile"
            ),
        }

    def apply_row(self, row):
        source = Path(row["source_path"])
        target = Path(row["target_path"])
        if not source.is_file():
            row["status"] = "blocked"
            row["blocked_reason"] = "source_missing_at_apply"
            return
        if target.exists():
            row["status"] = "blocked"
            row["blocked_reason"] = "target_already_exists_at_apply"
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        try:
            with transaction.atomic():
                if row["datafile_id"]:
                    data_file = DataFile.objects.select_for_update().get(
                        id=row["datafile_id"]
                    )
                    data_file.file_path = os.path.abspath(str(target))
                    data_file.is_current = False
                    marker = "Quarantined after manual_files validation failure."
                    if marker not in (data_file.description or ""):
                        data_file.description = " ".join(
                            value for value in (data_file.description, marker) if value
                        )
                    data_file.save(
                        update_fields=[
                            "file_path",
                            "is_current",
                            "description",
                            "updated_at",
                        ]
                    )
        except Exception:
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(source))
            raise
        row["status"] = "moved"

    @staticmethod
    def write_report(path, rows):
        fields = [
            "status",
            "source_path",
            "target_path",
            "file_name",
            "file_size",
            "file_role",
            "accession",
            "datafile_id",
            "datafile_is_current",
            "reason",
            "blocked_reason",
            "database_action",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
