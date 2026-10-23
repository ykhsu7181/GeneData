from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from files.management.external_data_command import add_safe_mode_arguments, is_apply_mode
from files.models import DataAccessToken


class Command(BaseCommand):
    help = "Revoke one external-data API token by exact token prefix; default is dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--token-prefix", required=True)
        add_safe_mode_arguments(parser)

    def handle(self, *args, **options):
        try:
            token = DataAccessToken.objects.get(token_prefix=options["token_prefix"])
        except DataAccessToken.DoesNotExist as exc:
            raise CommandError("Token prefix not found") from exc
        self.stdout.write(f"mode\t{'APPLY' if is_apply_mode(options) else 'DRY_RUN'}")
        self.stdout.write(f"token_id\t{token.id}")
        self.stdout.write(f"token_prefix\t{token.token_prefix}")
        if token.revoked_at:
            self.stdout.write("status\talready_revoked")
            return
        if not is_apply_mode(options):
            self.stdout.write("status\tready_to_revoke")
            return
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at", "updated_at"])
        self.stdout.write("status\trevoked")
