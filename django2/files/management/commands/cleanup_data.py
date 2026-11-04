from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled: legacy GenomeFile cleanup must not mutate the retired table."

    def handle(self, *args, **options):
        raise CommandError(
            "cleanup_data is disabled because GenomeFile is read-only after the T0 audit. "
            "Use DataFile/FileRelation-specific maintenance commands instead."
        )
