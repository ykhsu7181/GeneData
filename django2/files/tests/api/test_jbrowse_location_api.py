import json
import os
import tempfile
import time
from pathlib import Path

from django.test import TestCase, override_settings

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation
from files.services.annotation_feature_index_service import (
    build_annotation_feature_index,
    feature_index_version,
)
from files.services.reference_name_service import build_refname_mapping


class JBrowseLocationApiTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.manual_root = Path(self.temporary_directory.name) / "manual"
        self.derived_root = Path(self.temporary_directory.name) / "derived"
        self.manual_root.mkdir()
        self.derived_root.mkdir()
        self.settings_override = override_settings(
            MANUAL_FILES_DIR=str(self.manual_root),
            GENEDATA_DERIVED_DATA_DIR=str(self.derived_root),
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.accession = Accession.objects.create(accession="W2275")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="W2275 assembly",
            display_name="W2275",
            assembly_code="ASM_W2275",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="W2275 annotation",
            annotation_code="ANN_W2275",
            is_default=True,
        )
        self.genome = self._file(
            self.manual_root / "W2275.fasta",
            "GENOME_W2275",
            ">GWHESLA00000001 chromosome OriSeqID=chr1 Len=2000\n" + "A" * 2000 + "\n",
        )
        self.source_gff = self._file(
            self.manual_root / "W2275.gff3",
            "ANNOTATION_W2275",
            "chr1\tEVM\tgene\t700\t900\t.\t-\t.\tID=gene1;Name=gene1\n",
        )
        self.fai = self._file(
            self.derived_root / "reference.fasta.fai",
            "FAI_W2275",
            "GWHESLA00000001\t2000\t59\t2000\t2001\n",
        )
        self.gff3 = self._file(
            self.derived_root / "features.sorted.gff3.gz",
            "GFF3_W2275",
            "placeholder",
        )
        self.tbi = self._file(
            self.derived_root / "features.sorted.gff3.gz.tbi",
            "TBI_W2275",
            "placeholder",
        )
        self._relation(self.genome, "assembly", self.assembly.id, "genome_fasta", True)
        self._relation(self.fai, "assembly", self.assembly.id, "genome_index", True)
        self._relation(self.source_gff, "annotation", self.annotation.id, "annotation", True)
        self._relation(self.gff3, "annotation", self.annotation.id, "jbrowse_annotation_gff3", True)
        self._relation(self.tbi, "annotation", self.annotation.id, "jbrowse_annotation_tabix", True)

        base = time.time() - 100
        os.utime(self.genome.file_path, (base, base))
        os.utime(self.source_gff.file_path, (base, base))
        os.utime(self.fai.file_path, (base + 10, base + 10))
        os.utime(self.gff3.file_path, (base + 10, base + 10))
        os.utime(self.tbi.file_path, (base + 20, base + 20))

        self.feature_index, _ = build_annotation_feature_index(self.annotation)
        self.feature = self.feature_index.features.get()
        build_refname_mapping(
            self.assembly,
            self.genome,
            self.fai,
            output_root=str(self.derived_root),
        )

    def _file(self, path, code, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            is_current=True,
        )

    @staticmethod
    def _relation(data_file, related_type, related_id, role, primary=False):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=primary,
        )

    def _url(self, *, assembly=None, annotation=None, feature=None):
        return (
            f"/gd/api/files/assemblies/{assembly or self.assembly.id}/"
            f"annotations/{annotation or self.annotation.id}/"
            f"features/{feature or self.feature.id}/jbrowse-location/"
        )

    def test_resolves_ori_seqid_to_jbrowse_refname_and_padded_location(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "assembly_id": self.assembly.id,
                "annotation_id": self.annotation.id,
                "feature_id": self.feature.id,
                "feature_index_version": feature_index_version(self.feature_index),
                "ref_name": "GWHESLA00000001",
                "feature_start": 700,
                "feature_end": 900,
                "view_start": 200,
                "view_end": 1400,
                "loc": "GWHESLA00000001:200-1400",
                "assembly_name": f"assembly-{self.assembly.id}",
                "track_id": f"annotation-{self.annotation.id}-features",
            },
        )

    def test_one_click_workflow_contract_from_query_through_browser_assets(self):
        status_url = f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-status/"
        selection = {"annotation_id": self.annotation.id}

        status_response = self.client.get(status_url, selection)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["status"], "ready")
        self.assertTrue(status_payload["location_ready"])
        self.assertEqual(status_payload["location_status"], "ready")

        query_response = self.client.get(
            "/gd/api/files/query/annotation-data/",
            {
                "assembly_id": self.assembly.id,
                "annotation_id": self.annotation.id,
                "chromosome": "chr1",
                "feature_type": "gene",
            },
        )
        self.assertEqual(query_response.status_code, 200)
        feature_id = query_response.json()["results"][0]["feature_id"]

        location_response = self.client.get(self._url(feature=feature_id))
        self.assertEqual(location_response.status_code, 200)
        location_payload = location_response.json()
        self.assertEqual(location_payload["loc"], "GWHESLA00000001:200-1400")
        self.assertEqual(location_payload["assembly_name"], status_payload["assembly_name"])
        self.assertIn(location_payload["track_id"], status_payload["track_ids"])

        config_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/",
            selection,
        )
        self.assertEqual(config_response.status_code, 200)
        config_payload = config_response.json()
        self.assertEqual(config_payload["assemblies"][0]["name"], location_payload["assembly_name"])
        self.assertEqual(config_payload["tracks"][0]["trackId"], location_payload["track_id"])

        serialized_config = json.dumps(config_payload)
        self.assertNotIn(self.temporary_directory.name, serialized_config)
        asset_uris = [
            config_payload["assemblies"][0]["sequence"]["adapter"]["fastaLocation"]["uri"],
            config_payload["assemblies"][0]["sequence"]["adapter"]["faiLocation"]["uri"],
            config_payload["tracks"][0]["adapter"]["gffGzLocation"]["uri"],
            config_payload["tracks"][0]["adapter"]["index"]["location"]["uri"],
        ]
        for asset_uri in asset_uris:
            with self.subTest(asset_uri=asset_uri):
                asset_response = self.client.get(asset_uri, HTTP_RANGE="bytes=0-0")
                self.assertEqual(asset_response.status_code, 200)
                self.assertEqual(asset_response["Accept-Ranges"], "bytes")
                self.assertTrue(asset_response["X-Accel-Redirect"].startswith("/_protected_"))
                self.assertEqual(asset_response.content, b"")

    def test_annotation_query_includes_feature_id(self):
        response = self.client.get(
            "/gd/api/files/query/annotation-data/",
            {
                "assembly_id": self.assembly.id,
                "annotation_id": self.annotation.id,
                "chromosome": "chr1",
                "feature_type": "gene",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["feature_id"], self.feature.id)

    def test_foreign_annotation_and_feature_are_indistinguishable_404(self):
        other_accession = Accession.objects.create(accession="OTHER")
        other_assembly = Assembly.objects.create(
            accession=other_accession, name="Other", assembly_code="ASM_OTHER"
        )
        other_annotation = Annotation.objects.create(
            assembly=other_assembly,
            accession=other_accession,
            name="Other annotation",
            annotation_code="ANN_OTHER",
        )

        wrong_annotation = self.client.get(
            self._url(annotation=other_annotation.id)
        )
        missing_feature = self.client.get(self._url(feature=999999))

        self.assertEqual(wrong_annotation.status_code, 404)
        self.assertEqual(missing_feature.status_code, 404)
        self.assertEqual(wrong_annotation.json(), missing_feature.json())

    def test_rejects_old_expected_index_version(self):
        response = self.client.get(
            self._url(), {"feature_index_version": "old-version"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "feature_index_version_conflict")

    def test_mapping_fingerprint_change_fails_closed(self):
        self.genome.md5 = "changed"
        self.genome.save(update_fields=["md5", "updated_at"])

        status_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-status/",
            {"annotation_id": self.annotation.id},
        )
        response = self.client.get(self._url())

        self.assertFalse(status_response.json()["location_ready"])
        self.assertEqual(status_response.json()["location_status"], "mapping_stale")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "mapping_stale")

    def test_missing_mapping_fails_closed(self):
        FileRelation.objects.filter(file_role="jbrowse_refname_aliases").delete()

        status_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-status/",
            {"annotation_id": self.annotation.id},
        )
        response = self.client.get(self._url())

        self.assertFalse(status_response.json()["location_ready"])
        self.assertEqual(status_response.json()["location_status"], "mapping_missing")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "mapping_missing")

    def test_ambiguous_alias_returns_409(self):
        relation = FileRelation.objects.select_related("file").get(
            file_role="jbrowse_refname_aliases"
        )
        mapping_path = Path(relation.file.file_path)
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
        payload["aliases"]["chr1"] = {
            "status": "ambiguous",
            "ref_names": ["GWHESLA00000001", "another-contig"],
        }
        mapping_path.write_text(json.dumps(payload), encoding="utf-8")

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "alias_ambiguous")

    def test_old_feature_id_is_rejected_after_index_rebuild(self):
        old_feature_id = self.feature.id
        rebuilt_index, changed = build_annotation_feature_index(
            self.annotation, force=True
        )

        self.assertTrue(changed)
        self.assertNotEqual(rebuilt_index.features.get().id, old_feature_id)
        response = self.client.get(self._url(feature=old_feature_id))
        self.assertEqual(response.status_code, 404)

    def test_not_ready_jbrowse_dependency_returns_503(self):
        FileRelation.objects.filter(
            file=self.tbi, file_role="jbrowse_annotation_tabix"
        ).delete()

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "jbrowse_not_ready")

    def test_coordinate_out_of_bounds_returns_422(self):
        self.feature.end = 2500
        self.feature.length = 1801
        self.feature.save(update_fields=["end", "length"])

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "coordinate_out_of_bounds")
