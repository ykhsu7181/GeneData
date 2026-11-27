import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from django.utils.http import http_date


@dataclass(frozen=True)
class ProtectedFileLocation:
    allowed: bool
    reason: str
    root_name: str = ""
    resolved_path: str = ""
    internal_uri: str = ""


def resolve_protected_datafile_path(data_file, *, roots=None):
    """Map a DataFile to an internal URI without root or symlink escape."""
    if not data_file.file_path:
        return ProtectedFileLocation(False, "file_path_missing")

    try:
        candidate = Path(data_file.file_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return ProtectedFileLocation(False, "file_missing")
    if not candidate.is_file():
        return ProtectedFileLocation(False, "not_a_file")

    configured_roots = roots if roots is not None else getattr(
        settings, "GENEDATA_PROTECTED_FILE_ROOTS", {}
    )
    normalized_roots = []
    for root_name, root_config in configured_roots.items():
        try:
            root = Path(root_config["path"]).resolve(strict=True)
        except (KeyError, TypeError, OSError, RuntimeError, ValueError):
            continue
        if root.is_dir():
            normalized_roots.append((root_name, root_config, root))

    for root_name, root_config, root in sorted(
        normalized_roots,
        key=lambda item: len(item[2].parts),
        reverse=True,
    ):
        try:
            relative_path = candidate.relative_to(root)
        except ValueError:
            continue

        internal_prefix = str(root_config.get("internal_uri") or "").strip()
        if not internal_prefix.startswith("/"):
            continue
        internal_uri = (
            f"{internal_prefix.rstrip('/')}/"
            f"{quote(relative_path.as_posix(), safe='/')}"
        )
        return ProtectedFileLocation(
            allowed=True,
            reason="protected_root_match",
            root_name=str(root_name),
            resolved_path=str(candidate),
            internal_uri=internal_uri,
        )

    return ProtectedFileLocation(False, "outside_protected_roots")


def build_protected_file_response(
    data_file,
    *,
    roots=None,
    disposition="attachment",
    include_etag=True,
):
    """Build an authorization-free X-Accel response after callers grant access."""
    location = resolve_protected_datafile_path(data_file, roots=roots)
    if not location.allowed:
        return None
    try:
        stat = Path(location.resolved_path).stat()
    except OSError:
        return None

    response = HttpResponse(status=200, content_type=content_type_for(data_file.file_name))
    response["X-Accel-Redirect"] = location.internal_uri
    response["Content-Disposition"] = content_disposition(data_file.file_name, disposition)
    response["Content-Length"] = str(stat.st_size)
    response["Last-Modified"] = http_date(stat.st_mtime)
    response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    if include_etag and data_file.content_version:
        response["ETag"] = f'"sha256-{data_file.sha256.lower()}"'
    return response


def content_type_for(file_name):
    normalized = str(file_name or "").lower()
    if normalized.endswith((".fa", ".fasta", ".fna")):
        return "text/x-fasta"
    if normalized.endswith((".gff", ".gff3")):
        return "text/x-gff3"
    if normalized.endswith((".gff.gz", ".gff3.gz", ".gz")):
        return "application/gzip"
    content_type, _encoding = mimetypes.guess_type(normalized)
    return content_type or "application/octet-stream"


def content_disposition(file_name, disposition):
    if disposition not in {"attachment", "inline"}:
        raise ValueError("Unsupported content disposition")
    name = os.path.basename(file_name or "datafile")
    ascii_name = name.encode("ascii", errors="ignore").decode("ascii")
    ascii_name = "".join(
        character for character in ascii_name
        if character >= " " and character not in {'"', "\\"}
    ) or "datafile"
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
