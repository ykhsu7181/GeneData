import os

from django.core.management.base import BaseCommand

from files.models import Accession, GenomeFile


class Command(BaseCommand):
    help = "Link GenomeFile records to Accession records based on file name"

    def handle(self, *args, **options):
        updated_count = 0
        skipped_count = 0
        missing_count = 0

        queryset = GenomeFile.objects.all()

        if not queryset.exists():
            self.stdout.write(self.style.WARNING("No GenomeFile records found."))
            return

        for genome_file in queryset:
            accession_code = self.extract_accession_from_filename(genome_file.name)

            if not accession_code:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped: cannot parse accession from file name: {genome_file.name}"
                    )
                )
                continue

            accession_obj = Accession.objects.filter(accession=accession_code).first()

            if not accession_obj:
                missing_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing accession in DB: {accession_code} (file: {genome_file.name})"
                    )
                )
                continue

            if genome_file.accession_id != accession_obj.id:
                genome_file.accession = accession_obj
                genome_file.save(update_fields=["accession"])
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Link completed. Updated: {updated_count}, "
                f"Skipped: {skipped_count}, Missing: {missing_count}"
            )
        )

    def extract_accession_from_filename(self, filename):
        """
        Supported naming rules:
        1. category.accession.ext
           example: genome.IR64.fasta
        2. transcriptome.type.accession.ext
           example: transcriptome.root.IR64.tar.gz
        """

        if not filename or "." not in filename:
            return None

        parts = filename.split(".")

        if len(parts) < 3:
            return None

        if parts[0] == "transcriptome":
            if len(parts) >= 4:
                return parts[2].strip()
            return None

        if parts[0] in {
            "genome",
            "annotation",
            "codon",
            "centromere",
            "TEs",
            "coreBlocks",
            "miRNA",
            "tRNA",
            "rRNA",
        }:
            return parts[1].strip()

        return None
