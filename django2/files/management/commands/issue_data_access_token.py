from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from files.management.external_data_command import add_safe_mode_arguments, is_apply_mode
from files.models import DataAccessToken


class Command(BaseCommand):
    help = "Issue a hashed external-data API token; plaintext is displayed once in apply mode."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--scope", action="append", required=True, choices=sorted(DataAccessToken.ALLOWED_SCOPES))
        parser.add_argument("--access-tier", choices=[choice[0] for choice in DataAccessToken.ACCESS_TIER_CHOICES], default=DataAccessToken.ACCESS_TIER_PUBLIC)
        expiry = parser.add_mutually_exclusive_group()
        expiry.add_argument("--expires-at")
        expiry.add_argument("--expires-in-hours", type=int)
        parser.add_argument("--created-by")
        add_safe_mode_arguments(parser)

    def handle(self, *args, **options):
        expires_at = self._expires_at(options)
        creator = self._get_creator(options["created_by"])
        scopes = sorted(set(options["scope"]))
        self.stdout.write(f"mode\t{'APPLY' if is_apply_mode(options) else 'DRY_RUN'}")
        self.stdout.write(f"name\t{options['name']}")
        self.stdout.write(f"scopes\t{','.join(scopes)}")
        self.stdout.write(f"access_tier\t{options['access_tier']}")
        self.stdout.write(f"expires_at\t{expires_at.isoformat() if expires_at else ''}")
        if not is_apply_mode(options):
            self.stdout.write("status\tready_no_token_issued")
            return
        token, raw_token = DataAccessToken.issue(
            name=options["name"], scopes=scopes, access_tier=options["access_tier"],
            expires_at=expires_at, created_by=creator,
        )
        self.stdout.write(f"token_id\t{token.id}")
        self.stdout.write(f"token_prefix\t{token.token_prefix}")
        self.stdout.write(f"token\t{raw_token}")
        self.stdout.write("warning\tStore this token now; it cannot be displayed again.")

    @staticmethod
    def _expires_at(options):
        if options["expires_in_hours"] is not None:
            if options["expires_in_hours"] <= 0:
                raise CommandError("--expires-in-hours must be greater than zero")
            return timezone.now() + timedelta(hours=options["expires_in_hours"])
        if not options["expires_at"]:
            return None
        value = parse_datetime(options["expires_at"])
        if value is None:
            raise CommandError("--expires-at must be an ISO-8601 datetime")
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        if value <= timezone.now():
            raise CommandError("Token expiry must be in the future")
        return value

    @staticmethod
    def _get_creator(identifier):
        if not identifier:
            return None
        user_model = get_user_model()
        try:
            return user_model._default_manager.get(**{user_model.USERNAME_FIELD: identifier})
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Creator not found: {identifier}") from exc
