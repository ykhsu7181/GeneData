from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled: legacy GenomeFile-to-Accession writes are retired."

    def handle(self, *args, **options):
        raise CommandError(
            "link_genomefiles_to_accessions is disabled because GenomeFile is read-only "
            "after the T0 audit. Maintain ownership with FileRelation instead."
        )
