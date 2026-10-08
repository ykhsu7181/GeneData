import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase


class AdminMutationSecurityTests(APITestCase):
    create_url = "/gd/api/admin/data-management/accession/"
    update_url = "/gd/api/admin/data-management/accession/IR64/update/"
    delete_url = "/gd/api/admin/data-management/accession/IR64/delete/"
    batch_delete_url = "/gd/api/admin/data-management/batch-delete/"
    upload_url = "/gd/api/admin/data-management/upload-file/"
    delete_file_url = "/gd/api/admin/data-management/delete-file/IR64/genome/"
    session_url = "/gd/api/admin/session/"
    login_url = "/gd/api/admin/login/"
    logout_url = "/gd/api/admin/logout/"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.settings_override = override_settings(MANUAL_FILES_DIR=self.temp_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        user_model = get_user_model()
        self.normal_user = user_model.objects.create_user(
            username="normal-user",
            password="normal-password",
            is_staff=False,
        )
        self.staff_user = user_model.objects.create_user(
            username="staff-user",
            password="staff-password",
            is_staff=True,
        )
        self.superuser = user_model.objects.create_superuser(
            username="super-user",
            password="super-password",
            email="super@example.com",
        )

    def mutation_requests(self):
        return (
            ("post", self.create_url, {"accession": "IR64"}, "json"),
            ("put", self.update_url, {"subPopulation": "XI"}, "json"),
            ("delete", self.delete_url, {}, "json"),
            ("post", self.batch_delete_url, {"accessions": ["IR64"]}, "json"),
            ("post", self.upload_url, {}, "multipart"),
            ("delete", self.delete_file_url, {}, "json"),
        )

    def csrf_token(self, client):
        response = client.get(self.session_url)
        self.assertEqual(response.status_code, 200)
        return client.cookies["csrftoken"].value

    def login_staff(self, client, username="staff-user", password="staff-password"):
        token = self.csrf_token(client)
        response = client.post(
            self.login_url,
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        return self.csrf_token(client)

    def test_anonymous_users_cannot_call_management_mutations(self):
        for method, url, data, request_format in self.mutation_requests():
            with self.subTest(method=method, url=url):
                client = APIClient(enforce_csrf_checks=True)
                response = getattr(client, method)(url, data, format=request_format)
                self.assertIn(response.status_code, (401, 403))

        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "supplymentary_data.txt")))

    def test_non_staff_users_cannot_call_management_mutations(self):
        for method, url, data, request_format in self.mutation_requests():
            with self.subTest(method=method, url=url):
                client = APIClient(enforce_csrf_checks=True)
                client.force_login(self.normal_user)
                token = self.csrf_token(client)
                response = getattr(client, method)(
                    url,
                    data,
                    format=request_format,
                    HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 403)

        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "supplymentary_data.txt")))

    def test_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            self.login_url,
            {"username": "staff-user", "password": "staff-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_staff_account_cannot_create_admin_session(self):
        client = APIClient(enforce_csrf_checks=True)
        token = self.csrf_token(client)
        response = client.post(
            self.login_url,
            {"username": "normal-user", "password": "normal-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", client.session)

    def test_staff_session_can_create_and_upload(self):
        client = APIClient(enforce_csrf_checks=True)
        token = self.login_staff(client)

        create_response = client.post(
            self.create_url,
            {"accession": "IR64", "subPopulation": "XI"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(create_response.status_code, 200)

        upload = SimpleUploadedFile("genome.IR64.fasta", b">Chr1\nACGT\n")
        upload_response = client.post(
            self.upload_url,
            {"accession": "IR64", "fileType": "genome", "file": upload},
            format="multipart",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(upload_response.status_code, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir.name, "genome.IR64.fasta")))

    def test_staff_mutation_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff_user)
        response = client.post(self.create_url, {"accession": "IR64"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_superuser_is_allowed_by_staff_policy(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        token = self.csrf_token(client)
        response = client.post(
            self.create_url,
            {"accession": "SUPERUSER_ACCESSION"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)

    def test_logout_ends_the_admin_session(self):
        client = APIClient(enforce_csrf_checks=True)
        token = self.login_staff(client)
        response = client.post(self.logout_url, {}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", client.session)

        denied = client.post(
            self.create_url,
            {"accession": "AFTER_LOGOUT"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertIn(denied.status_code, (401, 403))
