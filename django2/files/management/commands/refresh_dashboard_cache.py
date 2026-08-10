from django.core.management.base import BaseCommand

from files.dashboard_views import DASHBOARD_CACHE_KEY, get_cached_dashboard_payload


class Command(BaseCommand):
    help = "Refresh the cached warehouse dashboard payload."

    def handle(self, *args, **options):
        payload = get_cached_dashboard_payload(force_refresh=True)
        summary = payload.get("summary", {})
        self.stdout.write(self.style.SUCCESS("Dashboard cache refreshed."))
        self.stdout.write(f"cache_key={DASHBOARD_CACHE_KEY}")
        self.stdout.write(f"species_count={summary.get('species_count', 0)}")
        self.stdout.write(f"accession_count={summary.get('accession_count', 0)}")
        self.stdout.write(f"datafile_count={summary.get('datafile_count', 0)}")
