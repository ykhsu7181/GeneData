"""Stable public URL helpers for the external data API."""

from urllib.parse import quote


def external_content_url(file_code):
    return f"/gd/api/v1/files/{quote(str(file_code), safe='')}/content/"
