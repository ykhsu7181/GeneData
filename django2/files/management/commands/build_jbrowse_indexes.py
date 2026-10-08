import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.services.assembly_visibility import public_assembly_list_queryset
from files.services.jbrowse_index_service import (
    JBrowseIndexBuildError,
    build_jbrowse_assembly_indexes,
    inspect_jbrowse_assembly,
)


SUCCESS_STATUSES = {
    "dry_run": {"ready_for_build", "reference_only"},
    "apply": {"built"},
}
REPORT_FIELDS = (
    "assembly_id",
    "assembly_code",
    "accession",
    "annotation_id",
    "status",
    "success",
    "write_performed",
    "error",
)


class Command(BaseCommand):
    help = "Inspect one Assembly or batch-build indexes for public Assemblies."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--assembly-id", type=int)
        selection.add_argument("--all", action="store_true", dest="all_assemblies")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--output-dir")
        parser.add_argument(
            "--batch-size",
            type=int,
            help="Maximum number of pending Assemblies to process in this run.",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Continue from the mode-specific checkpoint in --report-dir.",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="With --resume, process previously failed Assemblies again.",
        )
        parser.add_argument(
            "--report-dir",
            help="Required with --all; receives JSON, TSV, and checkpoint files.",
        )
        parser.add_argument(
            "--fail-on-error",
            action="store_true",
            help="Return a command error after writing reports if this run has failures.",
        )

    def handle(self, *args, **options):
        mode = self._validate_options(options)
        if options["assembly_id"] is not None:
            return self._handle_single(options, mode)
        return self._handle_all(options, mode)

    def _validate_options(self, options):
        if options["dry_run"] == options["apply"]:
            raise CommandError("Choose exactly one of --dry-run or --apply")
        mode = "dry_run" if options["dry_run"] else "apply"

        if options["batch_size"] is not None and options["batch_size"] < 1:
            raise CommandError("--batch-size must be positive")
        batch_only = (
            options["batch_size"] is not None
            or options["resume"]
            or options["retry_failed"]
            or options["report_dir"]
            or options["fail_on_error"]
        )
        if options["assembly_id"] is not None and batch_only:
            raise CommandError("Batch options may only be used with --all")
        if options["all_assemblies"] and not options["report_dir"]:
            raise CommandError("--report-dir is required with --all")
        if options["retry_failed"] and not options["resume"]:
            raise CommandError("--retry-failed requires --resume")
        return mode

    def _handle_single(self, options, mode):
        try:
            result = self._run_one(
                options["assembly_id"],
                mode,
                options.get("output_dir"),
            )
        except JBrowseIndexBuildError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        )
        if not self._is_success(result, mode):
            raise CommandError(f"JBrowse preflight failed: {result['status']}")

    def _handle_all(self, options, mode):
        report_dir = Path(options["report_dir"]).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = report_dir / f"jbrowse_indexes_{mode}_checkpoint.json"
        checkpoint = (
            self._load_checkpoint(checkpoint_path, mode)
            if options["resume"]
            else self._new_checkpoint(mode)
        )
        self._write_json_atomic(checkpoint_path, checkpoint)

        assembly_ids = list(
            public_assembly_list_queryset()
            .order_by("id")
            .values_list("id", flat=True)
        )
        processed = checkpoint["processed"]
        pending_ids = []
        skipped_count = 0
        for assembly_id in assembly_ids:
            previous = processed.get(str(assembly_id))
            should_retry = (
                previous
                and options["retry_failed"]
                and not previous.get("success", False)
            )
            if previous and not should_retry:
                skipped_count += 1
                continue
            pending_ids.append(assembly_id)

        if options["batch_size"] is not None:
            pending_ids = pending_ids[:options["batch_size"]]

        results = []
        for assembly_id in pending_ids:
            result = self._run_one_safely(
                assembly_id,
                mode,
                options.get("output_dir"),
            )
            result["success"] = self._is_success(result, mode)
            results.append(result)
            processed[str(assembly_id)] = {
                "status": result.get("status", "unknown"),
                "success": result["success"],
                "updated_at": self._utc_now(),
            }
            checkpoint["updated_at"] = self._utc_now()
            self._write_json_atomic(checkpoint_path, checkpoint)

        successful_count = sum(1 for result in results if result["success"])
        failed_count = len(results) - successful_count
        current_id_strings = {str(assembly_id) for assembly_id in assembly_ids}
        current_entries = [
            entry
            for assembly_id, entry in processed.items()
            if assembly_id in current_id_strings
        ]
        checkpoint_successful_count = sum(
            1 for entry in current_entries if entry.get("success", False)
        )
        checkpoint_failed_count = len(current_entries) - checkpoint_successful_count
        remaining_count = sum(
            1 for assembly_id in assembly_ids if str(assembly_id) not in processed
        )
        summary = {
            "mode": mode,
            "total_assembly_count": len(assembly_ids),
            "processed_this_run": len(results),
            "successful_this_run": successful_count,
            "failed_this_run": failed_count,
            "successful_checkpoint_count": checkpoint_successful_count,
            "failed_checkpoint_count": checkpoint_failed_count,
            "skipped_from_checkpoint": skipped_count,
            "remaining_count": remaining_count,
            "checkpoint_path": str(checkpoint_path),
        }
        json_path, tsv_path = self._write_reports(report_dir, mode, summary, results)
        summary.update(json_report=str(json_path), tsv_report=str(tsv_path))
        self.stdout.write(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
        )
        if failed_count and options["fail_on_error"]:
            raise CommandError(
                f"{failed_count} JBrowse batch item(s) failed; reports were written"
            )

    @staticmethod
    def _run_one(assembly_id, mode, output_dir):
        if mode == "dry_run":
            return inspect_jbrowse_assembly(assembly_id, output_root=output_dir)
        return build_jbrowse_assembly_indexes(assembly_id, output_root=output_dir)

    def _run_one_safely(self, assembly_id, mode, output_dir):
        try:
            return self._run_one(assembly_id, mode, output_dir)
        except Exception as exc:
            return {
                "assembly_id": assembly_id,
                "status": "build_failed" if mode == "apply" else "inspection_failed",
                "write_performed": False,
                "error": str(exc),
            }

    @staticmethod
    def _is_success(result, mode):
        return result.get("status") in SUCCESS_STATUSES[mode]

    @staticmethod
    def _new_checkpoint(mode):
        now = Command._utc_now()
        return {
            "schema_version": 1,
            "mode": mode,
            "created_at": now,
            "updated_at": now,
            "processed": {},
        }

    @staticmethod
    def _load_checkpoint(path, mode):
        if not path.is_file():
            return Command._new_checkpoint(mode)
        try:
            checkpoint = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Invalid JBrowse checkpoint: {path}: {exc}") from exc
        if checkpoint.get("schema_version") != 1 or checkpoint.get("mode") != mode:
            raise CommandError(f"Incompatible JBrowse checkpoint: {path}")
        if not isinstance(checkpoint.get("processed"), dict):
            raise CommandError(f"Invalid JBrowse checkpoint records: {path}")
        return checkpoint

    @staticmethod
    def _write_json_atomic(path, payload):
        temporary_path = path.with_name(f".{path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)

    def _write_reports(self, report_dir, mode, summary, results):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        stem = f"jbrowse_indexes_{mode}_{timestamp}"
        json_path = report_dir / f"{stem}.json"
        tsv_path = report_dir / f"{stem}.tsv"
        self._write_json_atomic(
            json_path,
            {"summary": summary, "results": results},
        )
        with tsv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS, dialect="excel-tab")
            writer.writeheader()
            for result in results:
                writer.writerow({field: result.get(field, "") for field in REPORT_FIELDS})
        return json_path, tsv_path

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat()
