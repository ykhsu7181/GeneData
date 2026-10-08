import os
import tempfile
import time

from django.test import TestCase, override_settings

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation


class JBrowseConfigApiTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.manual_root = os.path.join(self.temporary_directory.name, "manual_files")
        self.derived_root = os.path.join(self.temporary_directory.name, "derived_data")
        os.makedirs(self.manual_root)
        os.makedirs(self.derived_root)
        self.settings_override = override_settings(
            MANUAL_FILES_DIR=self.manual_root,
            GENEDATA_DERIVED_DATA_DIR=self.derived_root,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 genome assembly",
            display_name="IR64",
            assembly_code="ASM_IR64",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="IR64 annotation",
            annotation_code="ANN_IR64",
            is_default=True,
        )
        self.genome = self._file(
            self.manual_root,
            "genome.IR64.fasta",
            "GENOME_IR64",
            b">Chr01\nACGT\n",
        )
        self.source_gff = self._file(
            self.manual_root,
            "annotation.IR64.gff",
            "ANNOTATION_IR64",
            b"Chr01\ttest\tgene\t1\t4\t.\t+\t.\tID=gene1\n",
        )
        self.fai = self._file(
            self.derived_root,
            os.path.join("jbrowse", "assemblies", "assembly-1", "reference.fasta.fai"),
            "FAI_IR64",
            b"Chr01\t4\t7\t4\t5\n",
        )
        self.gff3 = self._file(
            self.derived_root,
            os.path.join("jbrowse", "annotations", "annotation-1", "features.sorted.gff3.gz"),
            "GFF3_IR64",
            b"bgzip-placeholder",
        )
        self.tbi = self._file(
            self.derived_root,
            os.path.join("jbrowse", "annotations", "annotation-1", "features.sorted.gff3.gz.tbi"),
            "TBI_IR64",
            b"tabix-placeholder",
        )
        self._relation(self.genome, "assembly", self.assembly.id, "genome_fasta", True)
        self._relation(self.fai, "assembly", self.assembly.id, "genome_index")
        self._relation(self.source_gff, "annotation", self.annotation.id, "annotation", True)
        self._relation(
            self.gff3,
            "annotation",
            self.annotation.id,
            "jbrowse_annotation_gff3",
        )
        self._relation(
            self.tbi,
            "annotation",
            self.annotation.id,
            "jbrowse_annotation_tabix",
        )
        now = time.time()
        os.utime(self.genome.file_path, (now - 30, now - 30))
        os.utime(self.source_gff.file_path, (now - 30, now - 30))
        os.utime(self.fai.file_path, (now - 20, now - 20))
        os.utime(self.gff3.file_path, (now - 20, now - 20))
        os.utime(self.tbi.file_path, (now - 10, now - 10))

    def _file(self, root, relative_path, code, content):
        path = os.path.join(root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)
        return DataFile.objects.create(
            file_code=code,
            file_name=os.path.basename(path),
            file_path=path,
            file_size=len(content),
            is_current=True,
        )

    def _relation(self, data_file, related_type, related_id, role, primary=False):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=primary,
        )

    def test_ready_status_and_config_use_asset_urls_without_physical_paths(self):
        status_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-status/"
        )
        config_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/"
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "ready")
        self.assertTrue(status_response.json()["reference_ready"])
        self.assertTrue(status_response.json()["annotation_ready"])
        self.assertEqual(status_response.json()["default_location"], "Chr01:1..4")
        self.assertEqual(
            status_response.json()["track_ids"],
            [f"annotation-{self.annotation.id}-features"],
        )
        self.assertEqual(config_response.status_code, 200)
        payload = config_response.json()
        self.assertEqual(payload["assemblies"][0]["name"], f"assembly-{self.assembly.id}")
        self.assertNotIn("status", payload)
        self.assertNotIn("defaultLocation", payload)
        self.assertEqual(len(payload["tracks"]), 1)
        self.assertEqual(
            payload["defaultSession"]["views"],
            [{
                "id": f"assembly-{self.assembly.id}-linear-view",
                "type": "LinearGenomeView",
                "init": {
                    "assembly": f"assembly-{self.assembly.id}",
                    "loc": "Chr01:1..4",
                    "tracks": [f"annotation-{self.annotation.id}-features"],
                },
            }],
        )
        serialized = config_response.content.decode("utf-8")
        self.assertNotIn(self.temporary_directory.name, serialized)
        self.assertIn(f"browser-assets/{self.genome.id}/", serialized)
        self.assertIn(f"browser-assets/{self.fai.id}/", serialized)
        self.assertIn(f"browser-assets/{self.gff3.id}/", serialized)
        self.assertIn(f"browser-assets/{self.tbi.id}/", serialized)

    def test_no_annotation_returns_reference_only_configuration(self):
        self.annotation.delete()

        response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tracks"], [])
        self.assertEqual(
            response.json()["defaultSession"]["views"][0]["init"]["tracks"],
            [],
        )
        self.assertEqual(
            response.json()["assemblies"][0]["name"],
            f"assembly-{self.assembly.id}",
        )

    def test_stale_annotation_index_returns_conflict(self):
        future = time.time() + 60
        os.utime(self.source_gff.file_path, (future, future))

        response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["status"], "stale_index")
        self.assertTrue(response.json()["reference_ready"])
        self.assertFalse(response.json()["annotation_ready"])

    def test_missing_fasta_index_uses_public_status_name(self):
        FileRelation.objects.filter(
            file=self.fai,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role="genome_index",
        ).delete()

        status_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-status/"
        )
        config_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/"
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "missing_fasta_index")
        self.assertEqual(config_response.status_code, 409)

    def test_invalid_annotation_parameter_returns_400(self):
        response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/",
            {"annotation_id": "not-an-integer"},
        )

        self.assertEqual(response.status_code, 400)

    def test_explicit_nondefault_annotation_can_be_selected(self):
        alternate = Annotation.objects.create(
            assembly=self.assembly,
            accession=self.accession,
            name="IR64 alternate annotation",
            annotation_code="ANN_IR64_ALT",
            is_default=False,
        )
        for source_file, role in (
            (self.source_gff, "annotation"),
            (self.gff3, "jbrowse_annotation_gff3"),
            (self.tbi, "jbrowse_annotation_tabix"),
        ):
            self._relation(source_file, "annotation", alternate.id, role)

        response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/",
            {"annotation_id": alternate.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["tracks"][0]["trackId"],
            f"annotation-{alternate.id}-features",
        )

    def test_hidden_placeholder_and_foreign_annotation_are_not_exposed(self):
        placeholder = Assembly.objects.create(
            accession=self.accession,
            name="default",
            assembly_code=None,
            is_default=False,
        )
        other_accession = Accession.objects.create(accession="OTHER")
        other_assembly = Assembly.objects.create(
            accession=other_accession,
            name="Other assembly",
            assembly_code="ASM_OTHER",
        )
        foreign_annotation = Annotation.objects.create(
            assembly=other_assembly,
            accession=other_accession,
            name="Other annotation",
            annotation_code="ANN_OTHER",
            is_default=True,
        )

        hidden_response = self.client.get(
            f"/gd/api/files/assemblies/{placeholder.id}/jbrowse-status/"
        )
        foreign_response = self.client.get(
            f"/gd/api/files/assemblies/{self.assembly.id}/jbrowse-config/",
            {"annotation_id": foreign_annotation.id},
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(foreign_response.status_code, 409)
        self.assertEqual(foreign_response.json()["status"], "annotation_not_found")
