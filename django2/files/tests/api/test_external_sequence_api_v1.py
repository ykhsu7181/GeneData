import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import Accession, Assembly, DataAccessToken, DataFile, FileRelation
from files.services.fasta_index_service import build_fasta_index


class ExternalSequenceApiV1Tests(TestCase):
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

        self.accession = Accession.objects.create(accession="TEST")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="TEST v1",
            assembly_code="ASM_TEST",
            is_default=True,
        )
        self.fasta_path = self.root / "genome.TEST.fasta"
        self.fasta_path.write_bytes(b">Chr01\nACGTAC\nGTAA\n>Chr02\nTTTT\n")
        index_path, _entries = build_fasta_index(str(self.fasta_path))
        self.index_path = Path(index_path)
        self.genome = self.make_file("GENOME", self.fasta_path)
        self.index = self.make_file("INDEX", self.index_path)
        self.add_relation(self.genome, "genome_fasta", True)
        self.add_relation(self.index, "genome_index", False)
        _token, self.raw_token = DataAccessToken.issue(
            name="sequence-test",
            scopes=[DataAccessToken.SCOPE_SEQUENCE_READ],
        )

    def make_file(self, code, path, **overrides):
        content = path.read_bytes()
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
        return DataFile.objects.create(**values)

    def add_relation(self, data_file, role, is_primary):
        return FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            related_code=self.assembly.assembly_code,
            file_role=role,
            is_primary=is_primary,
        )

    def bearer(self, raw_token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_token or self.raw_token}"}

    def get_region(self, params=None, request_headers=None):
        if request_headers is None:
            request_headers = self.bearer()
        return self.client.get(
            "/gd/api/v1/assemblies/ASM_TEST/sequence/",
            params or {"sequence": "Chr01", "start": 5, "end": 9},
            **request_headers,
        )

    def test_returns_one_based_inclusive_indexed_fasta_region(self):
        response = self.get_region()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/x-fasta")
        self.assertEqual(response["X-Coordinate-System"], "1-based-inclusive")
        self.assertEqual(response["X-Sequence-Id"], "Chr01")
        self.assertEqual(response.content, b">ASM_TEST|Chr01:5-9\nACGTA\n")

    def test_requires_sequence_scope(self):
        _token, wrong_scope = DataAccessToken.issue(
            name="metadata-only-sequence",
            scopes=[DataAccessToken.SCOPE_METADATA_READ],
        )

        anonymous = self.get_region(request_headers={})
        forbidden = self.get_region(request_headers=self.bearer(wrong_scope))

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["code"], "authentication_required")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["code"], "insufficient_scope")

    def test_rejects_invalid_or_out_of_bounds_coordinates(self):
        cases = (
            ({"sequence": "Chr01", "start": 0, "end": 2}, "invalid_region"),
            ({"sequence": "Chr01", "start": 4, "end": 3}, "invalid_region"),
            ({"sequence": "Chr01", "start": "x", "end": 3}, "invalid_region"),
            ({"sequence": "Chr01", "start": 1, "end": 11}, "invalid_region"),
        )
        for params, code in cases:
            with self.subTest(params=params):
                response = self.get_region(params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["code"], code)

    def test_rejects_missing_sequence_and_unknown_assembly(self):
        missing_sequence = self.get_region(
            {"sequence": "Chr99", "start": 1, "end": 2}
        )
        unknown_assembly = self.client.get(
            "/gd/api/v1/assemblies/UNKNOWN/sequence/",
            {"sequence": "Chr01", "start": 1, "end": 2},
            **self.bearer(),
        )

        self.assertEqual(missing_sequence.status_code, 404)
        self.assertEqual(missing_sequence.json()["code"], "sequence_not_found")
        self.assertEqual(unknown_assembly.status_code, 404)
        self.assertEqual(unknown_assembly.json()["code"], "not_found")

    @override_settings(GENEDATA_SEQUENCE_MAX_BASES=4)
    def test_enforces_base_count_limit(self):
        response = self.get_region(
            {"sequence": "Chr01", "start": 1, "end": 5}
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["code"], "region_too_large")

    @override_settings(GENEDATA_SEQUENCE_MAX_RESPONSE_BYTES=20)
    def test_enforces_response_byte_limit(self):
        response = self.get_region(
            {"sequence": "Chr01", "start": 1, "end": 2}
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["code"], "response_too_large")

    def test_requires_released_fresh_index(self):
        self.index.publication_status = DataFile.PUBLICATION_DRAFT
        self.index.save(update_fields=["publication_status"])
        unpublished = self.get_region()
        self.index.publication_status = DataFile.PUBLICATION_RELEASED
        self.index.save(update_fields=["publication_status"])
        fasta_mtime = self.fasta_path.stat().st_mtime
        os.utime(self.index_path, (fasta_mtime - 10, fasta_mtime - 10))
        stale = self.get_region()

        self.assertEqual(unpublished.status_code, 404)
        self.assertEqual(unpublished.json()["code"], "fasta_index_required")
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["code"], "fasta_index_stale")

    def test_rejects_compressed_fasta(self):
        self.genome.file_name = "genome.TEST.fasta.gz"
        self.genome.save(update_fields=["file_name"])

        response = self.get_region()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "unsupported_fasta_compression")

    def test_sequence_requests_are_rate_limited_per_token(self):
        with patch(
            "files.api_v1.throttles.ExternalSequenceThrottle.get_rate",
            return_value="2/minute",
        ):
            responses = [self.get_region() for _index in range(3)]

        self.assertEqual(
            [response.status_code for response in responses],
            [200, 200, 429],
        )
