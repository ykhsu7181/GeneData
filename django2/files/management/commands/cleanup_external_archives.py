from django.core.management.base import BaseCommand
from django.utils import timezone

from files.models import ExternalFileArchive
from files.services.external_file_archive_service import cleanup_expired_archives


class Command(BaseCommand):
    help = "Report expired external archives; delete files and mark expired only with --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Delete expired outputs and mark jobs expired.")

    def handle(self, *args, **options):
        now = timezone.now()
        count = ExternalFileArchive.objects.filter(
            expires_at__lte=now,
            status__in=[
                ExternalFileArchive.STATUS_QUEUED,
                ExternalFileArchive.STATUS_READY,
                ExternalFileArchive.STATUS_FAILED,
            ],
        ).count()
        if not options["apply"]:
            self.stdout.write("mode\tDRY_RUN")
            self.stdout.write(f"expired\t{count}")
            return
        processed, removed = cleanup_expired_archives(now=now)
        self.stdout.write("mode\tAPPLY")
        self.stdout.write(f"expired\t{processed}")
        self.stdout.write(f"files_removed\t{removed}")
