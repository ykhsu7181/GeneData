import csv
import re
from pathlib import Path
from urllib.parse import urljoin

from .errors import InputError


SELECTION_HEADERS = [
    "file_code", "file_name", "accession", "assembly", "dataset",
    "role", "format", "size", "sha256", "content_url",
]
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def read_selection_manifest(path, *, max_rows=1000):
    source = Path(path)
    try:
        handle = source.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        raise InputError("cannot read selection manifest: %s" % exc) from exc
    with handle:
        reader = csv.DictReader(handle, dialect="excel-tab")
        if reader.fieldnames != SELECTION_HEADERS:
            raise InputError("selection manifest has an invalid header")
        rows = []
        seen = set()
        for line_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise InputError("selection manifest row %d has an invalid column count" % line_number)
            file_code = row["file_code"].strip()
            if not file_code or any(character.isspace() or ord(character) < 32 for character in file_code):
                raise InputError("selection manifest row %d has an invalid file_code" % line_number)
            if not row["file_name"].strip():
                raise InputError("selection manifest row %d has an empty file_name" % line_number)
            try:
                size = int(row["size"])
            except ValueError as exc:
                raise InputError("selection manifest row %d has an invalid size" % line_number) from exc
            if size < 0:
                raise InputError("selection manifest row %d has a negative size" % line_number)
            sha256 = row["sha256"].strip().lower()
            if not SHA256_RE.fullmatch(sha256):
                raise InputError("selection manifest row %d has an invalid SHA-256" % line_number)
            content_url = row["content_url"].strip()
            if not content_url:
                raise InputError("selection manifest row %d has an empty content_url" % line_number)
            if file_code in seen:
                continue
            seen.add(file_code)
            normalized = dict(row)
            normalized.update(file_code=file_code, size=size, sha256=sha256, content_url=content_url)
            rows.append(normalized)
            if len(rows) > max_rows:
                raise InputError("selection manifest exceeds %d unique files" % max_rows)
    if not rows:
        raise InputError("selection manifest contains no files")
    return rows


def compare_selection_to_snapshot(selection, snapshot_files, *, base_url):
    differences = []
    selected_codes = [row["file_code"] for row in selection]
    snapshot_codes = [str(row.get("file_code") or "") for row in snapshot_files]
    if selected_codes != snapshot_codes:
        differences.append("file_code order or membership changed")
        return differences
    selected_by_code = {row["file_code"]: row for row in selection}
    for item in snapshot_files:
        code = str(item.get("file_code") or "")
        selected = selected_by_code[code]
        comparisons = (
            ("file_name", selected["file_name"], str(item.get("file_name") or "")),
            ("size", selected["size"], _integer(item.get("size"))),
            ("sha256", selected["sha256"], str(item.get("sha256") or "").lower()),
            (
                "content_url",
                urljoin(base_url.rstrip("/") + "/", selected["content_url"]),
                urljoin(base_url.rstrip("/") + "/", str(item.get("content_url") or "")),
            ),
        )
        for field, expected, actual in comparisons:
            if expected != actual:
                differences.append("%s %s changed" % (code, field))
    return differences


def validate_snapshot_files(files):
    if not isinstance(files, list) or not files:
        raise InputError("server batch manifest contains no files")
    required = {"file_code", "file_name", "size", "sha256", "content_url"}
    for position, item in enumerate(files, 1):
        if not isinstance(item, dict) or not required.issubset(item):
            raise InputError("server batch manifest item %d is invalid" % position)
        if _integer(item["size"]) < 0 or not SHA256_RE.fullmatch(str(item["sha256"])):
            raise InputError("server batch manifest item %d has invalid integrity fields" % position)


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
