import csv
import hashlib
import unicodedata
from collections import Counter, defaultdict
from io import StringIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from files.models import DataFile
from files.services.ingestion.file_parser import parse_ingestion_filename


MANIFEST_FIELDS = (
    "file_path",
    "file_role",
    "accession",
    "assembly_code",
    "annotation_code",
    "sample_code",
    "dataset_code",
    "md5",
)
COVERAGE_FIELDS = (
    "line_number",
    "file_name",
    "status",
    "base_match_count",
    "file_role",
    "accession",
    "assembly_code",
    "annotation_code",
    "existing_datafile_count",
    "existing_file_codes",
    "review_reason",
)
REVIEW_FIELDS = (
    "line_number",
    "file_name",
    "proposed_file_path",
    "proposed_file_role",
    "parsed_accession",
    "status",
    "review_reason",
)


class Command(BaseCommand):
    help = (
        "Prepare a read-only registration candidate manifest by reconciling an "
        "authoritative file-name list with an approved base file manifest."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file-list", required=True)
        parser.add_argument("--base-manifest", required=True)
        parser.add_argument("--manual-files-root", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        file_list_path = _input_file(options["file_list"], "File list")
        base_manifest_path = _input_file(
            options["base_manifest"], "Base manifest"
        )
        output = Path(options["output"]).expanduser().resolve()
        if output.exists() and not output.is_dir():
            raise CommandError(f"Output is not a directory: {output}")
        output.mkdir(parents=True, exist_ok=True)

        manual_root = str(options["manual_files_root"]).rstrip("/\\")
        if not manual_root:
            raise CommandError("Manual files root must not be empty.")

        names = _read_names(file_list_path)
        base_rows = _read_base_manifest(base_manifest_path)
        input_counts = Counter(_normalize(name) for _, name in names)
        base_by_name = defaultdict(list)
        for row in base_rows:
            base_by_name[_normalize(_basename(row["file_path"]))].append(row)

        datafiles_by_name = defaultdict(list)
        for file_code, file_name in DataFile.objects.order_by(
            "file_code", "id"
        ).values_list("file_code", "file_name"):
            datafiles_by_name[_normalize(file_name)].append(file_code)

        coverage_rows = []
        review_rows = []
        candidate_rows = []
        counters = Counter()
        source_names = set()
        for line_number, file_name in names:
            normalized = _normalize(file_name)
            source_names.add(normalized)
            matches = base_by_name.get(normalized, [])
            parsed = parse_ingestion_filename(file_name)
            status, reason = _classify(
                file_name=file_name,
                normalized=normalized,
                input_count=input_counts[normalized],
                base_matches=matches,
                base_path_allowed=(
                    len(matches) != 1
                    or _path_is_under_root(matches[0]["file_path"], manual_root)
                ),
                parsed=parsed,
            )
            counters[status] += 1

            matched = matches[0] if len(matches) == 1 else {}
            file_codes = datafiles_by_name.get(normalized, [])
            coverage_rows.append({
                "line_number": line_number,
                "file_name": file_name,
                "status": status,
                "base_match_count": len(matches),
                "file_role": matched.get("file_role", "") or (
                    parsed.get("file_role", "") if parsed else ""
                ),
                "accession": matched.get("accession", "") or (
                    parsed.get("accession_code", "") if parsed else ""
                ),
                "assembly_code": matched.get("assembly_code", ""),
                "annotation_code": matched.get("annotation_code", ""),
                "existing_datafile_count": len(file_codes),
                "existing_file_codes": ",".join(file_codes),
                "review_reason": reason,
            })

            if status == "READY_FROM_BASE_MANIFEST":
                candidate_rows.append({key: matched.get(key, "") for key in MANIFEST_FIELDS})
            else:
                review_rows.append({
                    "line_number": line_number,
                    "file_name": file_name,
                    "proposed_file_path": (
                        "" if status == "INVALID_FILE_NAME"
                        else f"{manual_root}/{file_name}"
                    ),
                    "proposed_file_role": parsed.get("file_role", "") if parsed else "",
                    "parsed_accession": parsed.get("accession_code", "") if parsed else "",
                    "status": status,
                    "review_reason": reason,
                })

        base_only_count = sum(
            len(rows)
            for normalized, rows in base_by_name.items()
            if normalized not in source_names
        )
        _write_tsv(output / "files.registration.candidate.tsv", MANIFEST_FIELDS, candidate_rows)
        _write_tsv(output / "files.registration.coverage.tsv", COVERAGE_FIELDS, coverage_rows)
        _write_tsv(output / "files.registration.review.tsv", REVIEW_FIELDS, review_rows)
        _write_summary(
            output / "REGISTRATION_SUMMARY.md",
            file_list_path=file_list_path,
            base_manifest_path=base_manifest_path,
            names=names,
            base_rows=base_rows,
            counters=counters,
            base_only_count=base_only_count,
        )
        _write_checksums(output)

        self.stdout.write(f"TOTAL_INPUT_NAMES\t{len(names)}")
        self.stdout.write(f"BASE_MANIFEST_ROWS\t{len(base_rows)}")
        for status, count in sorted(counters.items()):
            self.stdout.write(f"{status}\t{count}")
        self.stdout.write(f"BASE_ONLY_ROWS\t{base_only_count}")
        self.stdout.write(f"output\t{output}")


def _classify(
    *,
    file_name,
    normalized,
    input_count,
    base_matches,
    base_path_allowed,
    parsed,
):
    if not normalized or "/" in file_name or "\\" in file_name:
        return "INVALID_FILE_NAME", "file_name_must_be_a_basename"
    if input_count > 1:
        return "DUPLICATE_INPUT_NAME", "duplicate_normalized_name_in_file_list"
    if len(base_matches) > 1:
        return "AMBIGUOUS_BASE_MANIFEST", "multiple_base_manifest_rows_match_file_name"
    if len(base_matches) == 1:
        if not base_path_allowed:
            return "BASE_PATH_OUTSIDE_ROOT", "base_manifest_path_outside_manual_files_root"
        return "READY_FROM_BASE_MANIFEST", "approved_mapping_reused"
    if parsed:
        return "MAPPING_REQUIRED", "new_business_file_requires_hierarchy_review"
    return "NON_BUSINESS_REVIEW", "unrecognized_name_requires_include_or_exclude_decision"


def _read_names(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CommandError("File list must be UTF-8 or UTF-8 with BOM.") from exc
    return [
        (line_number, value.strip())
        for line_number, value in enumerate(text.splitlines(), start=1)
        if value.strip()
    ]


def _read_base_manifest(path):
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except UnicodeDecodeError as exc:
        raise CommandError("Base manifest must be UTF-8 or UTF-8 with BOM.") from exc
    with handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = set(MANIFEST_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise CommandError(
                "Base manifest is missing columns: " + ", ".join(sorted(missing))
            )
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def _write_tsv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\t".join(fields) + "\n")
        for row in rows:
            buffer = StringIO(newline="")
            writer = csv.writer(buffer, delimiter="\t", lineterminator="")
            writer.writerow([row.get(field, "") for field in fields])
            handle.write(buffer.getvalue().rstrip("\t") + "\n")


def _write_summary(
    path,
    *,
    file_list_path,
    base_manifest_path,
    names,
    base_rows,
    counters,
    base_only_count,
):
    lines = [
        "# External file registration preparation",
        "",
        "This report is read-only. It does not register, publish, or modify warehouse files.",
        "",
        "## Provenance",
        "",
        f"- File-list SHA-256: `{_sha256(file_list_path)}`",
        f"- Base-manifest SHA-256: `{_sha256(base_manifest_path)}`",
        "",
        "## Coverage",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Input file names | {len(names)} |",
        f"| Base manifest rows | {len(base_rows)} |",
    ]
    for status, count in sorted(counters.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        f"| Base-only rows | {base_only_count} |",
        "",
        "`READY_FROM_BASE_MANIFEST` rows may proceed to production physical-file and checksum validation. All other rows require review before any database import.",
        "",
    ])
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines))


def _write_checksums(output):
    names = (
        "files.registration.candidate.tsv",
        "files.registration.coverage.tsv",
        "files.registration.review.tsv",
        "REGISTRATION_SUMMARY.md",
    )
    lines = [f"{_sha256(output / name)}  {name}" for name in names]
    with (output / "SHA256SUMS").open(
        "w", encoding="ascii", newline=""
    ) as handle:
        handle.write("\n".join(lines) + "\n")


def _input_file(value, label):
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise CommandError(f"{label} does not exist: {path}")
    return path


def _basename(value):
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1]


def _path_is_under_root(value, root):
    normalized_path = str(value or "").replace("\\", "/").rstrip("/").casefold()
    normalized_root = str(root or "").replace("\\", "/").rstrip("/").casefold()
    return bool(normalized_root) and (
        normalized_path == normalized_root
        or normalized_path.startswith(normalized_root + "/")
    )


def _normalize(value):
    return unicodedata.normalize("NFC", str(value or "").strip()).casefold()


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
