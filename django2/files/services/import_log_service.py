"""Shared helpers for management command import logs."""

from collections import OrderedDict
from datetime import datetime
import hashlib
from pathlib import Path
import subprocess


def add_provenance_arguments(parser):
    parser.add_argument("--batch-id", default="", help="Optional ingestion batch identifier.")
    parser.add_argument("--source", default="manifest", help="Source system or provider.")
    parser.add_argument("--source-version", default="", help="Optional source data version.")


def provenance_options(options):
    return {
        "batch_id": options.get("batch_id", ""),
        "source": options.get("source", "manifest"),
        "source_version": options.get("source_version", ""),
    }


def manifest_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_code_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[3],
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def import_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_import_stats(
    *,
    command,
    input_path,
    dry_run,
    scanned_count,
    created_count=0,
    reused_count=0,
    updated_count=0,
    skipped_count=0,
    unmapped_count=0,
    error_count=0,
    started_at=None,
    finished_at=None,
    batch_id="",
    source="manifest",
    source_version="",
    manifest_digest=None,
    code_commit=None,
    extra=None,
):
    """Return ordered stats with both generic and command-specific counters."""
    stats = OrderedDict()
    stats["command"] = command
    stats["input_path"] = input_path
    stats["batch_id"] = batch_id
    stats["source"] = source
    stats["source_version"] = source_version
    stats["manifest_sha256"] = manifest_digest or manifest_sha256(input_path)
    stats["code_commit"] = code_commit or current_code_commit()
    if started_at:
        stats["started_at"] = started_at
    if finished_at:
        stats["finished_at"] = finished_at
    stats["dry_run"] = dry_run
    stats["scanned_count"] = scanned_count
    stats["created_count"] = created_count
    stats["reused_count"] = reused_count
    stats["updated_count"] = updated_count
    stats["skipped_count"] = skipped_count
    stats["unmapped_count"] = unmapped_count
    stats["error_count"] = error_count
    for key, value in (extra or {}).items():
        stats[key] = value
    return stats


def write_key_value_report(path, stats):
    with open(path, "w", encoding="utf-8") as handle:
        for key, value in stats.items():
            handle.write(f"{key}: {value}\n")
