from django.core.management.base import BaseCommand

from files.models import DataAccessToken


class Command(BaseCommand):
    help = "List external-data API token metadata without revealing hashes or plaintext."

    def add_arguments(self, parser):
        parser.add_argument("--include-inactive", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write("id\tprefix\tname\tstatus\taccess_tier\tscopes\texpires_at\tlast_used_at")
        count = 0
        for token in DataAccessToken.objects.all().order_by("id"):
            status = "active" if token.is_active else ("revoked" if token.revoked_at else "expired")
            if status != "active" and not options["include_inactive"]:
                continue
            self.stdout.write("\t".join([
                str(token.id), token.token_prefix, token.name, status, token.access_tier,
                ",".join(token.scopes or []),
                token.expires_at.isoformat() if token.expires_at else "",
                token.last_used_at.isoformat() if token.last_used_at else "",
            ]))
            count += 1
        self.stdout.write(f"count\t{count}")
