import csv
import gzip
import hashlib
import os
import tarfile
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from files.models import Accession, DataFile
from files.services.ingestion.file_parser import parse_ingestion_filename


SEVERITY_RANK = {"ok": 0, "warning": 1, "error": 2}
FASTA_EXTENSIONS = {"fa", "fasta", "fna"}
FASTQ_EXTENSIONS = {"fastq", "fastaq", "fq"}


class Command(BaseCommand):
    help = (
        "Read-only audit of manual_files names, contents and database binding "
        "readiness. This command never changes database rows or source files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="Directory to validate. Defaults to settings.MANUAL_FILES_DIR.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Report directory. Defaults to BASE_DIR/audit_reports.",
        )
        parser.add_argument(
            "--checksum",
            choices=["none", "md5", "sha256"],
            default="none",
            help="Optional streaming checksum. Defaults to none for large production files.",
        )
        parser.add_argument(
            "--fail-on-errors",
            action="store_true",
            help="Raise CommandError after writing reports when invalid files are found.",
        )
        parser.add_argument(
            "--filesystem-only",
            action="store_true",
            help=(
                "Skip all database lookups and validate filesystem names and contents only. "
                "Useful before database credentials are available."
            ),
        )

    def handle(self, *args, **options):
        root = Path(options["path"] or settings.MANUAL_FILES_DIR).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f"Manual files directory not found: {root}")

        output_dir = Path(
            options["output_dir"]
            or Path(settings.BASE_DIR) / "audit_reports"
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        checksum_algorithm = options["checksum"]
        filesystem_only = options["filesystem_only"]
        registered_paths = {}
        if not filesystem_only:
            registered_paths = {
                self.normalize_path(path): (is_current, file_id)
                for path, is_current, file_id in DataFile.objects.values_list(
                    "file_path", "is_current", "id"
                )
            }

        rows = []
        role_accession_counts = Counter()
        paths = sorted(path for path in root.rglob("*") if path.is_file())
        for path in paths:
            row = self.inspect_file(
                path,
                registered_paths=registered_paths,
                checksum_algorithm=checksum_algorithm,
                filesystem_only=filesystem_only,
            )
            rows.append(row)
            if row["file_role"] and row["accession"]:
                role_accession_counts[(row["file_role"], row["accession"])] += 1

        for row in rows:
            key = (row["file_role"], row["accession"])
            if key != ("", "") and role_accession_counts[key] > 1:
                self.add_issue(
                    row,
                    "warning",
                    f"duplicate_role_for_accession:{role_accession_counts[key]}",
                )
            row["issues"] = ";".join(row.pop("issue_list"))

        counts = Counter(row["status"] for row in rows)
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        detail_path = output_dir / f"validate_manual_files_{timestamp}.tsv"
        summary_path = output_dir / f"validate_manual_files_{timestamp}.txt"
        self.write_detail(detail_path, rows)
        self.write_summary(
            summary_path,
            root=root,
            checksum_algorithm=checksum_algorithm,
            filesystem_only=filesystem_only,
            total=len(rows),
            counts=counts,
            detail_path=detail_path,
        )

        result = "FAIL" if counts["error"] else "PASS_WITH_WARNINGS" if counts["warning"] else "PASS"
        self.stdout.write(
            f"manual_files_path\t{root}\n"
            f"total\t{len(rows)}\n"
            f"ok\t{counts['ok']}\n"
            f"warning\t{counts['warning']}\n"
            f"error\t{counts['error']}\n"
            f"result\t{result}\n"
            f"summary_report\t{summary_path}\n"
            f"detail_report\t{detail_path}"
        )
        if counts["error"] and options["fail_on_errors"]:
            raise CommandError(
                f"Found {counts['error']} invalid files; reports were written before exit."
            )

    def inspect_file(
        self,
        path,
        *,
        registered_paths,
        checksum_algorithm,
        filesystem_only,
    ):
        parsed = parse_ingestion_filename(path.name)
        stat = path.stat()
        normalized_path = self.normalize_path(path)
        registered = registered_paths.get(normalized_path)
        row = {
            "status": "ok",
            "file_path": str(path),
            "file_name": path.name,
            "file_size": stat.st_size,
            "file_role": parsed["file_role"] if parsed else "",
            "accession": parsed["accession_code"] if parsed else "",
            "extension": parsed["extension"] if parsed else self.extension_for(path.name),
            "checksum_algorithm": checksum_algorithm if checksum_algorithm != "none" else "",
            "checksum": "",
            "accession_state": "not_checked",
            "assembly_state": "not_checked",
            "annotation_state": "not_checked",
            "datafile_state": "not_checked" if filesystem_only else (
                "current" if registered and registered[0]
                else "inactive" if registered
                else "unregistered"
            ),
            "datafile_id": registered[1] if registered else "",
            "issue_list": [],
        }

        if stat.st_size == 0:
            self.add_issue(row, "error", "empty_file")
        if not parsed:
            self.add_issue(row, "warning", "unrecognized_filename")
        else:
            if filesystem_only:
                row["accession_state"] = "not_checked"
                row["assembly_state"] = "not_checked"
                row["annotation_state"] = "not_checked"
            else:
                self.inspect_database_context(row, parsed)
            if stat.st_size:
                for severity, issue in self.validate_content(path, parsed):
                    self.add_issue(row, severity, issue)

        if checksum_algorithm != "none" and stat.st_size:
            row["checksum"] = self.checksum(path, checksum_algorithm)
        return row

    def inspect_database_context(self, row, parsed):
        accession = Accession.objects.filter(accession=parsed["accession_code"]).first()
        if not accession:
            row["accession_state"] = "missing"
            row["assembly_state"] = "missing"
            row["annotation_state"] = "missing"
            self.add_issue(row, "error", "unknown_accession")
            return

        row["accession_state"] = "found"
        assemblies = list(accession.assemblies.all()[:3])
        row["assembly_state"] = self.context_state(assemblies)
        if len(assemblies) > 1:
            self.add_issue(row, "warning", "ambiguous_assembly_context")
        elif not assemblies and parsed["file_role"] in {"genome", "genome_fasta", "genome_index", "annotation"}:
            self.add_issue(row, "warning", "missing_assembly_context")

        annotations = list(assemblies[0].annotations.all()[:3]) if len(assemblies) == 1 else []
        row["annotation_state"] = self.context_state(annotations)
        if parsed["file_role"] == "annotation":
            if len(assemblies) != 1:
                self.add_issue(row, "warning", "annotation_context_not_resolvable")
            elif len(annotations) > 1:
                self.add_issue(row, "warning", "ambiguous_annotation_context")
            elif not annotations:
                self.add_issue(row, "warning", "missing_annotation_context")

    @staticmethod
    def context_state(objects):
        if not objects:
            return "missing"
        if len(objects) == 1:
            return "unique"
        return "ambiguous"

    def validate_content(self, path, parsed):
        role = parsed["file_role"]
        extension = parsed["extension"].lower()
        try:
            if role == "genome_index" or extension.endswith(".fai"):
                self.validate_fai(path)
            elif extension in FASTA_EXTENSIONS:
                self.validate_fasta(path)
            elif extension == "gff" or extension == "gff3":
                self.validate_gff(path)
            elif extension == "bed":
                self.validate_bed(path)
            elif extension.endswith(".tar.gz") or extension in {"tar", "tgz"}:
                self.validate_tar(path)
            elif extension.endswith(".gz"):
                self.validate_gzip(path, expect_fastq=role.startswith("transcriptome."))
            else:
                self.validate_readable(path)
        except (OSError, EOFError, UnicodeError, ValueError, tarfile.TarError) as exc:
            return [("error", f"invalid_content:{type(exc).__name__}:{exc}")]
        return []

    def validate_fasta(self, path):
        lines = self.first_text_lines(path, limit=30)
        if not lines or not lines[0].startswith(">"):
            raise ValueError("missing_fasta_header")
        sequence = "".join(line.strip() for line in lines[1:] if not line.startswith(">"))
        if not sequence:
            raise ValueError("missing_fasta_sequence")
        allowed = set("ACGTUNRYSWKMBDHVacgtunryswkmbdhv.-*")
        if any(char not in allowed for char in sequence):
            raise ValueError("invalid_fasta_sequence_characters")

    def validate_gff(self, path):
        for line in self.first_text_lines(path, limit=200):
            if not line or line.startswith("#"):
                continue
            columns = line.rstrip("\n\r").split("\t")
            if len(columns) != 9:
                raise ValueError("gff_requires_9_columns")
            int(columns[3])
            int(columns[4])
            return
        raise ValueError("gff_has_no_feature_rows")

    def validate_bed(self, path):
        for line in self.first_text_lines(path, limit=100):
            if not line or line.startswith(("#", "track", "browser")):
                continue
            columns = line.rstrip("\n\r").split("\t")
            if len(columns) < 3:
                raise ValueError("bed_requires_at_least_3_columns")
            standard = self.is_int(columns[1]) and self.is_int(columns[2])
            legacy_mirna = len(columns) >= 5 and self.is_int(columns[3]) and self.is_int(columns[4])
            if not standard and not legacy_mirna:
                raise ValueError("bed_coordinates_are_not_numeric")
            return
        raise ValueError("bed_has_no_data_rows")

    def validate_fai(self, path):
        for line in self.first_text_lines(path, limit=20):
            columns = line.rstrip("\n\r").split("\t")
            if len(columns) < 5 or not all(self.is_int(value) for value in columns[1:5]):
                raise ValueError("fai_requires_name_and_4_numeric_columns")
            return
        raise ValueError("fai_has_no_rows")

    @staticmethod
    def validate_tar(path):
        with tarfile.open(path, mode="r:*") as archive:
            next(iter(archive), None)

    def validate_gzip(self, path, *, expect_fastq=False):
        with gzip.open(path, mode="rt", encoding="utf-8", errors="strict") as handle:
            first = handle.readline().strip()
        if not first:
            raise ValueError("gzip_payload_is_empty")
        if expect_fastq and not first.startswith("@"):
            raise ValueError("transcriptome_fastq_missing_at_header")

    @staticmethod
    def validate_readable(path):
        with path.open("rb") as handle:
            if not handle.read(1):
                raise ValueError("file_has_no_content")

    @staticmethod
    def first_text_lines(path, *, limit):
        lines = []
        with path.open("rt", encoding="utf-8-sig", errors="strict") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
                if len(lines) >= limit:
                    break
        return lines

    @staticmethod
    def is_int(value):
        try:
            int(value)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def checksum(path, algorithm):
        digest = hashlib.new(algorithm)
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def extension_for(filename):
        parts = filename.split(".")
        if len(parts) < 2:
            return ""
        if parts[-1].lower() in {"gz", "bz2", "xz", "zip"} and len(parts) > 2:
            return ".".join(parts[-2:])
        return parts[-1]

    @staticmethod
    def normalize_path(path):
        return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))

    @staticmethod
    def add_issue(row, severity, issue):
        row["issue_list"].append(issue)
        if SEVERITY_RANK[severity] > SEVERITY_RANK[row["status"]]:
            row["status"] = severity

    @staticmethod
    def write_detail(path, rows):
        fields = [
            "status", "file_path", "file_name", "file_size", "file_role",
            "accession", "extension", "checksum_algorithm", "checksum",
            "accession_state", "assembly_state", "annotation_state",
            "datafile_state", "datafile_id", "issues",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def write_summary(
        path,
        *,
        root,
        checksum_algorithm,
        filesystem_only,
        total,
        counts,
        detail_path,
    ):
        result = "FAIL" if counts["error"] else "PASS_WITH_WARNINGS" if counts["warning"] else "PASS"
        lines = [
            f"generated_at\t{timezone.now().isoformat()}",
            f"manual_files_path\t{root}",
            "read_only\ttrue",
            f"filesystem_only\t{str(filesystem_only).lower()}",
            f"checksum_algorithm\t{checksum_algorithm}",
            f"total\t{total}",
            f"ok\t{counts['ok']}",
            f"warning\t{counts['warning']}",
            f"error\t{counts['error']}",
            f"result\t{result}",
            f"detail_report\t{detail_path}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
