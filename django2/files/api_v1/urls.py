from django.urls import path

from files.api_v1.file_views import file_content, file_metadata


app_name = "files-api-v1"

urlpatterns = [
    path("files/<int:file_id>/", file_metadata, name="file-metadata"),
    path("files/<int:file_id>/content/", file_content, name="file-content"),
]
