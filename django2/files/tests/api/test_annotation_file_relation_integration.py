import os
import tempfile
from django.test import TestCase

from files.models import Accession, Annotation, Assembly, DataFile, FileRelation, FileType
from files.services.annotation_feature_index_service import build_annotation_feature_index


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
        build_annotation_feature_index(self.annotation)
        response = self.client.get(
            f"/gd/api/files/query/annotation-data/?annotation_id={self.annotation.id}"
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
        self.assertEqual(
            payload["annotation_file"]["datafile_download_url"],
            f"/gd/api/files/data-files/{data_file.id}/download/",
        )
        self.assertEqual(
            payload["annotation_file"]["download_url"],
            payload["annotation_file"]["datafile_download_url"],
        )
        self.assertNotIn("/genome-files/", payload["annotation_file"]["download_url"])

    def test_annotation_options_keep_full_statistics_separate_from_filtered_results(self):
        file_path = os.path.join(self.temp_dir.name, "annotation.options.IR64.gff3")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("##gff-version 3\n")
            handle.write("chr1\tsource\tgene\t1\t100\t.\t+\t.\tID=gene1\n")
            handle.write("chr1\tsource\tmRNA\t1\t100\t.\t+\t.\tID=mrna1\n")
            handle.write("chr2\tsource\tgene\t20\t80\t.\t-\t.\tID=gene2\n")
        data_file = DataFile.objects.create(
            file_code="FILE000022",
            file_name="annotation.options.IR64.gff3",
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            file_role="annotation",
        )
        build_annotation_feature_index(self.annotation)

        options_response = self.client.get(
            f"/gd/api/files/query/annotation-options/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(options_response.status_code, 200)
        options = options_response.json()
        self.assertEqual(options["annotation_id"], self.annotation.id)
        self.assertEqual(options["chromosomes"], ["chr1", "chr2"])
        self.assertEqual(options["feature_types"], ["gene", "mRNA"])
        self.assertEqual(options["summary"], {
            "total_features": 3,
            "chromosome_count": 2,
            "feature_type_count": 2,
        })

        data_response = self.client.get(
            f"/gd/api/files/query/annotation-data/?annotation_id={self.annotation.id}"
            "&chromosome=chr1&feature_type=mRNA"
        )

        self.assertEqual(data_response.status_code, 200)
        payload = data_response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["filtered_count"], 1)
        self.assertEqual(payload["filtered_statistics"], {
            "chromosomes": ["chr1"],
            "feature_types": ["mRNA"],
            "total_features": 1,
        })
        self.assertEqual(payload["statistics"], payload["filtered_statistics"])

    def test_annotation_options_require_a_related_annotation_file(self):
        response = self.client.get(
            f"/gd/api/files/query/annotation-options/?annotation_id={self.annotation.id}"
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("未找到", response.json()["error"])

    def test_annotation_endpoint_requires_a_fresh_offline_index(self):
        file_path = self.create_annotation_file("annotation.unindexed.IR64.gff3")
        data_file = DataFile.objects.create(
            file_code="FILE000023",
            file_name="annotation.unindexed.IR64.gff3",
            file_path=file_path,
            file_size=os.path.getsize(file_path),
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="annotation",
            related_id=str(self.annotation.id),
            file_role="annotation",
        )

        response = self.client.get(
            f"/gd/api/files/query/annotation-data/?annotation_id={self.annotation.id}"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "annotation_index_unavailable")
        self.assertEqual(response.json()["index_status"], "missing")

        build_annotation_feature_index(self.annotation)
        with open(file_path, "a", encoding="utf-8") as handle:
            handle.write("chr2\tsource\tgene\t20\t30\t.\t+\t.\tID=gene2\n")
        stale_response = self.client.get(
            f"/gd/api/files/query/annotation-data/?annotation_id={self.annotation.id}"
        )
        self.assertEqual(stale_response.status_code, 503)
        self.assertEqual(stale_response.json()["index_status"], "stale")

    def test_genomefile_download_endpoint_is_archived(self):
        response = self.client.get("/gd/api/files/genome-files/987654/download/")

        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertTrue(payload["archived"])
        self.assertIn("GenomeFile download is archived", payload["message"])
