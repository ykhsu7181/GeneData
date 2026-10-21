from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.management.external_data_command import write_tsv
from files.services.external_api_readiness_service import build_external_api_readiness_report


FIELDS = {
    "summary": ("object_type", "status", "count"),
    "accessions": (
        "accession", "status", "anonymous_metadata", "public_assembly_count",
        "related_file_count",
    ),
    "assemblies": (
        "accession", "assembly_code", "assembly_accession", "status", "issues",
        "region_exposed", "genome_file_id", "index_file_id", "sequence_count",
    ),
    "datasets": (
        "dataset_code", "bioproject_accession", "status", "issues", "visibility",
        "dataset_status", "linked_file_count", "manifest_file_count",
        "manifest_exposed", "accessions",
    ),
    "files": (
        "file_code", "file_name", "status", "issues", "publication_status",
        "configured_access_level", "effective_access_level", "is_current",
        "relation_count", "roles", "anonymous_metadata", "token_download",
        "sha256", "content_version",
    ),
}


class Command(BaseCommand):
    help = "Write a read-only External Data API exposure and readiness inventory."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--require-file", action="append", default=[])
        parser.add_argument("--require-dataset", action="append", default=[])
        parser.add_argument("--require-assembly", action="append", default=[])

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        report = build_external_api_readiness_report()
        paths = {}
        for name, rows in report.items():
            path = output_dir / f"external_api_{name}.tsv"
            write_tsv(path, FIELDS[name], rows)
            paths[name] = path

        blockers = []
        blockers.extend(self._required_blockers(
            report["files"], "file_code", options["require_file"], "file"
        ))
        blockers.extend(self._required_blockers(
            report["datasets"], "dataset_code", options["require_dataset"], "dataset"
        ))
        blockers.extend(self._required_blockers(
            report["assemblies"], "assembly_code", options["require_assembly"], "assembly"
        ))
        self.stdout.write("mode\tREAD_ONLY")
        for name in ("summary", "accessions", "assemblies", "datasets", "files"):
            self.stdout.write(f"{name}\t{len(report[name])}\t{paths[name]}")
        self.stdout.write(f"required_blockers\t{len(blockers)}")
        for blocker in blockers:
            self.stdout.write(f"blocker\t{blocker}")
        if blockers:
            raise CommandError("Required External Data API objects are not READY.")

    @staticmethod
    def _required_blockers(rows, key, required, object_type):
        by_code = {row[key]: row for row in rows}
        blockers = []
        for code in dict.fromkeys(required):
            row = by_code.get(code)
            if row is None:
                blockers.append(f"{object_type}:{code}:NOT_FOUND")
            elif row["status"] != "READY":
                blockers.append(f"{object_type}:{code}:{row['status']}")
        return blockers
