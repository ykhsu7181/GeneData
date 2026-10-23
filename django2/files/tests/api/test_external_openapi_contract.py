import json
from pathlib import Path

from django.test import SimpleTestCase

from files.api_v1.schema_views import OPENAPI_PATH


class ExternalOpenApiContractTests(SimpleTestCase):
    expected_paths = {
        "/gd/api/v1/accessions/{accession}/",
        "/gd/api/v1/accessions/{accession}/assemblies/",
        "/gd/api/v1/accessions/{accession}/files/",
        "/gd/api/v1/files/",
        "/gd/api/v1/files/manifest.tsv",
        "/gd/api/v1/files/{file_code}/",
        "/gd/api/v1/files/{file_code}/content/",
        "/gd/api/v1/datasets/{dataset}/manifest/",
        "/gd/api/v1/datasets/{dataset}/manifest.tsv",
        "/gd/api/v1/assemblies/{assembly}/sequence/",
        "/gd/api/v1/file-batches/resolve/",
        "/gd/api/v1/file-batches/",
        "/gd/api/v1/file-batches/{batch_id}/",
        "/gd/api/v1/file-batches/{batch_id}/manifest/",
        "/gd/api/v1/file-batches/{batch_id}/manifest.tsv",
        "/gd/api/v1/file-batches/{batch_id}/archives/",
        "/gd/api/v1/file-archives/{archive_id}/",
        "/gd/api/v1/file-archives/{archive_id}/content/",
    }

    def test_schema_is_openapi_3_and_covers_every_public_v1_operation(self):
        schema = json.loads(Path(OPENAPI_PATH).read_text(encoding="utf-8"))
        self.assertEqual(schema["openapi"], "3.0.3")
        self.assertEqual(set(schema["paths"]), self.expected_paths)
        self.assertIn("bearerAuth", schema["components"]["securitySchemes"])
        self.assertEqual(
            schema["paths"]["/gd/api/v1/files/{file_code}/content/"]["get"]["security"],
            [{"bearerAuth": []}],
        )
        self.assertEqual(
            schema["paths"]["/gd/api/v1/files/"]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/FileCatalog",
        )
        sequence = schema["paths"]["/gd/api/v1/assemblies/{assembly}/sequence/"]["get"]
        self.assertEqual(sequence["responses"]["200"]["content"]["text/x-fasta"]["schema"]["type"], "string")
        self.assertIn("413", sequence["responses"])
        batch_create = schema["paths"]["/gd/api/v1/file-batches/"]["post"]
        self.assertEqual(batch_create["security"], [{"bearerAuth": []}])
        self.assertIn("Idempotency-Key", [item["name"] for item in batch_create["parameters"]])
        archive_create = schema["paths"]["/gd/api/v1/file-batches/{batch_id}/archives/"]["post"]
        self.assertEqual(archive_create["responses"]["202"]["content"]["application/json"]["schema"]["$ref"], "#/components/schemas/FileArchive")

    def test_schema_and_human_documentation_are_served(self):
        schema_response = self.client.get("/gd/api/v1/openapi.json")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.json()["info"]["version"], "1.4.0")

        docs_response = self.client.get("/docs/api/")
        self.assertEqual(docs_response.status_code, 200)
        self.assertContains(docs_response, "/gd/api/v1/openapi.json")
        self.assertNotContains(docs_response, "cdn")
