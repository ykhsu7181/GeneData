import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.services.assembly_visibility import public_assembly_list_queryset
from files.services.reference_name_service import (
    ReferenceNameError,
    build_refname_mapping,
    inspect_refname_mapping,
    select_mapping_inputs,
)


class Command(BaseCommand):
    help = "Inspect or backfill Assembly-level JBrowse refName mapping assets."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--assembly-id", type=int)
        selection.add_argument("--all", action="store_true", dest="all_assemblies")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--output-dir")
        parser.add_argument("--report-dir")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--retry-failed", action="store_true")
        parser.add_argument("--batch-size", type=int)
        parser.add_argument("--rate-limit-seconds", type=float, default=0.0)

    def handle(self, *args, **options):
        self._validate(options)
        mode = "apply" if options["apply"] else "dry_run"
        if options["assembly_id"] is not None:
            result = self._run_one_safely(
                options["assembly_id"], mode, options.get("output_dir")
            )
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            if result.get("status") not in {"built", "ready_for_build"}:
                raise CommandError(f"refName mapping failed: {result.get('status')}")
            return

        report_dir = Path(options["report_dir"]).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = report_dir / f"jbrowse_refnames_{mode}_checkpoint.json"
        checkpoint = self._load_checkpoint(checkpoint_path, mode) if options["resume"] else {
            "schema_version": 1,
            "mode": mode,
            "processed": {},
        }
        assembly_ids = list(
            public_assembly_list_queryset().order_by("id").values_list("id", flat=True)
        )
        pending = []
        for assembly_id in assembly_ids:
            previous = checkpoint["processed"].get(str(assembly_id))
            if previous and not (options["retry_failed"] and not previous.get("success")):
                continue
            pending.append(assembly_id)
        if options["batch_size"]:
            pending = pending[: options["batch_size"]]

        results = []
        for index, assembly_id in enumerate(pending):
            result = self._run_one_safely(assembly_id, mode, options.get("output_dir"))
            result["success"] = result.get("status") in {"built", "ready_for_build"}
            results.append(result)
            checkpoint["processed"][str(assembly_id)] = {
                "success": result["success"],
                "status": result.get("status"),
                "updated_at": self._now(),
            }
            self._write_json_atomic(checkpoint_path, checkpoint)
            if index + 1 < len(pending) and options["rate_limit_seconds"]:
                time.sleep(options["rate_limit_seconds"])

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        report_path = report_dir / f"jbrowse_refnames_{mode}_{stamp}.json"
        summary = {
            "mode": mode,
            "total_assembly_count": len(assembly_ids),
            "processed_this_run": len(results),
            "successful_this_run": sum(item["success"] for item in results),
            "failed_this_run": sum(not item["success"] for item in results),
            "remaining_count": sum(
                str(item) not in checkpoint["processed"] for item in assembly_ids
            ),
            "checkpoint_path": str(checkpoint_path),
        }
        self._write_json_atomic(report_path, {"summary": summary, "results": results})
        summary["json_report"] = str(report_path)
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    @staticmethod
    def _validate(options):
        if options["assembly_id"] is not None and options["assembly_id"] < 1:
            raise CommandError("--assembly-id must be positive")
        if options["all_assemblies"] and not options["report_dir"]:
            raise CommandError("--report-dir is required with --all")
        if options["assembly_id"] is not None and (
            options["report_dir"] or options["resume"] or options["retry_failed"] or options["batch_size"]
        ):
            raise CommandError("Batch options may only be used with --all")
        if options["retry_failed"] and not options["resume"]:
            raise CommandError("--retry-failed requires --resume")
        if options["batch_size"] is not None and options["batch_size"] < 1:
            raise CommandError("--batch-size must be positive")
        if options["rate_limit_seconds"] < 0:
            raise CommandError("--rate-limit-seconds must not be negative")

    @staticmethod
    def _run_one(assembly_id, mode, output_dir):
        assembly = public_assembly_list_queryset().filter(id=assembly_id).first()
        if assembly is None:
            return {"assembly_id": assembly_id, "status": "assembly_not_found", "write_performed": False}
        genome_file, fasta_index = select_mapping_inputs(assembly)
        if mode == "dry_run":
            return inspect_refname_mapping(
                assembly, genome_file, fasta_index, output_root=output_dir
            )
        return build_refname_mapping(
            assembly, genome_file, fasta_index, output_root=output_dir
        )

    def _run_one_safely(self, assembly_id, mode, output_dir):
        try:
            return self._run_one(assembly_id, mode, output_dir)
        except (OSError, UnicodeError, ValueError, ReferenceNameError) as exc:
            return {
                "assembly_id": assembly_id,
                "status": getattr(exc, "code", "mapping_failed"),
                "write_performed": False,
                "error": str(exc),
            }

    @staticmethod
    def _load_checkpoint(path, mode):
        if not path.is_file():
            return {"schema_version": 1, "mode": mode, "processed": {}}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Invalid checkpoint: {path}") from exc
        if payload.get("schema_version") != 1 or payload.get("mode") != mode:
            raise CommandError(f"Incompatible checkpoint: {path}")
        return payload

    @staticmethod
    def _write_json_atomic(path, payload):
        temporary_path = path.with_name(f".{path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()
