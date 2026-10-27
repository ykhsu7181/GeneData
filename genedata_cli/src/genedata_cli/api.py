import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import ApiError, InputError, NetworkError


USER_AGENT = "genedata-cli/0.1.0"


class ApiClient:
    def __init__(self, base_url, *, token=None, timeout=60):
        parsed = urlsplit(str(base_url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise InputError("base URL must be an http(s) origin without credentials")
        self.origin = "%s://%s" % (parsed.scheme.lower(), parsed.netloc.lower())
        self.token = token or None
        self.timeout = timeout
        self.opener = build_opener(SameOriginRedirectHandler(self.origin))

    def url(self, path):
        resolved = urljoin(self.origin + "/", str(path))
        self.require_same_origin(resolved)
        return resolved

    def require_same_origin(self, value):
        parsed = urlsplit(str(value))
        origin = "%s://%s" % (parsed.scheme.lower(), parsed.netloc.lower())
        if origin != self.origin:
            raise InputError("cross-origin URL rejected: %s" % value)
        return str(value)

    def get_json(self, path, *, query=None, authenticated=False):
        url = self.url(path)
        if query:
            cleaned = {key: value for key, value in query.items() if value not in (None, "")}
            if cleaned:
                url = "%s?%s" % (url, urlencode(cleaned))
        return self._json("GET", url, authenticated=authenticated)

    def post_json(self, path, payload, *, authenticated=True, headers=None):
        return self._json(
            "POST",
            self.url(path),
            payload=payload,
            authenticated=authenticated,
            headers=headers,
        )

    def get_bytes(self, path, *, authenticated=False):
        response = self.open(path, authenticated=authenticated)
        try:
            return response.read()
        finally:
            response.close()

    def open(self, path_or_url, *, authenticated=False, range_start=None):
        url = self.url(path_or_url) if str(path_or_url).startswith("/") else str(path_or_url)
        self.require_same_origin(url)
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if authenticated:
            if not self.token:
                raise InputError("GENEDATA_TOKEN is required for this operation")
            headers["Authorization"] = "Bearer %s" % self.token
        if range_start is not None and range_start > 0:
            headers["Range"] = "bytes=%d-" % range_start
        request = Request(url, headers=headers, method="GET")
        return self._open(request)

    def _json(self, method, url, *, payload=None, authenticated=False, headers=None):
        request_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.token:
                raise InputError("GENEDATA_TOKEN is required for this operation")
            request_headers["Authorization"] = "Bearer %s" % self.token
        request_headers.update(headers or {})
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        response = self._open(Request(url, data=body, headers=request_headers, method=method))
        try:
            raw = response.read()
        finally:
            response.close()
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("server returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ApiError("server returned an unexpected JSON document")
        return value

    def _open(self, request):
        try:
            return self.opener.open(request, timeout=self.timeout)
        except HTTPError as exc:
            try:
                raw = exc.read(1024 * 1024)
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                payload = {}
            detail = payload.get("detail") if isinstance(payload, dict) else None
            code = payload.get("code") if isinstance(payload, dict) else None
            raise ApiError(
                detail or "server returned HTTP %d" % exc.code,
                status=exc.code,
                code=code,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise NetworkError("unable to reach GeneData: %s" % getattr(exc, "reason", exc)) from exc


class SameOriginRedirectHandler(HTTPRedirectHandler):
    def __init__(self, origin):
        super().__init__()
        self.origin = origin

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        redirect_origin = "%s://%s" % (parsed.scheme.lower(), parsed.netloc.lower())
        if redirect_origin != self.origin:
            raise InputError("cross-origin redirect rejected")
        return super().redirect_request(request, fp, code, msg, headers, newurl)
