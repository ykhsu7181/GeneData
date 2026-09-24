import csv
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.models import Accession, Annotation, Assembly, FileRelation, FileType
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)
from files.services.ingestion.roles import validate_file_role


REQUIRED_COLUMNS = {
    "file_path",
    "file_role",
    "accession",
    "assembly_code",
    "annotation_code",
    "sample_code",
    "dataset_code",
    "md5",
}
COMPRESSION_EXTENSIONS = {"bz2", "gz", "xz", "zip"}


class Command(BaseCommand):
    help = (
        "Import an explicit files.full.tsv manifest from MANUAL_FILES_DIR. "
        "The command never infers an Assembly when assembly_code is supplied, "
        "defaults to dry-run, and writes an audit report."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument(
            "--manual-files-dir",
            default=None,
            help="Allowed storage root. Defaults to settings.MANUAL_FILES_DIR.",
        )
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        manifest_path = Path(options["file"]).expanduser().resolve()
        manual_root = Path(
            options["manual_files_dir"] or settings.MANUAL_FILES_DIR
        ).expanduser().resolve()
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not manifest_path.is_file():
            raise CommandError(f"File manifest not found: {manifest_path}")
        if not manual_root.is_dir():
            raise CommandError(f"manual_files directory not found: {manual_root}")

        rows = self.load_rows(manifest_path)
        planned, report_rows = self.preflight(rows, manual_root)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"hierarchy_file_manifest_{timestamp}.tsv"
        error_count = sum(row["status"] == "error" for row in report_rows)
        if error_count:
            self.write_report(report_path, report_rows)
            self.stdout.write(
                "mode\tDRY_RUN\n"
                "status\tBLOCKED\n"
                f"total\t{len(rows)}\n"
                f"errors\t{error_count}\n"
                f"report\t{report_path}"
            )
            return

        stats = Counter()
        with transaction.atomic():
            for item in planned:
                action = self.apply_row(item, stats)
                item["report"]["status"] = "ready" if dry_run else "applied"
                item["report"]["action"] = action
            if dry_run:
                transaction.set_rollback(True)

        self.write_report(report_path, report_rows)
        status = "READY" if dry_run else "APPLIED"
        self.stdout.write(
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
            f"status\t{status}\n"
            f"total\t{len(rows)}\n"
            f"datafile_created\t{stats['datafile_created']}\n"
            f"datafile_reused\t{stats['datafile_reused']}\n"
            f"datafile_updated\t{stats['datafile_updated']}\n"
            f"relation_created\t{stats['relation_created']}\n"
            f"relation_reused\t{stats['relation_reused']}\n"
            "errors\t0\n"
            f"report\t{report_path}"
        )

    @staticmethod
    def load_rows(path):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            columns = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise CommandError(
                    "File manifest is missing columns: " + ", ".join(sorted(missing))
                )
            return [
                {
                    key: (value or "").strip()
                    for key, value in row.items()
                }
                for row in reader
            ]

    def preflight(self, rows, manual_root):
        planned = []
        report_rows = []
        identities = set()
        accessions = {
            item.accession: item
            for item in Accession.objects.all()
        }
        assemblies = {
            item.assembly_code: item
            for item in Assembly.objects.select_related("accession")
            if item.assembly_code
        }
        annotations = {
            item.annotation_code: item
            for item in Annotation.objects.select_related("assembly")
            if item.annotation_code
        }

        for line_number, row in enumerate(rows, start=2):
            reasons = []
            role = row.get("file_role", "")
            try:
                validate_file_role(role)
            except ValueError:
                reasons.append("unknown_file_role")

            raw_path = Path(row.get("file_path", ""))
            path = raw_path.resolve() if raw_path.is_absolute() else (manual_root / raw_path).resolve()
            if not path.is_relative_to(manual_root):
                reasons.append("path_outside_manual_files")
            elif not path.is_file():
                reasons.append("file_not_found")
            elif path.stat().st_size == 0:
                reasons.append("empty_file")

            identity = (str(path), role)
            if identity in identities:
                reasons.append("duplicate_file_role")
            identities.add(identity)

            accession = accessions.get(row.get("accession"))
            assembly = assemblies.get(row.get("assembly_code"))
            annotation = annotations.get(row.get("annotation_code")) if row.get("annotation_code") else None
            if not accession:
                reasons.append("unknown_accession")
            if not assembly:
                reasons.append("unknown_assembly")
            elif accession and assembly.accession_id != accession.id:
                reasons.append("assembly_accession_mismatch")
            if row.get("annotation_code"):
                if not annotation:
                    reasons.append("unknown_annotation")
                elif assembly and annotation.assembly_id != assembly.id:
                    reasons.append("annotation_assembly_mismatch")
            if role == "annotation" and not row.get("annotation_code"):
                reasons.append("annotation_code_required")
            if row.get("sample_code") or row.get("dataset_code"):
                reasons.append("unsupported_non_hierarchy_target")

            report = {
                "status": "error" if reasons else "planned",
                "line_number": line_number,
                "file_path": str(path),
                "file_role": role,
                "accession": row.get("accession", ""),
                "assembly_code": row.get("assembly_code", ""),
                "annotation_code": row.get("annotation_code", ""),
                "action": "blocked" if reasons else "pending",
                "reason": ";".join(reasons),
            }
            report_rows.append(report)
            if not reasons:
                planned.append({
                    "row": row,
                    "path": path,
                    "accession": accession,
                    "assembly": assembly,
                    "annotation": annotation,
                    "report": report,
                })
        return planned, report_rows

    def apply_row(self, item, stats):
        row = item["row"]
        path = item["path"]
        file_type = self.resolve_file_type(path)
        data_file, created, reused, updated = create_or_get_datafile_from_path(
            file_path=str(path),
            file_name=path.name,
            file_type=file_type,
            file_size=path.stat().st_size,
            md5=row.get("md5") or None,
            description="Imported from an explicit hierarchy file manifest.",
        )
        stats["datafile_created"] += int(created)
        stats["datafile_reused"] += int(reused)
        stats["datafile_updated"] += int(updated)

        specs = [
            ("accession", item["accession"], item["accession"].accession, False),
            ("assembly", item["assembly"], item["assembly"].assembly_code, True),
        ]
        if item["annotation"]:
            specs.append(
                (
                    "annotation",
                    item["annotation"],
                    item["annotation"].annotation_code,
                    True,
                )
            )
        for related_type, target, code, primary in specs:
            relation, relation_created, relation_reused = create_or_get_file_relation(
                data_file=data_file,
                related_type=related_type,
                related_id=target.id,
                related_code=code,
                file_role=row["file_role"],
            )
            stats["relation_created"] += int(relation_created)
            stats["relation_reused"] += int(relation_reused)
            if primary:
                FileRelation.objects.filter(
                    related_type=related_type,
                    related_id=str(target.id),
                    file_role=row["file_role"],
                    is_primary=True,
                ).exclude(id=relation.id).update(is_primary=False)
                if not relation.is_primary:
                    relation.is_primary = True
                    relation.save(update_fields=["is_primary", "updated_at"])
        return "created" if created else "reused"

    @staticmethod
    def resolve_file_type(path):
        suffixes = [suffix.lstrip(".") for suffix in path.suffixes]
        extension = suffixes[-1] if suffixes else ""
        if extension.lower() in COMPRESSION_EXTENSIONS and len(suffixes) > 1:
            extension = f"{suffixes[-2]}.{extension}"
        file_type = FileType.objects.filter(extension__iexact=extension).order_by("id").first()
        if file_type:
            return file_type
        return FileType.objects.create(
            name=extension.upper() if extension else "UNKNOWN",
            extension=extension,
        )

    @staticmethod
    def write_report(path, rows):
        fields = [
            "status",
            "line_number",
            "file_path",
            "file_role",
            "accession",
            "assembly_code",
            "annotation_code",
            "action",
            "reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
