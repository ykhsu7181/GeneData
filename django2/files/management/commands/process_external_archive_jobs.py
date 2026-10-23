from django.core.management.base import BaseCommand, CommandError

from files.services.external_file_archive_service import (
    claim_next_archive,
    process_archive,
    recover_stale_jobs,
)


class Command(BaseCommand):
    help = "Process durable external file archive jobs. Run under a supervised worker."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
        parser.add_argument("--limit", type=int, default=10, help="Maximum jobs to process per invocation.")
        parser.add_argument(
            "--recover-stale-minutes",
            type=int,
            default=60,
            help="Requeue interrupted running jobs older than this value.",
        )

    def handle(self, *args, **options):
        limit = 1 if options["once"] else options["limit"]
        if limit < 1:
            raise CommandError("--limit must be at least 1")
        stale_minutes = options["recover_stale_minutes"]
        if stale_minutes < 1:
            raise CommandError("--recover-stale-minutes must be at least 1")

        recovered, exhausted = recover_stale_jobs(stale_minutes=stale_minutes)
        processed = ready = failed = 0
        for _index in range(limit):
            archive_id = claim_next_archive()
            if archive_id is None:
                break
            archive = process_archive(archive_id)
            processed += 1
            if archive.status == archive.STATUS_READY:
                ready += 1
            else:
                failed += 1
            self.stdout.write(f"{archive.archive_id}\t{archive.status}")

        self.stdout.write(f"recovered\t{recovered}")
        self.stdout.write(f"attempts_exhausted\t{exhausted}")
        self.stdout.write(f"processed\t{processed}")
        self.stdout.write(f"ready\t{ready}")
        self.stdout.write(f"failed\t{failed}")
