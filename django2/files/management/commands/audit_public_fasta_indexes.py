from django.core.management.base import BaseCommand, CommandError

from files.models import Assembly, DataFile, FileRelation
from files.services.assembly_visibility import visible_assembly_queryset
from files.services.datafile_access_service import resolve_datafile_access_level
from files.services.external_sequence_service import inspect_public_fasta_index


class Command(BaseCommand):
    help = "Audit public Assembly FASTA files for Region API readiness."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assembly",
            dest="assembly_code",
            help="Audit one exact Assembly code.",
        )

    def handle(self, *args, **options):
        queryset = visible_assembly_queryset(
            Assembly.objects.select_related("accession")
        )
        assembly_code = options.get("assembly_code")
        if assembly_code:
            queryset = queryset.filter(assembly_code=assembly_code)
        else:
            relations = FileRelation.objects.select_related("file").filter(
                related_type="assembly",
                file_role__in=("genome_fasta", "genome"),
                file__is_current=True,
                file__publication_status="released",
            )
            numeric_ids = []
            for relation in relations:
                level, _reason = resolve_datafile_access_level(relation.file)
                if (
                    level != DataFile.ACCESS_LEVEL_PUBLIC
                    or relation.file.published_at is None
                    or relation.file.content_version is None
                ):
                    continue
                try:
                    numeric_ids.append(int(relation.related_id))
                except (TypeError, ValueError):
                    continue
            queryset = queryset.filter(id__in=numeric_ids)

        assemblies = list(queryset.order_by("assembly_code", "id"))
        if assembly_code and not assemblies:
            raise CommandError(f"Assembly not found: {assembly_code}")
        self.stdout.write(
            "assembly_id\tassembly_code\tstatus\tgenome_file_id\tindex_file_id\tsequence_count\tdetail"
        )
        failed = 0
        for assembly in assemblies:
            result = inspect_public_fasta_index(assembly)
            if result["status"] != "PASS":
                failed += 1
            self.stdout.write("\t".join([
                str(assembly.id),
                assembly.assembly_code or "",
                result["status"],
                str(result.get("genome_file_id", "")),
                str(result.get("index_file_id", "")),
                str(result.get("sequence_count", "")),
                result["detail"],
            ]))
        self.stdout.write(f"total={len(assemblies)} pass={len(assemblies) - failed} failed={failed}")
        if failed:
            raise CommandError(f"Public FASTA index audit failed for {failed} Assembly(s).")
