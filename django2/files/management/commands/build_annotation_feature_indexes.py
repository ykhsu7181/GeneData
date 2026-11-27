from django.core.management.base import BaseCommand, CommandError

from files.management.data_asset_command_support import command_user, profile_assets
from files.services.jbrowse_asset_build_service import build_annotation_feature_index_for_asset


class Command(BaseCommand):
    help = "Build AnnotationFeature indexes from genome_annotation DataAssets."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--asset-code", action="append", dest="asset_codes")
        selection.add_argument("--all", action="store_true", dest="all_assets")
        parser.add_argument("--username", required=True)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--batch-size", type=int, default=2000)

    def handle(self, *args, **options):
        if options["batch_size"] < 1:
            raise CommandError("--batch-size must be positive")
        user = command_user(options["username"])
        assets, registry = profile_assets(
            user=user, family="genome_annotation", asset_codes=options["asset_codes"]
        )
        if options["asset_codes"] and not assets:
            raise CommandError("No authorized genome_annotation DataAsset matched")
        built = skipped = failed = 0
        for asset in assets:
            try:
                feature_index, changed = build_annotation_feature_index_for_asset(
                    asset,
                    user=user,
                    registry=registry,
                    force=options["force"],
                    batch_size=options["batch_size"],
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(f"asset={asset.asset_code} failed: {exc}")
                continue
            if changed:
                built += 1
                self.stdout.write(
                    f"asset={asset.asset_code} indexed features={feature_index.feature_count}"
                )
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f"annotation indexes: built={built} unchanged={skipped} failed={failed}"
        ))
