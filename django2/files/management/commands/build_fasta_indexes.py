from django.core.management.base import BaseCommand, CommandError

from files.management.data_asset_command_support import command_user, profile_assets
from files.services.jbrowse_asset_build_service import build_reference_fasta_index


class Command(BaseCommand):
    help = "Build DataAsset-owned FASTA indexes from reference_genome Profiles."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--asset-code", action="append", dest="asset_codes")
        selection.add_argument("--all", action="store_true", dest="all_assets")
        parser.add_argument("--username", required=True)
        parser.add_argument("--output-root")

    def handle(self, *args, **options):
        user = command_user(options["username"])
        assets, registry = profile_assets(
            user=user, family="reference_genome", asset_codes=options["asset_codes"]
        )
        if options["asset_codes"] and not assets:
            raise CommandError("No authorized reference_genome DataAsset matched")
        built = failed = 0
        for asset in assets:
            try:
                index_file, sequence_count = build_reference_fasta_index(
                    asset,
                    user=user,
                    registry=registry,
                    output_root=options["output_root"],
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(f"asset={asset.asset_code} failed: {exc}")
                continue
            built += 1
            self.stdout.write(
                f"asset={asset.asset_code} index={index_file.file_code} sequences={sequence_count}"
            )
        self.stdout.write(self.style.SUCCESS(f"FASTA indexes: built={built} failed={failed}"))
