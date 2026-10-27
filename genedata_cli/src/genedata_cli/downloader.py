import csv
import hashlib
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .errors import DownloadError, InputError


REPORT_HEADERS = [
    "file_code", "file_name", "status", "size", "sha256", "local_path", "error_code",
]


def download_batch(client, files, output_dir, *, jobs=2):
    if jobs not in range(1, 5):
        raise InputError("jobs must be between 1 and 4")
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    targets = {}
    for item in files:
        target = batch_target(root, item)
        key = os.path.normcase(str(target))
        if key in targets and targets[key] != item["file_code"]:
            raise InputError("multiple files resolve to the same local path: %s" % target)
        targets[key] = item["file_code"]
    required = sum(
        int(item["size"])
        for item in files
        if not batch_target(root, item).is_file()
    )
    if shutil.disk_usage(root).free < required:
        raise DownloadError("insufficient free space for the authoritative batch snapshot")

    reports = [None] * len(files)
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(download_item, client, item, batch_target(root, item), authenticated=True): index
            for index, item in enumerate(files)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                reports[index] = future.result()
            except Exception as exc:  # Keep the remaining bounded downloads observable.
                item = files[index]
                reports[index] = _report(
                    item,
                    "failed",
                    batch_target(root, item),
                    getattr(exc, "code", None) or exc.__class__.__name__,
                )
    return reports


def download_single(client, metadata, output_dir):
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / safe_segment(metadata["file_name"], "file_name")
    return download_item(client, metadata, target, authenticated=False)


def download_item(client, item, target, *, authenticated):
    expected_size = int(item["size"])
    expected_sha = str(item["sha256"]).lower()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if target.stat().st_size == expected_size and sha256_file(target) == expected_sha:
            return _report(item, "cached", target, "")
        raise DownloadError("existing target does not match the authoritative checksum: %s" % target)
    partial = target.with_name(target.name + ".part")
    start = partial.stat().st_size if partial.is_file() else 0
    if start > expected_size:
        raise DownloadError("partial file is larger than the authoritative size: %s" % partial)
    if start == expected_size and start > 0:
        if sha256_file(partial) != expected_sha:
            raise DownloadError("complete partial file has an invalid SHA-256: %s" % partial)
        os.replace(str(partial), str(target))
        return _report(item, "downloaded", target, "")
    response = client.open(item["content_url"], authenticated=authenticated, range_start=start)
    try:
        status = getattr(response, "status", response.getcode())
        if start and status != 206:
            start = 0
            mode = "wb"
        else:
            mode = "ab" if start else "wb"
        with partial.open(mode) as destination:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                destination.write(chunk)
    finally:
        response.close()
    if partial.stat().st_size != expected_size:
        raise DownloadError("downloaded size does not match the authoritative manifest")
    if sha256_file(partial) != expected_sha:
        raise DownloadError("downloaded SHA-256 does not match the authoritative manifest")
    os.replace(str(partial), str(target))
    return _report(item, "downloaded", target, "")


def batch_target(root, item):
    accession = safe_segment(item.get("accession") or "_unclassified", "accession")
    assembly = safe_segment(item.get("assembly") or "_unassembled", "assembly")
    name = safe_segment(item["file_name"], "file_name")
    return root / accession / assembly / name


def safe_segment(value, field):
    text = str(value).strip()
    if (
        not text
        or text in {".", ".."}
        or "/" in text
        or "\\" in text
        or any(ord(character) < 32 or ord(character) == 127 for character in text)
    ):
        raise InputError("invalid %s in server manifest" % field)
    return text


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def write_report(path, reports):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_HEADERS, dialect="excel-tab", lineterminator="\n")
        writer.writeheader()
        writer.writerows([
            {key: _spreadsheet_safe(value) for key, value in report.items()}
            for report in reports
        ])


def _report(item, status, path, error_code):
    return {
        "file_code": item["file_code"],
        "file_name": item["file_name"],
        "status": status,
        "size": int(item["size"]),
        "sha256": str(item["sha256"]).lower(),
        "local_path": str(path),
        "error_code": error_code,
    }


def _spreadsheet_safe(value):
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
