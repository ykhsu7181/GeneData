import os
import tempfile

from django.test import TestCase, override_settings

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation


class JBrowseAssetApiTestCase(TestCase):
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
            GENEDATA_JBROWSE_MANUAL_INTERNAL_PREFIX="/_protected_manual_files/",
            GENEDATA_JBROWSE_DERIVED_INTERNAL_PREFIX="/_protected_derived_data/",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="IR64 genome assembly",
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

    def _file(self, root, relative_path, code, content=b"data"):
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

    def _relation(self, data_file, related_type, related_id, role):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=True,
        )

    def test_manual_fasta_returns_internal_redirect_without_streaming_body(self):
        data_file = self._file(
            self.manual_root,
            "genome.IR64.fasta",
            "GENOME_IR64",
            b">Chr01\nACGT\n",
        )
        self._relation(data_file, "assembly", self.assembly.id, "genome")

        response = self.client.get(
            f"/gd/api/files/browser-assets/{data_file.id}/",
            HTTP_RANGE="bytes=0-3",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_manual_files/genome.IR64.fasta",
        )
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response.content, b"")
        self.assertFalse(response.streaming)

    def test_derived_annotation_uses_encoded_internal_path(self):
        data_file = self._file(
            self.derived_root,
            os.path.join("jbrowse", "annotations", "注释 1.gff3.gz"),
            "JBROWSE_GFF3_IR64",
        )
        self._relation(
            data_file,
            "annotation",
            self.annotation.id,
            "jbrowse_annotation_gff3",
        )

        response = self.client.get(f"/gd/api/files/browser-assets/{data_file.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/gzip")
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_derived_data/jbrowse/annotations/%E6%B3%A8%E9%87%8A%201.gff3.gz",
        )

    def test_noncurrent_disallowed_unbound_and_outside_files_return_404(self):
        outside_root = os.path.join(self.temporary_directory.name, "outside")
        os.makedirs(outside_root)
        cases = []

        noncurrent = self._file(self.manual_root, "old.fasta", "OLD", b">Chr01\nA\n")
        noncurrent.is_current = False
        noncurrent.save(update_fields=["is_current"])
        self._relation(noncurrent, "assembly", self.assembly.id, "genome_fasta")
        cases.append(noncurrent)

        disallowed = self._file(self.manual_root, "notes.txt", "NOTES")
        self._relation(disallowed, "assembly", self.assembly.id, "other")
        cases.append(disallowed)

        mismatched = self._file(self.manual_root, "fake.txt", "MISMATCHED")
        self._relation(mismatched, "assembly", self.assembly.id, "genome_fasta")
        cases.append(mismatched)

        unbound = self._file(self.manual_root, "unbound.fasta", "UNBOUND", b">Chr01\nA\n")
        cases.append(unbound)

        outside = self._file(outside_root, "outside.fasta", "OUTSIDE", b">Chr01\nA\n")
        self._relation(outside, "assembly", self.assembly.id, "genome_fasta")
        cases.append(outside)

        for data_file in cases:
            with self.subTest(file_code=data_file.file_code):
                response = self.client.get(
                    f"/gd/api/files/browser-assets/{data_file.id}/"
                )
                self.assertEqual(response.status_code, 404)

    def test_replaced_placeholder_relation_does_not_grant_access(self):
        placeholder = Assembly.objects.create(
            accession=self.accession,
            name="default",
            assembly_code=None,
            is_default=False,
        )
        data_file = self._file(
            self.manual_root,
            "genome.placeholder.fasta",
            "PLACEHOLDER_GENOME",
            b">Chr01\nA\n",
        )
        self._relation(data_file, "assembly", placeholder.id, "genome_fasta")

        response = self.client.get(f"/gd/api/files/browser-assets/{data_file.id}/")

        self.assertEqual(response.status_code, 404)
