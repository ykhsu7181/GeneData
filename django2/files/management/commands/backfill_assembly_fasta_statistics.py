from pathlib import Path

from django.core.management.base import BaseCommand

from files.models import Assembly
from files.services.fasta_statistics_service import calculate_fasta_statistics
from files.services.file_relation_service import (
    GenomeFileSelectionError,
    get_primary_genome_file_for_assembly,
)


class Command(BaseCommand):
    help = "Calculate missing Assembly statistics from each primary genome FASTA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assembly-id",
            action="append",
            type=int,
            dest="assembly_ids",
            help="Limit processing to one or more Assembly IDs.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing FASTA-derived values instead of filling blanks only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Calculate and report values without updating the database.",
        )

    def handle(self, *args, **options):
        queryset = Assembly.objects.order_by("id")
        if options["assembly_ids"]:
            queryset = queryset.filter(id__in=options["assembly_ids"])

        scanned = updated = skipped = failed = 0
        for assembly in queryset.iterator():
            try:
                primary_file = get_primary_genome_file_for_assembly(assembly.id)
                if not primary_file:
                    skipped += 1
                    self.stdout.write(f"assembly={assembly.id} skipped=no_primary_genome_fasta")
                    continue
                fasta_path = Path(primary_file["file_path"])
                if not fasta_path.is_file():
                    raise FileNotFoundError(f"FASTA file not found: {fasta_path}")

                values = calculate_fasta_statistics(fasta_path)
                scanned += 1
                updates = {
                    field: value
                    for field, value in values.items()
                    if options["overwrite"] or getattr(assembly, field) is None
                }
                if not updates:
                    skipped += 1
                    self.stdout.write(f"assembly={assembly.id} skipped=statistics_present")
                    continue
                if not options["dry_run"]:
                    for field, value in updates.items():
                        setattr(assembly, field, value)
                    assembly.save(update_fields=[*updates, "updated_at"])
                updated += 1
                fields = ",".join(sorted(updates))
                self.stdout.write(f"assembly={assembly.id} updated={fields}")
            except (GenomeFileSelectionError, OSError, ValueError) as exc:
                failed += 1
                self.stderr.write(f"assembly={assembly.id} error={exc}")

        self.stdout.write(
            f"scanned={scanned} updated={updated} skipped={skipped} "
            f"failed={failed} dry_run={options['dry_run']}"
        )
