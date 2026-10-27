import unittest

from genedata_cli.api import ApiClient, SameOriginRedirectHandler
from genedata_cli.errors import InputError


class ApiSafetyTests(unittest.TestCase):
    def test_rejects_credentials_and_cross_origin_content_urls(self):
        with self.assertRaisesRegex(InputError, "without credentials"):
            ApiClient("https://user:secret@example.test")

        client = ApiClient("https://example.test/base")
        with self.assertRaisesRegex(InputError, "cross-origin URL"):
            client.require_same_origin("https://attacker.test/file")

    def test_redirect_handler_rejects_cross_origin_before_copying_headers(self):
        handler = SameOriginRedirectHandler("https://example.test")

        with self.assertRaisesRegex(InputError, "cross-origin redirect"):
            handler.redirect_request(
                None, None, 302, "Found", {}, "https://attacker.test/collect"
            )


if __name__ == "__main__":
    unittest.main()
