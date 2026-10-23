import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from files.models import DataFile


class PrepareExternalFileRegistrationTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def test_prepares_candidates_and_review_without_database_writes(self):
        file_list = self.root / "names.txt"
        file_list.write_text(
            "genome.IR64.fasta\nannotation.NEW.gff\ncodon.sh\n",
            encoding="utf-8",
        )
        base_manifest = self.root / "files.full.tsv"
        self._write_manifest(base_manifest, [
            {
                "file_path": "/warehouse/genome.IR64.fasta",
                "file_role": "genome",
                "accession": "IR64",
                "assembly_code": "ASM_IR64",
                "annotation_code": "",
                "sample_code": "",
                "dataset_code": "",
                "md5": "",
            }
        ])
        DataFile.objects.create(
            file_code="FILE000013",
            file_name="genome.IR64.fasta",
            file_path=str(self.root / "registered.fasta"),
        )
        before = DataFile.objects.count()
        output = self.root / "reports"

        stdout = StringIO()
        call_command(
            "prepare_external_file_registration",
            file_list=str(file_list),
            base_manifest=str(base_manifest),
            manual_files_root="/warehouse",
            output=str(output),
            stdout=stdout,
        )

        self.assertEqual(DataFile.objects.count(), before)
        self.assertIn("READY_FROM_BASE_MANIFEST\t1", stdout.getvalue())
        self.assertIn("MAPPING_REQUIRED\t1", stdout.getvalue())
        self.assertIn("NON_BUSINESS_REVIEW\t1", stdout.getvalue())

        candidates = self._read_tsv(output / "files.registration.candidate.tsv")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["accession"], "IR64")
        reviews = self._read_tsv(output / "files.registration.review.tsv")
        self.assertEqual(
            {row["status"] for row in reviews},
            {"MAPPING_REQUIRED", "NON_BUSINESS_REVIEW"},
        )
        coverage = self._read_tsv(output / "files.registration.coverage.tsv")
        registered = next(row for row in coverage if row["file_name"] == "genome.IR64.fasta")
        self.assertEqual(registered["existing_file_codes"], "FILE000013")
        self.assertIn(
            "files.registration.candidate.tsv",
            (output / "SHA256SUMS").read_text(encoding="ascii"),
        )

    def test_duplicate_input_and_duplicate_base_are_not_candidates(self):
        file_list = self.root / "names.txt"
        file_list.write_text(
            "genome.A.fasta\nGENOME.A.FASTA\nannotation.B.gff\n",
            encoding="utf-8",
        )
        base_manifest = self.root / "files.full.tsv"
        self._write_manifest(base_manifest, [
            self._row("/warehouse/genome.A.fasta", "genome", "A"),
            self._row("/warehouse/annotation.B.gff", "annotation", "B"),
            self._row("/other/annotation.B.gff", "annotation", "B"),
        ])
        output = self.root / "reports"

        call_command(
            "prepare_external_file_registration",
            file_list=str(file_list),
            base_manifest=str(base_manifest),
            manual_files_root="/warehouse",
            output=str(output),
        )

        candidates = self._read_tsv(output / "files.registration.candidate.tsv")
        self.assertEqual(candidates, [])
        statuses = [
            row["status"]
            for row in self._read_tsv(output / "files.registration.coverage.tsv")
        ]
        self.assertEqual(statuses.count("DUPLICATE_INPUT_NAME"), 2)
        self.assertIn("AMBIGUOUS_BASE_MANIFEST", statuses)

    def test_base_path_outside_root_is_blocked(self):
        file_list = self.root / "names.txt"
        file_list.write_text("genome.A.fasta\n", encoding="utf-8")
        base_manifest = self.root / "files.full.tsv"
        self._write_manifest(base_manifest, [
            self._row("/outside/genome.A.fasta", "genome", "A"),
        ])
        output = self.root / "reports"

        call_command(
            "prepare_external_file_registration",
            file_list=str(file_list),
            base_manifest=str(base_manifest),
            manual_files_root="/warehouse",
            output=str(output),
        )

        coverage = self._read_tsv(output / "files.registration.coverage.tsv")
        self.assertEqual(coverage[0]["status"], "BASE_PATH_OUTSIDE_ROOT")
        self.assertEqual(
            self._read_tsv(output / "files.registration.candidate.tsv"),
            [],
        )

    @staticmethod
    def _row(path, role, accession):
        return {
            "file_path": path,
            "file_role": role,
            "accession": accession,
            "assembly_code": f"ASM_{accession}",
            "annotation_code": "",
            "sample_code": "",
            "dataset_code": "",
            "md5": "",
        }

    @staticmethod
    def _write_manifest(path, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "file_path",
                    "file_role",
                    "accession",
                    "assembly_code",
                    "annotation_code",
                    "sample_code",
                    "dataset_code",
                    "md5",
                ),
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _read_tsv(path):
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))
