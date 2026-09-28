import json

from django.core.management.base import BaseCommand, CommandError

from files.services.jbrowse_index_service import (
    JBrowseIndexBuildError,
    build_jbrowse_assembly_indexes,
    inspect_jbrowse_assembly,
)


class Command(BaseCommand):
    help = "Inspect or build JBrowse indexes for visible Assemblies."

    def add_arguments(self, parser):
        parser.add_argument("--assembly-id", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--output-dir")

    def handle(self, *args, **options):
        if options["dry_run"] == options["apply"]:
            raise CommandError("Choose exactly one of --dry-run or --apply")

        try:
            if options["dry_run"]:
                result = inspect_jbrowse_assembly(
                    options["assembly_id"],
                    output_root=options.get("output_dir"),
                )
            else:
                result = build_jbrowse_assembly_indexes(
                    options["assembly_id"],
                    output_root=options.get("output_dir"),
                )
        except JBrowseIndexBuildError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

        if result["status"] not in {"ready_for_build", "reference_only", "built"}:
            raise CommandError(f"JBrowse preflight failed: {result['status']}")
