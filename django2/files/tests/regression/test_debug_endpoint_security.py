import json

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve

from filemanager.urls import debug_urlpatterns, debug_view


class DebugEndpointSecurityTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_debug_url_is_not_registered_when_debug_is_false(self):
        patterns = debug_urlpatterns()
        self.assertEqual(patterns, [])
        with self.assertRaises(Resolver404):
            resolve("/gd/api/debug/", urlconf=tuple(patterns))

    @override_settings(DEBUG=True)
    def test_debug_url_is_registered_without_echoing_headers(self):
        patterns = debug_urlpatterns()
        match = resolve("/gd/api/debug/", urlconf=tuple(patterns))
        self.assertEqual(match.url_name, "debug")

        response = debug_view(RequestFactory().get("/gd/api/debug/", HTTP_AUTHORIZATION="secret"))
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["status"], "Django is working")
        self.assertNotIn("headers", payload)
