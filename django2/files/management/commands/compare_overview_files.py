import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, GenomeFile
from files.services.file_relation_service import get_files_for_accession


class Command(BaseCommand):
    help = "Compare paginated_overview legacy GenomeFile files with DataFile/FileRelation service files."

    def add_arguments(self, parser):
        parser.add_argument("--accession", help="Accession code, for example IR64.")
        parser.add_argument("--accession-id", type=int, help="Accession primary key id.")
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit accessions when comparing overview files in batch mode.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for compare_overview_files.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        accessions = self.resolve_accessions(
            accession_code=options.get("accession"),
            accession_id=options.get("accession_id"),
            limit=options.get("limit"),
        )
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "compare_overview_files.tsv")

        totals = Counter()
        source_counts = Counter()
        report_rows = [[
            "accession",
            "accession_id",
            "status",
            "file_path",
            "file_role",
            "old_name",
            "new_name",
            "new_source",
        ]]

        for accession_obj in accessions:
            old_files = self.get_legacy_files(accession_obj)
            new_files = get_files_for_accession(accession_obj.id)

            old_map = {self.file_key(item): item for item in old_files}
            new_map = {self.file_key(item): item for item in new_files}
            old_keys = set(old_map)
            new_keys = set(new_map)

            matched_keys = sorted(old_keys & new_keys)
            only_old_keys = sorted(old_keys - new_keys)
            only_new_keys = sorted(new_keys - old_keys)

            totals["old_count"] += len(old_files)
            totals["new_count"] += len(new_files)
            totals["matched_files"] += len(matched_keys)
            totals["only_in_old"] += len(only_old_keys)
            totals["only_in_new"] += len(only_new_keys)
            source_counts.update(item["source"] for item in new_files)

            report_rows.extend(
                self.build_report_rows(
                    accession_obj=accession_obj,
                    matched_keys=matched_keys,
                    only_old_keys=only_old_keys,
                    only_new_keys=only_new_keys,
                    old_map=old_map,
                    new_map=new_map,
                )
            )

        with open(report_path, "w", encoding="utf-8", newline="") as handle:
            for row in report_rows:
                handle.write("\t".join(str(value) for value in row))
                handle.write("\n")

        lines = [
            f"accession_scope\t{self.scope_label(accessions)}",
            f"accession_checked\t{len(accessions)}",
            f"old_count\t{totals['old_count']}",
            f"new_count\t{totals['new_count']}",
            f"matched_files\t{totals['matched_files']}",
            f"only_in_old\t{totals['only_in_old']}",
            f"only_in_new\t{totals['only_in_new']}",
            "source_distribution\t"
            + ",".join(f"{source}:{count}" for source, count in sorted(source_counts.items())),
            f"report\t{report_path}",
        ]
        for line in lines:
            self.stdout.write(line)

    def resolve_accessions(self, *, accession_code, accession_id, limit):
        if accession_code and accession_id:
            raise CommandError("Provide --accession or --accession-id, not both.")

        if accession_id:
            accession_obj = Accession.objects.filter(id=accession_id).first()
            if not accession_obj:
                raise CommandError(f"Accession not found: {accession_id}")
            return [accession_obj]

        if accession_code:
            accession_obj = Accession.objects.filter(accession=accession_code).first()
            if not accession_obj:
                raise CommandError(f"Accession not found: {accession_code}")
            return [accession_obj]

        queryset = Accession.objects.order_by("accession", "id")
        if limit is not None:
            if limit < 1:
                raise CommandError("--limit must be greater than 0.")
            queryset = queryset[:limit]

        accessions = list(queryset)
        if not accessions:
            raise CommandError("No accession records found.")
        return accessions

    def get_legacy_files(self, accession_obj):
        queryset = GenomeFile.objects.filter(accession=accession_obj).select_related(
            "file_type", "accession", "assembly", "annotation"
        )
        if not queryset.exists():
            queryset = GenomeFile.objects.filter(organism=accession_obj.accession).select_related(
                "file_type", "accession", "assembly", "annotation"
            )

        return [
            {
                "file_path": genome_file.file_path,
                "file_role": genome_file.category,
                "file_name": genome_file.name,
                "source": "legacy_genomefile",
            }
            for genome_file in queryset.order_by("category", "name", "id")
        ]

    def file_key(self, item):
        return (item.get("file_path") or "", item.get("file_role") or "")

    def build_report_rows(
        self,
        *,
        accession_obj,
        matched_keys,
        only_old_keys,
        only_new_keys,
        old_map,
        new_map,
    ):
        rows = []
        for key in matched_keys:
            old_item = old_map[key]
            new_item = new_map[key]
            rows.append([
                accession_obj.accession,
                accession_obj.id,
                "matched",
                key[0],
                key[1],
                old_item.get("file_name") or "",
                new_item.get("file_name") or "",
                new_item.get("source") or "",
            ])
        for key in only_old_keys:
            old_item = old_map[key]
            rows.append([
                accession_obj.accession,
                accession_obj.id,
                "only_in_old",
                key[0],
                key[1],
                old_item.get("file_name") or "",
                "",
                "",
            ])
        for key in only_new_keys:
            new_item = new_map[key]
            rows.append([
                accession_obj.accession,
                accession_obj.id,
                "only_in_new",
                key[0],
                key[1],
                "",
                new_item.get("file_name") or "",
                new_item.get("source") or "",
            ])
        return rows

    def scope_label(self, accessions):
        if len(accessions) == 1:
            accession_obj = accessions[0]
            return f"{accession_obj.accession} ({accession_obj.id})"
        return "batch"
