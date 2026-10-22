import json
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET


OPENAPI_PATH = Path(__file__).with_name("openapi.json")


@require_GET
def openapi_schema(request):
    with OPENAPI_PATH.open(encoding="utf-8") as source:
        schema = json.load(source)
    return JsonResponse(schema, json_dumps_params={"ensure_ascii": False})


@require_GET
def api_documentation(request):
    html = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GeneData External Data API v1</title></head>
<body>
<main>
<h1>GeneData External Data API v1</h1>
<p>机器可读 OpenAPI 3 契约：<a href="/gd/api/v1/openapi.json">/gd/api/v1/openapi.json</a></p>
<p>所有坐标均为 1-based inclusive。受保护接口使用 <code>Authorization: Bearer &lt;token&gt;</code>。</p>
<p>运维人员请同时参阅仓库中的 API 使用手册与运维手册。</p>
</main>
</body></html>"""
    return HttpResponse(html, content_type="text/html; charset=utf-8")
