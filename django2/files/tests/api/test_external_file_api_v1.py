import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import DataAccessToken, DataFile, Dataset, FileRelation


@override_settings(GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=True)
class ExternalFileApiV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "protected"
        self.root.mkdir()
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def make_file(self, code="PUBLIC", content=b">chr1\nACGT\n", **overrides):
        relative = overrides.pop("relative", f"folder/{code}.fasta")
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        values = {
            "file_code": code,
            "file_name": path.name,
            "file_path": str(path),
            "file_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "access_level": DataFile.ACCESS_LEVEL_PUBLIC,
            "publication_status": DataFile.PUBLICATION_RELEASED,
            "published_at": timezone.now(),
            "is_current": True,
        }
        values.update(overrides)
        data_file = DataFile.objects.create(**values)
        FileRelation.objects.create(
            file=data_file,
            related_type="other",
            related_id="test",
            file_role="genome_fasta",
            is_primary=True,
        )
        return data_file

    def issue(self, scopes, access_tier=DataAccessToken.ACCESS_TIER_PUBLIC):
        return DataAccessToken.issue(
            name=f"api-{DataAccessToken.objects.count()}",
            scopes=scopes,
            access_tier=access_tier,
        )

    @staticmethod
    def bearer(raw_token):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token}"}

    def test_public_metadata_is_anonymous_and_never_exposes_physical_path(self):
        data_file = self.make_file()

        response = self.client.get(f"/gd/api/v1/files/{data_file.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], data_file.id)
        self.assertEqual(payload["format"], "FASTA")
        self.assertEqual(payload["role"], "genome_fasta")
        self.assertEqual(payload["size"], 11)
        self.assertEqual(payload["content_version"], f"sha256:{data_file.sha256}")
        self.assertEqual(payload["content_url"], "/gd/api/v1/files/PUBLIC/content/")
        self.assertNotIn("file_path", payload)
        self.assertNotIn(str(self.root), str(payload))

    def test_draft_and_missing_physical_files_are_not_discoverable(self):
        draft = self.make_file("DRAFT", publication_status=DataFile.PUBLICATION_DRAFT)
        missing = self.make_file("MISSING")
        os.unlink(missing.file_path)

        for data_file in (draft, missing):
            with self.subTest(data_file=data_file.file_code):
                response = self.client.get(f"/gd/api/v1/files/{data_file.id}/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["code"], "not_found")

    def test_public_content_allows_anonymous_get_and_head(self):
        data_file = self.make_file()

        get_response = self.client.get(f"/gd/api/v1/files/{data_file.id}/content/")
        head_response = self.client.head(f"/gd/api/v1/files/{data_file.id}/content/")

        for response in (get_response, head_response):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Length"], "11")
            self.assertEqual(response["Accept-Ranges"], "bytes")
            self.assertIn("attachment", response["Content-Disposition"])

    @override_settings(GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=False)
    def test_feature_switch_restores_file_read_token_requirement(self):
        data_file = self.make_file()

        response = self.client.get(f"/gd/api/v1/files/{data_file.id}/content/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
        self.assertEqual(response.json()["code"], "authentication_required")

    def test_valid_token_returns_protected_get_and_head_headers(self):
        data_file = self.make_file(relative="IR64 folder/genome IR64.fasta")
        token, raw_token = self.issue([DataAccessToken.SCOPE_FILE_READ])

        get_response = self.client.get(
            f"/gd/api/v1/files/{data_file.id}/content/",
            **self.bearer(raw_token),
        )
        head_response = self.client.head(
            f"/gd/api/v1/files/{data_file.id}/content/",
            **self.bearer(raw_token),
        )

        for response in (get_response, head_response):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response["X-Accel-Redirect"],
                "/_protected_test/IR64%20folder/genome%20IR64.fasta",
            )
            self.assertEqual(response["Content-Length"], "11")
            self.assertEqual(response["Accept-Ranges"], "bytes")
            self.assertEqual(response["Content-Type"], "text/x-fasta")
            self.assertEqual(response["ETag"], f'"sha256-{data_file.sha256}"')
            self.assertIn("attachment", response["Content-Disposition"])
            self.assertIn("Last-Modified", response)
        self.assertEqual(get_response.content, b"")
        self.assertEqual(head_response.content, b"")
        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

    def test_stable_file_code_route_and_numeric_compatibility_match(self):
        data_file = self.make_file(code="FILE000013")

        stable = self.client.get("/gd/api/v1/files/FILE000013/")
        legacy = self.client.get(f"/gd/api/v1/files/{data_file.id}/")

        self.assertEqual(stable.status_code, 200)
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(stable.json(), legacy.json())
        self.assertEqual(
            stable.json()["content_url"],
            "/gd/api/v1/files/FILE000013/content/",
        )

    def test_matching_etag_returns_not_modified_without_protected_handoff(self):
        data_file = self.make_file(code="FILE000014")
        _token, raw_token = self.issue([DataAccessToken.SCOPE_FILE_READ])

        response = self.client.get(
            "/gd/api/v1/files/FILE000014/content/",
            HTTP_IF_NONE_MATCH=f'"sha256-{data_file.sha256}"',
            **self.bearer(raw_token),
        )

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response["ETag"], f'"sha256-{data_file.sha256}"')
        self.assertNotIn("X-Accel-Redirect", response)

    def test_invalid_or_revoked_token_returns_401(self):
        data_file = self.make_file()
        token, raw_token = self.issue([DataAccessToken.SCOPE_FILE_READ])
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])

        for supplied in ("not-a-token", raw_token):
            with self.subTest(token=supplied[:12]):
                response = self.client.get(
                    f"/gd/api/v1/files/{data_file.id}/content/",
                    **self.bearer(supplied),
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["code"], "invalid_token")

    def test_internal_metadata_requires_internal_tier_and_scope(self):
        dataset = Dataset.objects.create(
            dataset_code="DS_INTERNAL_V1",
            visibility="lab_internal",
            status="released",
        )
        data_file = self.make_file(
            "INTERNAL",
            dataset=dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
        )
        _public, public_raw = self.issue([DataAccessToken.SCOPE_METADATA_READ])
        _internal, internal_raw = self.issue(
            [DataAccessToken.SCOPE_METADATA_READ],
            access_tier=DataAccessToken.ACCESS_TIER_INTERNAL,
        )

        anonymous = self.client.get(f"/gd/api/v1/files/{data_file.id}/")
        public = self.client.get(
            f"/gd/api/v1/files/{data_file.id}/", **self.bearer(public_raw)
        )
        internal = self.client.get(
            f"/gd/api/v1/files/{data_file.id}/", **self.bearer(internal_raw)
        )

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(public.status_code, 403)
        self.assertEqual(public.json()["code"], "insufficient_access_tier")
        self.assertEqual(internal.status_code, 200)
        self.assertEqual(internal.json()["dataset"], dataset.dataset_code)

    def test_internal_content_is_not_exposed_anonymously(self):
        dataset = Dataset.objects.create(
            dataset_code="DS_INTERNAL_CONTENT_V1",
            visibility="lab_internal",
            status="released",
        )
        data_file = self.make_file(
            "INTERNAL_CONTENT",
            dataset=dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
        )

        anonymous = self.client.get(f"/gd/api/v1/files/{data_file.id}/content/")

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["code"], "authentication_required")

    def test_content_requests_are_rate_limited_per_token(self):
        cache.clear()
        data_file = self.make_file()
        _token, raw_token = self.issue([DataAccessToken.SCOPE_FILE_READ])

        with patch(
            "files.api_v1.throttles.ExternalAuthenticatedContentThrottle.get_rate",
            return_value="2/minute",
        ):
            responses = [
                self.client.head(
                    f"/gd/api/v1/files/{data_file.id}/content/",
                    **self.bearer(raw_token),
                )
                for _index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429])
        self.assertIn("Retry-After", responses[-1])
        self.assertNotIn(raw_token, responses[-1].content.decode("utf-8"))
        self.assertNotIn(str(self.root), responses[-1].content.decode("utf-8"))

    def test_anonymous_content_requests_use_ip_burst_limit(self):
        cache.clear()
        data_file = self.make_file()

        with patch(
            "files.api_v1.throttles.ExternalAnonymousContentThrottle.get_rate",
            return_value="2/minute",
        ):
            responses = [
                self.client.head(f"/gd/api/v1/files/{data_file.id}/content/")
                for _index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429])
        self.assertIn("Retry-After", responses[-1])

    def test_anonymous_content_requests_use_ip_daily_limit(self):
        cache.clear()
        data_file = self.make_file()

        with patch(
            "files.api_v1.throttles.ExternalAnonymousContentDailyThrottle.get_rate",
            return_value="2/day",
        ):
            responses = [
                self.client.head(f"/gd/api/v1/files/{data_file.id}/content/")
                for _index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429])
        self.assertIn("Retry-After", responses[-1])
