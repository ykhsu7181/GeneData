import json

from django.core.management.base import BaseCommand, CommandError

from files.management.data_asset_command_support import command_user, profile_assets
from files.services.jbrowse_asset_build_service import (
    build_annotation_feature_index_for_asset,
    build_annotation_tabix_index,
    build_reference_fasta_index,
    build_reference_name_cache,
)
from files.services.jbrowse_asset_service import resolve_jbrowse_asset_context


class Command(BaseCommand):
    help = "Inspect or build JBrowse dependencies for Annotation DataAssets."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--asset-code", action="append", dest="asset_codes")
        selection.add_argument("--all", action="store_true", dest="all_assets")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--username", required=True)
        parser.add_argument("--output-root")
        parser.add_argument("--tabix-command")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        user = command_user(options["username"])
        assets, registry = profile_assets(
            user=user, family="genome_annotation", asset_codes=options["asset_codes"]
        )
        if options["asset_codes"] and not assets:
            raise CommandError("No authorized genome_annotation DataAsset matched")
        results = []
        for asset in assets:
            try:
                context = resolve_jbrowse_asset_context(
                    asset, user=user, registry=registry, require_indexes=False
                )
                if options["dry_run"]:
                    results.append({
                        "asset_code": asset.asset_code,
                        "reference_asset_code": context.reference_asset.asset_code,
                        "status": "ready_for_build",
                        "write_performed": False,
                    })
                    continue
                fasta_index, sequence_count = build_reference_fasta_index(
                    context.reference_asset,
                    user=user,
                    registry=registry,
                    output_root=options["output_root"],
                )
                tabix_index = build_annotation_tabix_index(
                    asset,
                    user=user,
                    registry=registry,
                    output_root=options["output_root"],
                    tabix_command=options["tabix_command"],
                )
                feature_index, _ = build_annotation_feature_index_for_asset(
                    asset,
                    user=user,
                    registry=registry,
                    force=options["force"],
                )
                cache_path, _ = build_reference_name_cache(
                    asset,
                    user=user,
                    registry=registry,
                    output_root=options["output_root"],
                )
                results.append({
                    "asset_code": asset.asset_code,
                    "status": "built",
                    "write_performed": True,
                    "fasta_index_file": fasta_index.file_code,
                    "tabix_index_file": tabix_index.file_code,
                    "sequence_count": sequence_count,
                    "feature_count": feature_index.feature_count,
                    "refname_cache": str(cache_path),
                })
            except Exception as exc:
                results.append({
                    "asset_code": asset.asset_code,
                    "status": "failed",
                    "write_performed": False,
                    "error": str(exc),
                })
        self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
        if any(item["status"] == "failed" for item in results):
            raise CommandError("One or more JBrowse builds failed")
