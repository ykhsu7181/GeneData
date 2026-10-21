import mimetypes
import os
from pathlib import Path
from urllib.parse import quote

from django.http import HttpResponse
from django.utils.http import http_date

from files.services.datafile_access_service import resolve_protected_datafile_path


def build_protected_file_response(data_file, *, roots=None, disposition="attachment"):
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
    if data_file.content_version:
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
