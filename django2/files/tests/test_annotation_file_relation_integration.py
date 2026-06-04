import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType, GenomeFile


class AnnotationFileRelationIntegrationTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.file_type = FileType.objects.create(name="GFF3", extension="gff3")
        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )
        self.annotation = Annotation.objects.create(
            assembly=self.assembly,
            name="default-annotation",
            standard_id="ANN-IR64",
            is_default=True,
        )

    def create_annotation_file(self, filename):
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("##gff-version 3\n")
            handle.write("chr1\tsource\tgene\t1\t10\t.\t+\t.\tID=gene1\n")
        return path

    def test_annotation_endpoint_uses_file_relation_file(self):
        new_path = self.create_annotation_file("annotation.new.IR64.gff3")
        old_path = self.create_annotation_file("annotation.old.IR64.gff3")
        data_file = DataFile.objects.create(
            file_code="FILE000020",
            file_name="annotation.new.IR64.gff3",
            file_path=new_path,
            file_size=os.path.getsize(new_path),
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            file_role="annotation",
        )
        GenomeFile.objects.create(
            name="annotation.old.IR64.gff3",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="annotation",
            file_path=old_path,
            file_type=self.file_type,
            size=os.path.getsize(old_path),
        )

        response = self.client.get(
            f"/gd/api/files/genome-files/get_annotation_data/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["seqid"], "chr1")
        self.assertEqual(payload["annotation_file"]["id"], data_file.id)
        self.assertEqual(payload["annotation_file"]["name"], "annotation.new.IR64.gff3")
        self.assertEqual(payload["annotation_file"]["file_path"], new_path)
        self.assertEqual(payload["annotation_file"]["category"], "annotation")
        self.assertEqual(payload["annotation_file"]["file_size"], os.path.getsize(new_path))
        self.assertEqual(payload["annotation_file"]["source"], "new_relation")

    def test_annotation_endpoint_falls_back_to_genomefile(self):
        legacy_path = self.create_annotation_file("annotation.legacy.IR64.gff3")
        legacy_file = GenomeFile.objects.create(
            name="annotation.legacy.IR64.gff3",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="annotation",
            file_path=legacy_path,
            file_type=self.file_type,
            size=os.path.getsize(legacy_path),
        )

        response = self.client.get(
            f"/gd/api/files/genome-files/get_annotation_data/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["annotation_file"]["id"], legacy_file.id)
        self.assertEqual(payload["annotation_file"]["name"], "annotation.legacy.IR64.gff3")
        self.assertEqual(payload["annotation_file"]["file_path"], legacy_path)
        self.assertEqual(payload["annotation_file"]["category"], "annotation")
        self.assertEqual(payload["annotation_file"]["file_size"], os.path.getsize(legacy_path))
        self.assertEqual(payload["annotation_file"]["source"], "legacy_genomefile")

    def test_download_endpoint_still_uses_genomefile(self):
        file_path = self.create_annotation_file("annotation.download.IR64.gff3")
        genome_file = GenomeFile.objects.create(
            name="annotation.download.IR64.gff3",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="annotation",
            file_path=file_path,
            file_type=self.file_type,
            size=os.path.getsize(file_path),
        )

        response = self.client.get(f"/gd/api/files/genome-files/{genome_file.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("annotation.download.IR64.gff3", response["Content-Disposition"])
        response.close()

    def test_compare_annotation_files_command_writes_report(self):
        file_path = self.create_annotation_file("annotation.compare.IR64.gff3")
        GenomeFile.objects.create(
            name="annotation.compare.IR64.gff3",
            organism="IR64",
            accession=self.accession,
            assembly=self.assembly,
            annotation=self.annotation,
            category="annotation",
            file_path=file_path,
            file_type=self.file_type,
            size=os.path.getsize(file_path),
        )
        data_file = DataFile.objects.create(
            file_code="FILE000021",
            file_name="annotation.compare.IR64.gff3",
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            file_role="annotation",
        )
        stdout = StringIO()

        call_command(
            "compare_annotation_files",
            annotation_id=self.annotation.id,
            output_dir=self.temp_dir.name,
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("old_count\t1", output)
        self.assertIn("new_count\t1", output)
        self.assertIn("matched_files\t1", output)

        report_path = os.path.join(self.temp_dir.name, "compare_annotation_files.tsv")
        with open(report_path, "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("matched", report)
        self.assertIn(file_path, report)
