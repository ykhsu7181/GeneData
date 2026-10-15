import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.management.commands.generate_hierarchy_manifests_from_file_list import (
    ANNOTATION_FIELDS,
    ASSEMBLY_FIELDS,
    EXCEPTION_FIELDS,
    FILE_FIELDS,
)


PACKAGE_FILES = {
    "assemblies": ("assemblies.full.tsv", ASSEMBLY_FIELDS),
    "annotations": ("annotations.full.tsv", ANNOTATION_FIELDS),
    "files": ("files.full.tsv", FILE_FIELDS),
    "exceptions": ("exceptions.full.tsv", EXCEPTION_FIELDS),
}
TRUE_VALUES = {"1", "true", "yes"}
FALSE_VALUES = {"0", "false", "no"}


class Command(BaseCommand):
    help = (
        "Validate a generated hierarchy manifest package without changing "
        "database or file state."
    )

    def add_arguments(self, parser):
        parser.add_argument("--manifest-dir", required=True)
        parser.add_argument("--report")
        parser.add_argument(
            "--verify-source-files",
            action="store_true",
            help="Also require every file_path in files.full.tsv to exist.",
        )

    def handle(self, *args, **options):
        manifest_dir = Path(options["manifest_dir"]).expanduser().resolve()
        if not manifest_dir.is_dir():
            raise CommandError(f"Manifest directory not found: {manifest_dir}")

        errors = []
        rows = {}
        for key, (name, required_fields) in PACKAGE_FILES.items():
            path = manifest_dir / name
            if not path.is_file():
                errors.append(f"missing_manifest: {name}")
                rows[key] = []
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                headers = reader.fieldnames or []
                missing = [field for field in required_fields if field not in headers]
                if missing:
                    errors.append(
                        f"missing_columns: {name}: {', '.join(missing)}"
                    )
                rows[key] = list(reader)

        if not errors:
            self.validate_rows(rows, errors, options["verify_source_files"])

        report_lines = [
            "GeneData hierarchy manifest package acceptance report",
            f"manifest_dir\t{manifest_dir}",
            f"assemblies\t{len(rows.get('assemblies', []))}",
            f"annotations\t{len(rows.get('annotations', []))}",
            f"file_bindings\t{len(rows.get('files', []))}",
            f"exceptions\t{len(rows.get('exceptions', []))}",
            f"source_files_verified\t{str(options['verify_source_files']).lower()}",
            f"status\t{'FAIL' if errors else 'PASS'}",
        ]
        if errors:
            report_lines.append("errors")
            report_lines.extend(f"- {error}" for error in errors)
        report = "\n".join(report_lines) + "\n"

        if options.get("report"):
            report_path = Path(options["report"]).expanduser().resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report, encoding="utf-8")
        self.stdout.write(report.rstrip())
        if errors:
            raise CommandError(
                f"Manifest package validation failed with {len(errors)} error(s)."
            )

    @staticmethod
    def validate_rows(rows, errors, verify_source_files):
        assemblies = rows["assemblies"]
        annotations = rows["annotations"]
        files = rows["files"]

        def require_unique(items, field, label):
            counts = Counter(row.get(field, "").strip() for row in items)
            for value, count in counts.items():
                if not value:
                    errors.append(f"blank_{label}: {field}")
                elif count > 1:
                    errors.append(f"duplicate_{label}: {value}")

        require_unique(assemblies, "assembly_code", "assembly_code")
        require_unique(annotations, "annotation_code", "annotation_code")
        require_unique(files, "file_path", "file_path")

        assembly_by_code = {
            row.get("assembly_code", "").strip(): row for row in assemblies
        }
        annotation_by_code = {
            row.get("annotation_code", "").strip(): row for row in annotations
        }
        annotation_groups = defaultdict(list)

        for row in annotations:
            annotation_code = row.get("annotation_code", "").strip()
            assembly_code = row.get("assembly_code", "").strip()
            assembly = assembly_by_code.get(assembly_code)
            if not assembly:
                errors.append(
                    f"annotation_missing_assembly: {annotation_code}: {assembly_code}"
                )
                continue
            if row.get("accession", "").strip() != assembly.get("accession", "").strip():
                errors.append(f"annotation_accession_mismatch: {annotation_code}")
            raw_default = row.get("is_default", "").strip().lower()
            if raw_default not in TRUE_VALUES | FALSE_VALUES:
                errors.append(f"invalid_is_default: {annotation_code}: {raw_default}")
            annotation_groups[assembly_code].append(raw_default in TRUE_VALUES)

        for assembly_code, defaults in annotation_groups.items():
            if sum(defaults) != 1:
                errors.append(
                    f"invalid_default_count: {assembly_code}: {sum(defaults)}"
                )

        for row in files:
            file_path = row.get("file_path", "").strip()
            assembly_code = row.get("assembly_code", "").strip()
            annotation_code = row.get("annotation_code", "").strip()
            assembly = assembly_by_code.get(assembly_code)
            if not assembly:
                errors.append(
                    f"file_missing_assembly: {file_path}: {assembly_code}"
                )
                continue
            if row.get("accession", "").strip() != assembly.get("accession", "").strip():
                errors.append(f"file_accession_mismatch: {file_path}")
            if annotation_code:
                annotation = annotation_by_code.get(annotation_code)
                if not annotation:
                    errors.append(
                        f"file_missing_annotation: {file_path}: {annotation_code}"
                    )
                elif annotation.get("assembly_code", "").strip() != assembly_code:
                    errors.append(f"file_annotation_assembly_mismatch: {file_path}")
            if row.get("file_role", "").strip() == "annotation" and not annotation_code:
                errors.append(f"annotation_file_without_annotation_code: {file_path}")
            if verify_source_files and not Path(file_path).is_file():
                errors.append(f"source_file_not_found: {file_path}")
