import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin

from . import __version__
from .api import ApiClient
from .downloader import download_batch, download_single, write_report
from .errors import DownloadError, GeneDataError, InputError, SnapshotMismatchError
from .manifests import (
    compare_selection_to_snapshot,
    read_selection_manifest,
    validate_snapshot_files,
)


DEFAULT_BASE_URL = "https://riceome.hzau.edu.cn"


def build_parser():
    parser = argparse.ArgumentParser(prog="genedata", description="Query and download GeneData files")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--base-url", default=os.environ.get("GENEDATA_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=positive_integer, default=60, help="HTTP timeout in seconds")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="search public resources")
    search_commands = search.add_subparsers(dest="resource", required=True)
    files = search_commands.add_parser("files", help="search the public file catalog")
    for name in ("name_contains", "accession", "assembly", "dataset", "role", "format"):
        files.add_argument("--" + name.replace("_", "-"))
    files.add_argument("--page", type=positive_integer, default=1)
    files.add_argument("--page-size", type=bounded_page_size, default=100)

    show = commands.add_parser("show", help="show authoritative file metadata")
    show.add_argument("file_code")

    download = commands.add_parser("download", help="download one public file or a selected manifest")
    download.add_argument("target", help="FILE_CODE, or the literal 'manifest'")
    download.add_argument("manifest_path", nargs="?", help="selected-files.tsv when target is manifest")
    download.add_argument("--output", default="genedata_cache")
    download.add_argument("--preview", action="store_true", help="resolve manifest without creating or downloading a batch")
    download.add_argument("--jobs", type=bounded_jobs, default=2)
    download.add_argument("--idempotency-key")
    return parser


def run(args, *, stdout=None):
    output = stdout or sys.stdout
    client = ApiClient(
        args.base_url,
        token=os.environ.get("GENEDATA_TOKEN"),
        timeout=args.timeout,
    )
    if args.command == "search":
        payload = client.get_json(
            "/gd/api/v1/files/",
            query={
                "name_contains": args.name_contains,
                "accession": args.accession,
                "assembly": args.assembly,
                "dataset": args.dataset,
                "role": args.role,
                "format": args.format,
                "page": args.page,
                "page_size": args.page_size,
            },
        )
        _print_json(payload, output)
        return 0
    if args.command == "show":
        _print_json(client.get_json("/gd/api/v1/files/%s/" % quote(args.file_code, safe="")), output)
        return 0
    if args.command == "download":
        if args.target == "manifest":
            if not args.manifest_path:
                raise InputError("download manifest requires selected-files.tsv")
            return _download_manifest(client, args, output)
        if args.manifest_path:
            raise InputError("unexpected argument after single file code")
        if args.preview:
            raise InputError("--preview is only valid for download manifest")
        metadata = client.get_json("/gd/api/v1/files/%s/" % quote(args.target, safe=""))
        report = download_single(client, metadata, args.output)
        _print_json(report, output)
        return 0
    raise InputError("unsupported command")


def _download_manifest(client, args, output):
    selection = read_selection_manifest(args.manifest_path)
    for row in selection:
        client.require_same_origin(urljoin(client.origin + "/", row["content_url"]))
    payload = {
        "name": Path(args.manifest_path).name[:255],
        "strict": True,
        "file_codes": [row["file_code"] for row in selection],
    }
    if args.preview:
        resolution = client.post_json("/gd/api/v1/file-batches/resolve/", payload)
        _print_json(resolution, output)
        summary = resolution.get("summary") or {}
        return 0 if not any(summary.get(key, 0) for key in ("ambiguous", "missing", "blocked")) else 5

    headers = {}
    if args.idempotency_key:
        headers["Idempotency-Key"] = args.idempotency_key
    batch = client.post_json("/gd/api/v1/file-batches/", payload, headers=headers)
    batch_id = str(batch.get("batch_id") or "")
    manifest_path = str(batch.get("manifest_url") or "")
    manifest_tsv_path = str(batch.get("manifest_tsv_url") or "")
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", batch_id)
        or batch_id in {".", ".."}
        or not manifest_path
        or not manifest_tsv_path
    ):
        raise InputError("server returned an incomplete batch response")
    authoritative = client.get_json(manifest_path, authenticated=True)
    files = authoritative.get("files")
    validate_snapshot_files(files)
    for item in files:
        client.require_same_origin(urljoin(client.origin + "/", item["content_url"]))
    differences = compare_selection_to_snapshot(selection, files, base_url=client.origin)
    if differences:
        raise SnapshotMismatchError(
            "selection differs from the authoritative snapshot: %s; export the selection again"
            % "; ".join(differences[:10])
        )

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / ("batch-%s.json" % batch_id), batch)
    _write_json(output_dir / ("%s.manifest.json" % batch_id), authoritative)
    (output_dir / ("%s.manifest.tsv" % batch_id)).write_bytes(
        client.get_bytes(manifest_tsv_path, authenticated=True)
    )
    reports = download_batch(client, files, output_dir, jobs=args.jobs)
    report_path = output_dir / "download-report.tsv"
    write_report(report_path, reports)
    summary = {
        "batch_id": batch_id,
        "snapshot_sha256": authoritative.get("snapshot_sha256"),
        "downloaded": sum(row["status"] == "downloaded" for row in reports),
        "cached": sum(row["status"] == "cached" for row in reports),
        "failed": sum(row["status"] == "failed" for row in reports),
        "report": str(report_path),
    }
    _print_json(summary, output)
    if summary["failed"]:
        raise DownloadError("one or more files failed; inspect %s" % report_path)
    return 0


def main(argv=None):
    parser = build_parser()
    try:
        code = run(parser.parse_args(argv))
    except GeneDataError as exc:
        print("genedata: %s" % exc, file=sys.stderr)
        code = exc.exit_code
    raise SystemExit(code)


def positive_integer(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def bounded_page_size(value):
    parsed = positive_integer(value)
    if parsed > 500:
        raise argparse.ArgumentTypeError("must not exceed 500")
    return parsed


def bounded_jobs(value):
    parsed = positive_integer(value)
    if parsed > 4:
        raise argparse.ArgumentTypeError("must be between 1 and 4")
    return parsed


def _print_json(value, output):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), file=output)


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
