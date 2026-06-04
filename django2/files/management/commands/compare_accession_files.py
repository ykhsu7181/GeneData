import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from files.models import Accession, GenomeFile
from files.services.file_relation_service import get_files_for_accession


class Command(BaseCommand):
    help = "Compare legacy GenomeFile files with DataFile/FileRelation service files for one accession."

    def add_arguments(self, parser):
        parser.add_argument("--accession", help="Accession code, for example IR64.")
        parser.add_argument("--accession-id", type=int, help="Accession primary key id.")
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for compare_accession_files.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        accession_obj = self.resolve_accession(options.get("accession"), options.get("accession_id"))
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "compare_accession_files.tsv")

        old_files = self.get_legacy_files(accession_obj)
        new_files = get_files_for_accession(accession_obj.id)

        old_map = {self.file_key(item): item for item in old_files}
        new_map = {self.file_key(item): item for item in new_files}
        old_keys = set(old_map)
        new_keys = set(new_map)

        matched_keys = sorted(old_keys & new_keys)
        only_old_keys = sorted(old_keys - new_keys)
        only_new_keys = sorted(new_keys - old_keys)
        source_counts = Counter(item["source"] for item in new_files)

        self.write_report(
            report_path,
            matched_keys=matched_keys,
            only_old_keys=only_old_keys,
            only_new_keys=only_new_keys,
            old_map=old_map,
            new_map=new_map,
        )

        lines = [
            f"accession\t{accession_obj.accession}",
            f"accession_id\t{accession_obj.id}",
            f"old_count\t{len(old_files)}",
            f"new_count\t{len(new_files)}",
            f"matched_files\t{len(matched_keys)}",
            f"only_in_old\t{len(only_old_keys)}",
            f"only_in_new\t{len(only_new_keys)}",
            "source_distribution\t"
            + ",".join(f"{source}:{count}" for source, count in sorted(source_counts.items())),
            f"report\t{report_path}",
        ]
        for line in lines:
            self.stdout.write(line)

    def resolve_accession(self, accession_code, accession_id):
        if bool(accession_code) == bool(accession_id):
            raise CommandError("Provide exactly one of --accession or --accession-id.")

        if accession_id:
            accession_obj = Accession.objects.filter(id=accession_id).first()
            label = accession_id
        else:
            accession_obj = Accession.objects.filter(accession=accession_code).first()
            label = accession_code

        if not accession_obj:
            raise CommandError(f"Accession not found: {label}")
        return accession_obj

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

    def write_report(self, report_path, *, matched_keys, only_old_keys, only_new_keys, old_map, new_map):
        rows = [["status", "file_path", "file_role", "old_name", "new_name", "new_source"]]
        for key in matched_keys:
            old_item = old_map[key]
            new_item = new_map[key]
            rows.append(
                [
                    "matched",
                    key[0],
                    key[1],
                    old_item.get("file_name") or "",
                    new_item.get("file_name") or "",
                    new_item.get("source") or "",
                ]
            )
        for key in only_old_keys:
            old_item = old_map[key]
            rows.append(["only_in_old", key[0], key[1], old_item.get("file_name") or "", "", ""])
        for key in only_new_keys:
            new_item = new_map[key]
            rows.append(
                [
                    "only_in_new",
                    key[0],
                    key[1],
                    "",
                    new_item.get("file_name") or "",
                    new_item.get("source") or "",
                ]
            )

        with open(report_path, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write("\t".join(row))
                handle.write("\n")
