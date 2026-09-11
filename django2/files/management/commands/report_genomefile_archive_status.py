import csv
import inspect
import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from files import query_views
from files.management.commands import scan_files
from files.download_views import download_datafile
from files.models import Accession, Annotation, DataFile, FileRelation, GenomeFile
from files.services import (
    accession_context,
    data_overview_service,
    file_relation_service,
    query_view_helpers,
    transcriptome_list_service,
)
from files.services.file_relation_service import get_files_for_accession, get_files_for_annotation


class Command(BaseCommand):
    help = "Report GenomeFile archive status without changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=os.path.join(settings.BASE_DIR, "audit_reports"),
            help="Directory for archive status reports.",
        )

    def handle(self, *args, **options):
        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        txt_path = os.path.join(output_dir, f"genomefile_archive_status_{timestamp}.txt")
        tsv_path = os.path.join(output_dir, f"genomefile_archive_status_{timestamp}.tsv")

        details = []
        stats = self._collect_stats(details)
        result = "PASS" if self._is_pass(stats) else "FAIL"
        stats["result"] = result

        self._write_txt(txt_path, stats)
        self._write_tsv(tsv_path, details)

        for key in [
            "result",
            "genomefile_total_count",
            "genomefile_mapped_datafile_count",
            "genomefile_unmapped_datafile_count",
            "legacy_genomefile_source_count",
            "organism_fallback_count",
            "business_genomefile_download_return_count",
            "scan_files_legacy_dual_write_count",
            "business_genomefile_objects_reference_count",
        ]:
            self.stdout.write(f"{key}\t{stats[key]}")
        self.stdout.write(f"txt_report\t{txt_path}")
        self.stdout.write(f"tsv_report\t{tsv_path}")

    def _collect_stats(self, details):
        genomefiles = list(GenomeFile.objects.all().order_by("id"))
        datafile_paths = set(
            DataFile.objects.exclude(file_path__isnull=True)
            .exclude(file_path="")
            .values_list("file_path", flat=True)
        )

        mapped_count = 0
        for genome_file in genomefiles:
            if genome_file.file_path in datafile_paths:
                mapped_count += 1
                status = "mapped"
                issue = ""
                suggested_action = "keep_as_archive"
            else:
                status = "unmapped"
                issue = "GenomeFile file_path has no matching DataFile"
                suggested_action = "backfill_to_datafile_before_removing_archive_dependency"
            details.append(
                {
                    "check_type": "genomefile_mapping",
                    "status": status,
                    "object_type": "GenomeFile",
                    "object_id": genome_file.id,
                    "file_path": genome_file.file_path,
                    "related_type": "",
                    "related_id": "",
                    "file_role": genome_file.category,
                    "issue": issue,
                    "suggested_action": suggested_action,
                }
            )

        source_counts = self._count_service_sources()
        legacy_source_count = source_counts["legacy_genomefile"]
        organism_fallback_count = source_counts["organism_fallback"]
        self._append_status_detail(
            details,
            "legacy_source",
            "pass" if legacy_source_count == 0 else "fail",
            legacy_source_count,
            "service returned legacy_genomefile source",
            "repair FileRelation coverage and keep service new-only",
        )
        self._append_status_detail(
            details,
            "organism_fallback",
            "pass" if organism_fallback_count == 0 else "fail",
            organism_fallback_count,
            "service returned organism_fallback source",
            "repair FileRelation coverage and keep service new-only",
        )

        business_download_count = self._count_business_download_url_references()
        scan_legacy_dual_count = self._count_scan_files_legacy_dual_support()
        business_reference_count = self._count_business_genomefile_objects_references()
        self._append_status_detail(
            details,
            "business_download_url",
            "pass" if business_download_count == 0 else "fail",
            business_download_count,
            "business response code still contains genome-files download URL",
            "return data-files download URLs only",
        )
        self._append_status_detail(
            details,
            "scan_files_write_mode",
            "pass" if scan_legacy_dual_count == 0 else "fail",
            scan_legacy_dual_count,
            "scan_files still supports legacy or dual write mode",
            "keep scan_files new-only",
        )
        self._append_status_detail(
            details,
            "business_genomefile_objects",
            "pass" if business_reference_count == 0 else "fail",
            business_reference_count,
            "business main-chain code still uses GenomeFile.objects",
            "query DataFile and FileRelation instead",
        )

        return {
            "genomefile_total_count": len(genomefiles),
            "genomefile_mapped_datafile_count": mapped_count,
            "genomefile_unmapped_datafile_count": len(genomefiles) - mapped_count,
            "legacy_genomefile_source_count": legacy_source_count,
            "organism_fallback_count": organism_fallback_count,
            "business_genomefile_download_return_count": business_download_count,
            "scan_files_legacy_dual_write_count": scan_legacy_dual_count,
            "business_genomefile_objects_reference_count": business_reference_count,
        }

    def _count_service_sources(self):
        counter = Counter()
        for accession in Accession.objects.all().order_by("id"):
            for item in get_files_for_accession(accession.id):
                counter[item.get("source", "")] += 1
                fallback_source = item.get("fallback_source")
                if fallback_source:
                    counter[fallback_source] += 1
        for annotation in Annotation.objects.all().order_by("id"):
            for item in get_files_for_annotation(annotation.id):
                counter[item.get("source", "")] += 1
                fallback_source = item.get("fallback_source")
                if fallback_source:
                    counter[fallback_source] += 1
        return counter

    def _count_business_download_url_references(self):
        sources = [
            inspect.getsource(accession_context),
            inspect.getsource(query_views),
            inspect.getsource(query_view_helpers),
        ]
        count = 0
        for source in sources:
            for line in source.splitlines():
                if "download_url" in line and "genome-files" in line:
                    count += 1
        return count

    def _count_scan_files_legacy_dual_support(self):
        source = inspect.getsource(scan_files.Command.handle)
        count = 0
        if 'write_mode == "legacy"' in source or "write_mode == 'legacy'" in source:
            count += 1
        if 'write_mode == "dual"' in source or "write_mode == 'dual'" in source:
            count += 1
        return count

    def _count_business_genomefile_objects_references(self):
        sources = [
            inspect.getsource(file_relation_service),
            inspect.getsource(accession_context),
            inspect.getsource(data_overview_service),
            inspect.getsource(transcriptome_list_service),
            inspect.getsource(query_views),
            inspect.getsource(query_view_helpers),
            inspect.getsource(scan_files.Command.handle),
            inspect.getsource(download_datafile),
        ]
        return sum(source.count("GenomeFile.objects") for source in sources)

    def _append_status_detail(self, details, check_type, status, count, issue, suggested_action):
        details.append(
            {
                "check_type": check_type,
                "status": status,
                "object_type": "",
                "object_id": "",
                "file_path": "",
                "related_type": "",
                "related_id": "",
                "file_role": "",
                "issue": "" if count == 0 else issue,
                "suggested_action": "no_action" if count == 0 else suggested_action,
            }
        )

    def _is_pass(self, stats):
        return (
            stats["genomefile_unmapped_datafile_count"] == 0
            and stats["legacy_genomefile_source_count"] == 0
            and stats["organism_fallback_count"] == 0
            and stats["business_genomefile_download_return_count"] == 0
            and stats["scan_files_legacy_dual_write_count"] == 0
            and stats["business_genomefile_objects_reference_count"] == 0
        )

    def _write_txt(self, path, stats):
        lines = [
            "GenomeFile archive status",
            f"generated_at\t{timezone.now().isoformat()}",
        ]
        for key, value in stats.items():
            lines.append(f"{key}\t{value}")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def _write_tsv(self, path, details):
        fieldnames = [
            "check_type",
            "status",
            "object_type",
            "object_id",
            "file_path",
            "related_type",
            "related_id",
            "file_role",
            "issue",
            "suggested_action",
        ]
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(details)
