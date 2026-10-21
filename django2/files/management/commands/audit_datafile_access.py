from collections import Counter

from django.core.management.base import BaseCommand

from files.management.external_data_command import make_report_path, write_tsv
from files.models import DataFile
from files.services.datafile_access_service import get_datafile_dataset_access_levels
from files.services.external_data_operations import inspect_datafile_readiness


FIELDS = (
    "data_file_id", "file_code", "access_level", "publication_status",
    "effective_access_level", "dataset_levels", "path_status", "sha256_status",
    "fasta_index_status", "readiness", "issues",
)


class Command(BaseCommand):
    help = "Read-only audit of DataFile readiness for external API publication."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--data-file-id", action="append", type=int, dest="data_file_ids")

    def handle(self, *args, **options):
        queryset = DataFile.objects.all().order_by("id")
        if options["data_file_ids"]:
            queryset = queryset.filter(id__in=options["data_file_ids"])

        counters = Counter()
        rows = []
        for data_file in queryset.iterator():
            dataset_levels, integrity_error = get_datafile_dataset_access_levels(data_file)
            readiness = inspect_datafile_readiness(data_file)
            levels = set(dataset_levels)
            if data_file.access_level != DataFile.ACCESS_LEVEL_INHERITED:
                levels.add(data_file.access_level)
            policy_conflict = integrity_error or len(levels) > 1
            has_dataset = data_file.dataset_id is not None or data_file.relations.filter(
                related_type="dataset"
            ).exists()

            counters["total"] += 1
            counters[f"access_level_{data_file.access_level}"] += 1
            counters["datasetless"] += int(not has_dataset)
            counters["policy_conflict"] += int(policy_conflict)
            counters["missing_sha256"] += int(data_file.content_version is None)
            counters[f"path_{readiness.path_reason}"] += 1
            counters[f"fasta_index_{readiness.fasta_index_status}"] += 1
            counters["ready"] += int(readiness.ready)
            counters["blocked"] += int(not readiness.ready)

            issues = list(readiness.issues)
            if policy_conflict:
                issues.append("policy_conflict")
            rows.append({
                "data_file_id": data_file.id,
                "file_code": data_file.file_code,
                "access_level": data_file.access_level,
                "publication_status": data_file.publication_status,
                "effective_access_level": readiness.effective_access_level,
                "dataset_levels": ",".join(sorted(dataset_levels)),
                "path_status": readiness.path_reason,
                "sha256_status": "verified" if data_file.content_version else "missing_or_invalid",
                "fasta_index_status": readiness.fasta_index_status,
                "readiness": "ready" if readiness.ready else "blocked",
                "issues": ",".join(dict.fromkeys(issues)),
            })

        report_path = make_report_path(options["output_dir"], "datafile_access_audit")
        write_tsv(report_path, FIELDS, rows)
        ordered_keys = [
            "total", "datasetless", "access_level_inherited", "access_level_private",
            "access_level_internal", "access_level_public", "policy_conflict",
            "path_file_missing", "path_outside_protected_roots", "missing_sha256",
            "fasta_index_missing", "fasta_index_stale", "ready", "blocked",
        ]
        for key in ordered_keys:
            self.stdout.write(f"{key}\t{counters[key]}")
        self.stdout.write(f"report\t{report_path}")
