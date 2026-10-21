import csv
import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import Accession, Assembly, DataFile, Dataset, DatasetAccession, FileRelation
from files.services.fasta_index_service import build_fasta_index


class AuditExternalApiReadinessTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "protected"
        self.root.mkdir()
        self.output = Path(self.temporary_directory.name) / "reports"
        self.settings_override = override_settings(
            GENEDATA_PROTECTED_FILE_ROOTS={
                "test": {"path": str(self.root), "internal_uri": "/_protected_test/"}
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=self.accession, name="IR64 v1", assembly_code="ASM_IR64"
        )
        self.dataset = Dataset.objects.create(
            dataset_code="DS_IR64", visibility="public", status="released"
        )
        DatasetAccession.objects.create(dataset=self.dataset, accession=self.accession)
        fasta_path = self.root / "genome.IR64.fasta"
        fasta_path.write_bytes(b">Chr01\nACGT\n")
        index_path, _entries = build_fasta_index(str(fasta_path))
        self.genome = self.make_file("GENOME", fasta_path)
        self.index = self.make_file("INDEX", Path(index_path))
        self.relate(self.genome, "assembly", self.assembly.id, "genome_fasta", True)
        self.relate(self.index, "assembly", self.assembly.id, "genome_index", False)
        self.relate(self.genome, "dataset", self.dataset.id, "genome", True)
        self.relate(self.index, "dataset", self.dataset.id, "genome_index", False)

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
        }
        values.update(overrides)
        return DataFile.objects.create(**values)

    @staticmethod
    def relate(data_file, related_type, related_id, role, primary):
        return FileRelation.objects.create(
            file=data_file,
            related_type=related_type,
            related_id=str(related_id),
            file_role=role,
            is_primary=primary,
        )

    def read_rows(self, name):
        with (self.output / f"external_api_{name}.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            return list(csv.DictReader(handle, delimiter="\t"))

    def test_writes_exposure_reports_without_paths_or_mutation(self):
        internal_path = self.root / "internal.txt"
        internal_path.write_text("internal", encoding="utf-8")
        internal_dataset = Dataset.objects.create(
            dataset_code="DS_INTERNAL", visibility="lab_internal", status="released"
        )
        internal = self.make_file(
            "INTERNAL", internal_path, dataset=internal_dataset,
            access_level=DataFile.ACCESS_LEVEL_INHERITED,
        )
        self.relate(internal, "dataset", internal_dataset.id, "other", True)
        draft_path = self.root / "draft.txt"
        draft_path.write_text("draft", encoding="utf-8")
        self.make_file("DRAFT", draft_path, publication_status=DataFile.PUBLICATION_DRAFT)
        before = (DataFile.objects.count(), FileRelation.objects.count(), Dataset.objects.count())

        stdout = StringIO()
        call_command(
            "audit_external_api_readiness",
            "--output-dir", str(self.output),
            "--require-file", "GENOME",
            "--require-dataset", "DS_IR64",
            "--require-assembly", "ASM_IR64",
            stdout=stdout,
        )

        self.assertIn("mode\tREAD_ONLY", stdout.getvalue())
        self.assertIn("required_blockers\t0", stdout.getvalue())
        self.assertEqual(
            before,
            (DataFile.objects.count(), FileRelation.objects.count(), Dataset.objects.count()),
        )
        file_rows = {row["file_code"]: row for row in self.read_rows("files")}
        self.assertEqual(file_rows["GENOME"]["status"], "READY")
        self.assertEqual(file_rows["INTERNAL"]["status"], "INTERNAL_ONLY")
        self.assertEqual(file_rows["DRAFT"]["status"], "NOT_RELEASED")
        dataset_rows = {row["dataset_code"]: row for row in self.read_rows("datasets")}
        self.assertEqual(dataset_rows["DS_IR64"]["status"], "READY")
        assembly_rows = {row["assembly_code"]: row for row in self.read_rows("assemblies")}
        self.assertEqual(assembly_rows["ASM_IR64"]["status"], "READY")
        for path in self.output.glob("*.tsv"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn(str(self.root), content)
            self.assertNotIn("file_path", content)

    def test_required_gate_fails_after_writing_reports(self):
        with self.assertRaises(CommandError):
            call_command(
                "audit_external_api_readiness",
                "--output-dir", str(self.output),
                "--require-file", "UNKNOWN",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertTrue((self.output / "external_api_summary.tsv").is_file())
