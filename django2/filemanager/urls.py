"""filemanager URL Configuration."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from files import views
from files.views import GenomeFileViewSet

try:
    from rest_framework.documentation import include_docs_urls
except Exception:
    include_docs_urls = None

try:
    import coreapi  # noqa: F401
    import coreschema  # noqa: F401
except Exception:
    DOCS_ENABLED = False
else:
    DOCS_ENABLED = include_docs_urls is not None


def debug_view(request):
    """Debug view to test if Django is receiving requests."""
    return JsonResponse(
        {
            "status": "Django is working",
            "path": request.path,
            "method": request.method,
            "headers": dict(request.headers),
        }
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("gd/api/files/", include("files.urls")),
    path("gd/api/admin/", include("files.urls")),
    path("gd/api/integrations/", include("integrations.urls")),
    path("api/files/", include("files.urls")),
    path("api/admin/", include("files.urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("gd/api/debug/", debug_view, name="debug"),
    path(
        "gd/api/manual_download/<str:filename>",
        views.download_manual_file,
        name="legacy-manual-download",
    ),
]

legacy_download_view = getattr(GenomeFileViewSet, "download_transcriptome", None)
if legacy_download_view is not None:
    urlpatterns.append(
        path(
            "gd/api/download/",
            GenomeFileViewSet.as_view({"get": "download_transcriptome"}),
            name="legacy-download",
        )
    )

if DOCS_ENABLED:
    urlpatterns.append(
        path("docs/", include_docs_urls(title="API Documentation")),
    )
