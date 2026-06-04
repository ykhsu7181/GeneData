import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from files.models import Annotation, GenomeFile
from files.services.file_relation_service import get_files_for_annotation


class Command(BaseCommand):
    help = "Compare legacy GenomeFile files with DataFile/FileRelation service files for one annotation."

    def add_arguments(self, parser):
        parser.add_argument("--annotation-id", type=int, help="Annotation primary key id.")
        parser.add_argument("--annotation", help="Annotation name or standard_id.")
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for compare_annotation_files.tsv. Defaults to BASE_DIR.",
        )

    def handle(self, *args, **options):
        annotation = self.resolve_annotation(options.get("annotation"), options.get("annotation_id"))
        output_dir = options.get("output_dir") or str(settings.BASE_DIR)
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "compare_annotation_files.tsv")

        old_files = self.get_legacy_files(annotation)
        new_files = get_files_for_annotation(annotation.id)

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
            f"annotation_id\t{annotation.id}",
            f"annotation\t{annotation.name}",
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

    def resolve_annotation(self, annotation_code, annotation_id):
        if bool(annotation_code) == bool(annotation_id):
            raise CommandError("Provide exactly one of --annotation or --annotation-id.")

        if annotation_id:
            annotation = Annotation.objects.filter(id=annotation_id).first()
            label = annotation_id
        else:
            matches = Annotation.objects.filter(
                Q(name=annotation_code) | Q(standard_id=annotation_code)
            )
            count = matches.count()
            if count > 1:
                raise CommandError(f"Multiple annotations matched: {annotation_code}")
            annotation = matches.first()
            label = annotation_code

        if not annotation:
            raise CommandError(f"Annotation not found: {label}")
        return annotation

    def get_legacy_files(self, annotation):
        return [
            {
                "file_path": genome_file.file_path,
                "file_role": genome_file.category,
                "file_name": genome_file.name,
                "source": "legacy_genomefile",
            }
            for genome_file in GenomeFile.objects.filter(annotation=annotation)
            .select_related("file_type", "accession", "assembly", "annotation")
            .order_by("category", "name", "id")
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
