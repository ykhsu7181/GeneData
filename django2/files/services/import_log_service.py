"""Shared helpers for management command import logs."""

from collections import OrderedDict
from datetime import datetime


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
    extra=None,
):
    """Return ordered stats with both generic and command-specific counters."""
    stats = OrderedDict()
    stats["command"] = command
    stats["input_path"] = input_path
    stats["dry_run"] = dry_run
    if started_at:
        stats["started_at"] = started_at
    if finished_at:
        stats["finished_at"] = finished_at
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
