import csv
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from files.management.commands.cleanup_placeholder_hierarchy import (
    Command as CleanupCommand,
)
from files.management.commands.import_annotation_manifest import (
    Command as AnnotationManifestCommand,
)
from files.management.commands.import_assembly_manifest import (
    Command as AssemblyManifestCommand,
)
from files.management.commands.validate_manual_files import (
    Command as ValidationCommand,
)
from files.models import Accession, Annotation, Assembly, FileRelation, FileType
from files.services.file_write_service import (
    create_or_get_datafile_from_path,
    create_or_get_file_relation,
)
from files.services.import_log_service import manifest_sha256
from files.services.ingestion.file_parser import parse_ingestion_filename
from files.services.ingestion.metadata_policy import plan_fill_blank_metadata


class Command(BaseCommand):
    help = (
        "Atomically import an incremental Assembly/Annotation manifest batch, "
        "bind its real files, select defaults and clean safe placeholders only "
        "for accessions in the batch. Default mode is dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--assembly-file", required=True)
        parser.add_argument("--annotation-file", default=None)
        parser.add_argument(
            "--manual-files-dir",
            default=None,
            help="Defaults to settings.MANUAL_FILES_DIR.",
        )
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--batch-id", default="")
        parser.add_argument("--source", default="public_database_import")
        parser.add_argument("--source-version", default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        dry_run = not options["apply"]
        assembly_path = Path(options["assembly_file"]).resolve()
        annotation_path = (
            Path(options["annotation_file"]).resolve()
            if options.get("annotation_file")
            else None
        )
        manual_root = Path(
            options["manual_files_dir"] or settings.MANUAL_FILES_DIR
        ).resolve()
        output_dir = Path(
            options["output_dir"] or Path(settings.BASE_DIR) / "audit_reports"
        ).resolve()
        if not assembly_path.is_file():
            raise CommandError(f"Assembly manifest not found: {assembly_path}")
        if annotation_path and not annotation_path.is_file():
            raise CommandError(f"Annotation manifest not found: {annotation_path}")
        if not manual_root.is_dir():
            raise CommandError(f"Manual files directory not found: {manual_root}")
        output_dir.mkdir(parents=True, exist_ok=True)

        assembly_loader = AssemblyManifestCommand()
        annotation_loader = AnnotationManifestCommand()
        assembly_rows = assembly_loader._load_rows(assembly_path)
        annotation_rows = (
            annotation_loader._load_rows(annotation_path) if annotation_path else []
        )

        errors, planned_files = self.preflight(
            assembly_rows,
            annotation_rows,
            manual_root=manual_root,
        )
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"incremental_hierarchy_batch_{timestamp}.tsv"
        summary_path = output_dir / f"incremental_hierarchy_batch_{timestamp}.txt"
        if errors:
            self.write_report(report_path, errors)
            self.write_summary(
                summary_path,
                options=options,
                dry_run=dry_run,
                assembly_path=assembly_path,
                annotation_path=annotation_path,
                stats={"errors": len(errors), "status": "BLOCKED"},
            )
            self.stdout.write(
                f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
                f"status\tBLOCKED\nerrors\t{len(errors)}\n"
                f"report\t{report_path}\nsummary\t{summary_path}"
            )
            return

        stats = Counter()
        actions = []
        accession_codes = {row["accession"] for row in assembly_rows}
        with transaction.atomic():
            assemblies = {}
            for row in assembly_rows:
                assembly, action = self.upsert_assembly(row)
                assemblies[row["assembly_code"]] = assembly
                stats[f"assembly_{action}"] += 1
                actions.append(self.action_row("assembly", row, action))

            annotations = {}
            for row in annotation_rows:
                annotation, action = self.upsert_annotation(
                    row,
                    assembly=assemblies.get(row["assembly_code"])
                    or Assembly.objects.get(assembly_code=row["assembly_code"]),
                )
                annotations[row["annotation_code"]] = annotation
                stats[f"annotation_{action}"] += 1
                actions.append(self.action_row("annotation", row, action))

            for item in planned_files:
                assembly = assemblies[item["assembly_code"]]
                annotation = (
                    annotations[item["annotation_code"]]
                    if item.get("annotation_code")
                    else None
                )
                file_action = self.bind_file(
                    path=item["path"],
                    parsed=item["parsed"],
                    accession=assembly.accession,
                    assembly=assembly,
                    annotation=annotation,
                )
                stats[f"file_{file_action}"] += 1

            for assembly in assemblies.values():
                Assembly.objects.filter(accession=assembly.accession).exclude(
                    id=assembly.id
                ).update(is_default=False)
                if not assembly.is_default:
                    assembly.is_default = True
                    assembly.save(update_fields=["is_default", "updated_at"])
            for annotation in annotations.values():
                Annotation.objects.filter(assembly=annotation.assembly).exclude(
                    id=annotation.id
                ).update(is_default=False)
                if not annotation.is_default:
                    annotation.is_default = True
                    annotation.save(update_fields=["is_default", "updated_at"])

            cleanup = CleanupCommand()
            _, assembly_candidates = cleanup.audit_assemblies(
                accession_codes=accession_codes
            )
            _, annotation_candidates = cleanup.audit_annotations(
                parent_assembly_candidate_ids={item.id for item in assembly_candidates},
                accession_codes=accession_codes,
            )
            stats["placeholder_assemblies_removed"] = len(assembly_candidates)
            stats["placeholder_annotations_removed"] = len(annotation_candidates) + sum(
                item.annotations.filter(name="default-annotation").count()
                for item in assembly_candidates
            )
            cleanup.apply_cleanup(assembly_candidates, annotation_candidates)

            if dry_run:
                transaction.set_rollback(True)

        stats["errors"] = 0
        stats["status"] = "READY" if dry_run else "APPLIED"
        self.write_report(report_path, actions)
        self.write_summary(
            summary_path,
            options=options,
            dry_run=dry_run,
            assembly_path=assembly_path,
            annotation_path=annotation_path,
            stats=stats,
        )
        self.stdout.write(
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}\n"
            f"status\t{stats['status']}\n"
            f"accessions\t{len(accession_codes)}\n"
            f"assemblies\t{len(assembly_rows)}\n"
            f"annotations\t{len(annotation_rows)}\n"
            f"files\t{len(planned_files)}\n"
            f"placeholder_assemblies_removed\t{stats['placeholder_assemblies_removed']}\n"
            f"placeholder_annotations_removed\t{stats['placeholder_annotations_removed']}\n"
            f"report\t{report_path}\nsummary\t{summary_path}"
        )

    def preflight(self, assembly_rows, annotation_rows, *, manual_root):
        errors = []
        planned_files = []
        seen_assembly_codes = set()
        seen_accessions = set()
        planned_assemblies = {}
        validator = ValidationCommand()

        for line_number, row in enumerate(assembly_rows, start=2):
            code = row["assembly_code"]
            accession_code = row["accession"]
            if not code or not accession_code:
                errors.append(self.error("assembly", line_number, accession_code, code, "missing_identity"))
                continue
            if code in seen_assembly_codes:
                errors.append(self.error("assembly", line_number, accession_code, code, "duplicate_assembly_code_in_batch"))
            if accession_code in seen_accessions:
                errors.append(self.error("assembly", line_number, accession_code, code, "multiple_assemblies_for_accession_in_batch"))
            seen_assembly_codes.add(code)
            seen_accessions.add(accession_code)
            accession = Accession.objects.filter(accession=accession_code).first()
            if not accession:
                errors.append(self.error("assembly", line_number, accession_code, code, "accession_not_found"))
                continue
            try:
                metadata = AssemblyManifestCommand._metadata_values(row)
            except ValueError as exc:
                errors.append(self.error("assembly", line_number, accession_code, code, str(exc)))
                continue
            existing = Assembly.objects.filter(assembly_code=code).first()
            if existing and existing.accession_id != accession.id:
                errors.append(self.error("assembly", line_number, accession_code, code, "assembly_code_identity_conflict"))
                continue
            if existing:
                _, conflicts = plan_fill_blank_metadata(existing, metadata)
                if conflicts:
                    fields = ",".join(item["field"] for item in conflicts)
                    errors.append(self.error("assembly", line_number, accession_code, code, f"metadata_conflict:{fields}"))
            planned_assemblies[code] = accession
            file_result = self.validate_manifest_file(
                row.get("file_name", ""),
                expected_accession=accession_code,
                expected_roles={"genome", "genome_fasta"},
                manual_root=manual_root,
                validator=validator,
            )
            if file_result["error"]:
                errors.append(self.error("assembly", line_number, accession_code, code, file_result["error"]))
            else:
                planned_files.append({
                    "path": file_result["path"],
                    "parsed": file_result["parsed"],
                    "assembly_code": code,
                    "annotation_code": "",
                })

        seen_annotation_codes = set()
        for line_number, row in enumerate(annotation_rows, start=2):
            code = row["annotation_code"]
            accession_code = row["accession"]
            assembly_code = row["assembly_code"]
            if not code or not accession_code or not assembly_code:
                errors.append(self.error("annotation", line_number, accession_code, code, "missing_identity"))
                continue
            if code in seen_annotation_codes:
                errors.append(self.error("annotation", line_number, accession_code, code, "duplicate_annotation_code_in_batch"))
            seen_annotation_codes.add(code)
            accession = Accession.objects.filter(accession=accession_code).first()
            planned_accession = planned_assemblies.get(assembly_code)
            existing_assembly = Assembly.objects.filter(assembly_code=assembly_code).first()
            assembly_accession_id = (
                planned_accession.id if planned_accession
                else existing_assembly.accession_id if existing_assembly
                else None
            )
            if not accession:
                errors.append(self.error("annotation", line_number, accession_code, code, "accession_not_found"))
                continue
            if assembly_accession_id != accession.id:
                errors.append(self.error("annotation", line_number, accession_code, code, "assembly_not_in_batch_or_wrong_accession"))
                continue
            existing = Annotation.objects.filter(annotation_code=code).first()
            if existing and (
                existing.assembly.assembly_code != assembly_code
                or existing.accession_id not in (None, accession.id)
            ):
                errors.append(self.error("annotation", line_number, accession_code, code, "annotation_code_identity_conflict"))
                continue
            if existing:
                _, conflicts = plan_fill_blank_metadata(
                    existing,
                    AnnotationManifestCommand._metadata_values(row, accession),
                )
                if conflicts:
                    fields = ",".join(item["field"] for item in conflicts)
                    errors.append(self.error("annotation", line_number, accession_code, code, f"metadata_conflict:{fields}"))
            file_result = self.validate_manifest_file(
                row.get("file_name", ""),
                expected_accession=accession_code,
                expected_roles={"annotation"},
                manual_root=manual_root,
                validator=validator,
            )
            if file_result["error"]:
                errors.append(self.error("annotation", line_number, accession_code, code, file_result["error"]))
            else:
                planned_files.append({
                    "path": file_result["path"],
                    "parsed": file_result["parsed"],
                    "assembly_code": assembly_code,
                    "annotation_code": code,
                })
        return errors, planned_files

    def validate_manifest_file(
        self,
        file_name,
        *,
        expected_accession,
        expected_roles,
        manual_root,
        validator,
    ):
        if not file_name:
            return {"error": "file_name_is_required", "path": None, "parsed": None}
        path = (manual_root / file_name).resolve()
        try:
            path.relative_to(manual_root)
        except ValueError:
            return {"error": "file_path_escapes_manual_files", "path": path, "parsed": None}
        if not path.is_file():
            return {"error": f"file_not_found:{file_name}", "path": path, "parsed": None}
        if path.stat().st_size == 0:
            return {"error": f"empty_file:{file_name}", "path": path, "parsed": None}
        parsed = parse_ingestion_filename(path.name)
        if not parsed:
            return {"error": f"unrecognized_filename:{file_name}", "path": path, "parsed": None}
        if parsed["accession_code"] != expected_accession:
            return {"error": f"filename_accession_mismatch:{file_name}", "path": path, "parsed": parsed}
        if parsed["file_role"] not in expected_roles:
            return {"error": f"unexpected_file_role:{parsed['file_role']}", "path": path, "parsed": parsed}
        issues = validator.validate_content(path, parsed)
        errors = [issue for severity, issue in issues if severity == "error"]
        return {
            "error": ";".join(errors),
            "path": path,
            "parsed": parsed,
        }

    def upsert_assembly(self, row):
        accession = Accession.objects.get(accession=row["accession"])
        metadata = AssemblyManifestCommand._metadata_values(row)
        assembly = Assembly.objects.filter(assembly_code=row["assembly_code"]).first()
        if not assembly:
            return Assembly.objects.create(
                assembly_code=row["assembly_code"],
                **AssemblyManifestCommand._defaults(row, accession, metadata),
            ), "created"
        updates, _ = plan_fill_blank_metadata(assembly, metadata)
        if updates:
            for field, value in updates.items():
                setattr(assembly, field, value)
            assembly.save(update_fields=[*updates, "updated_at"])
            return assembly, "updated"
        return assembly, "reused"

    def upsert_annotation(self, row, *, assembly):
        accession = assembly.accession
        annotation = Annotation.objects.filter(annotation_code=row["annotation_code"]).first()
        if not annotation:
            return Annotation.objects.create(
                annotation_code=row["annotation_code"],
                **AnnotationManifestCommand._defaults(row, accession, assembly),
            ), "created"
        metadata = AnnotationManifestCommand._metadata_values(row, accession)
        updates, _ = plan_fill_blank_metadata(annotation, metadata)
        if updates:
            for field, value in updates.items():
                setattr(annotation, field, value)
            annotation.save(update_fields=[*updates, "updated_at"])
            return annotation, "updated"
        return annotation, "reused"

    def bind_file(self, *, path, parsed, accession, assembly, annotation):
        extension = parsed["extension"]
        file_type = FileType.objects.filter(extension=extension).first()
        if not file_type:
            file_type = FileType.objects.create(
                name=extension.upper(),
                extension=extension,
            )
        data_file, created, _, _ = create_or_get_datafile_from_path(
            file_path=str(path),
            file_name=path.name,
            file_type=file_type,
            file_size=path.stat().st_size,
            description="Imported from a public database; manual_files is local storage.",
        )
        if not data_file.is_current:
            data_file.is_current = True
            data_file.save(update_fields=["is_current", "updated_at"])
        specs = [
            ("accession", accession.id, accession.accession, False),
            ("assembly", assembly.id, assembly.assembly_code or assembly.name, True),
        ]
        if annotation:
            specs.append(
                (
                    "annotation",
                    annotation.id,
                    annotation.annotation_code or annotation.name,
                    True,
                )
            )
        for related_type, related_id, related_code, primary in specs:
            relation, _, _ = create_or_get_file_relation(
                data_file=data_file,
                related_type=related_type,
                related_id=related_id,
                related_code=related_code,
                file_role=parsed["file_role"],
            )
            if primary:
                FileRelation.objects.filter(
                    related_type=related_type,
                    related_id=str(related_id),
                    file_role=parsed["file_role"],
                    is_primary=True,
                ).exclude(id=relation.id).update(is_primary=False)
                if not relation.is_primary:
                    relation.is_primary = True
                    relation.save(update_fields=["is_primary", "updated_at"])
        return "created" if created else "reused"

    @staticmethod
    def error(object_type, line_number, accession, object_code, reason):
        return {
            "status": "error",
            "object_type": object_type,
            "line_number": line_number,
            "accession": accession,
            "object_code": object_code,
            "action": "blocked",
            "reason": reason,
        }

    @staticmethod
    def action_row(object_type, row, action):
        code_field = "assembly_code" if object_type == "assembly" else "annotation_code"
        return {
            "status": "ready",
            "object_type": object_type,
            "line_number": "",
            "accession": row["accession"],
            "object_code": row[code_field],
            "action": action,
            "reason": "",
        }

    @staticmethod
    def write_report(path, rows):
        fields = [
            "status", "object_type", "line_number", "accession",
            "object_code", "action", "reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def write_summary(
        path,
        *,
        options,
        dry_run,
        assembly_path,
        annotation_path,
        stats,
    ):
        lines = [
            f"generated_at\t{timezone.now().isoformat()}",
            f"mode\t{'DRY_RUN' if dry_run else 'APPLY'}",
            f"batch_id\t{options.get('batch_id', '')}",
            f"source\t{options.get('source', '')}",
            f"source_version\t{options.get('source_version', '')}",
            f"assembly_manifest\t{assembly_path}",
            f"assembly_manifest_sha256\t{manifest_sha256(assembly_path)}",
            f"annotation_manifest\t{annotation_path or ''}",
            f"annotation_manifest_sha256\t{manifest_sha256(annotation_path) if annotation_path else ''}",
        ]
        lines.extend(f"{key}\t{value}" for key, value in stats.items())
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
