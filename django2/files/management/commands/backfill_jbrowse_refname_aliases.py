import json

from django.core.management.base import BaseCommand, CommandError

from files.management.data_asset_command_support import command_user, profile_assets
from files.services.jbrowse_asset_build_service import (
    build_reference_name_cache,
    inspect_reference_name_cache,
)


class Command(BaseCommand):
    help = "Build refName cache files from Annotation DataAsset reference relations."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--asset-code", action="append", dest="asset_codes")
        selection.add_argument("--all", action="store_true", dest="all_assets")
        parser.add_argument("--username", required=True)
        parser.add_argument("--output-root")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        user = command_user(options["username"])
        assets, registry = profile_assets(
            user=user, family="genome_annotation", asset_codes=options["asset_codes"]
        )
        if options["asset_codes"] and not assets:
            raise CommandError("No authorized genome_annotation DataAsset matched")
        results = []
        for asset in assets:
            if options["dry_run"]:
                try:
                    _, payload = inspect_reference_name_cache(
                        asset, user=user, registry=registry
                    )
                except Exception as exc:
                    results.append({
                        "asset_code": asset.asset_code,
                        "status": "failed",
                        "error": str(exc),
                    })
                    continue
                results.append({
                    "asset_code": asset.asset_code,
                    "status": "ready_for_build",
                    "reference_count": len(payload["reference_lengths"]),
                })
                continue
            try:
                path, payload = build_reference_name_cache(
                    asset,
                    user=user,
                    registry=registry,
                    output_root=options["output_root"],
                )
            except Exception as exc:
                results.append({
                    "asset_code": asset.asset_code, "status": "failed", "error": str(exc)
                })
                continue
            results.append({
                "asset_code": asset.asset_code,
                "status": "built",
                "path": str(path),
                "reference_count": len(payload["reference_lengths"]),
            })
        self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
        if any(item["status"] == "failed" for item in results):
            raise CommandError("One or more refName cache builds failed")
