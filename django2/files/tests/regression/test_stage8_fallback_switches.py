import os
import tempfile
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from files.models import Accession, Assembly, DataFile, FileRelation, FileType, GenomeFile
from files.services.file_relation_service import get_files_for_accession


class Stage8FallbackSwitchesTestCase(TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.file_type = FileType.objects.create(
            name=f"FASTA_STAGE8_{self.suffix}",
            extension="fasta",
        )
        self.accession = Accession.objects.create(accession=f"IR64_{self.suffix}")
        self.assembly = Assembly.objects.create(
            accession=self.accession,
            name="default",
            is_default=True,
        )

    def create_data_file(self, code_suffix, file_path, file_name=None):
        return DataFile.objects.create(
            file_code=f"STAGE8{self.suffix}{code_suffix}",
            file_name=file_name or os.path.basename(file_path),
            file_path=file_path,
            file_size=123,
        )

    def create_legacy_file(self, accession=None, organism=None, name="legacy.fasta"):
        return GenomeFile.objects.create(
            name=name,
            organism=organism or self.accession.accession,
            accession=accession,
            assembly=self.assembly if accession else None,
            category="genome",
            file_path=f"/tmp/stage8/{self.suffix}/{name}",
            file_type=self.file_type,
            size=123,
        )

    @override_settings(ENABLE_GENOMEFILE_FALLBACK=True, ENABLE_ORGANISM_FALLBACK=True)
    def test_genomefile_fallback_enabled_setting_no_longer_enables_fallback(self):
        self.create_legacy_file(accession=self.accession)

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    @override_settings(ENABLE_GENOMEFILE_FALLBACK=False, ENABLE_ORGANISM_FALLBACK=False)
    def test_genomefile_fallback_disabled_is_not_used(self):
        self.create_legacy_file(accession=self.accession)

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    @override_settings(ENABLE_GENOMEFILE_FALLBACK=True, ENABLE_ORGANISM_FALLBACK=True)
    def test_organism_fallback_enabled_setting_no_longer_enables_fallback(self):
        self.create_legacy_file(organism=self.accession.accession, name="organism.fasta")

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    @override_settings(ENABLE_GENOMEFILE_FALLBACK=True, ENABLE_ORGANISM_FALLBACK=False)
    def test_organism_fallback_disabled_is_not_used(self):
        self.create_legacy_file(organism=self.accession.accession, name="organism.fasta")

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(files, [])

    @override_settings(ENABLE_GENOMEFILE_FALLBACK=False, ENABLE_ORGANISM_FALLBACK=False)
    def test_new_relation_query_is_not_affected_by_fallback_switches(self):
        data_file = self.create_data_file("A", f"/tmp/stage8/{self.suffix}/new.fasta")
        FileRelation.objects.create(
            file=data_file,
            related_type="accession",
            related_id=str(self.accession.id),
            related_code=self.accession.accession,
            file_role="genome",
        )

        files = get_files_for_accession(self.accession.id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["source"], "new_relation")

    def test_report_legacy_usage_writes_report_without_changing_database(self):
        legacy_file = self.create_legacy_file(accession=self.accession)
        before_counts = self.table_counts()
        stdout = StringIO()

        call_command("report_legacy_usage", output_dir=self.output_dir.name, stdout=stdout)

        self.assertEqual(self.table_counts(), before_counts)
        self.assertIn("legacy_usage_count\t1", stdout.getvalue())
        reports = [
            name for name in os.listdir(self.output_dir.name)
            if name.startswith("legacy_usage_report_") and name.endswith(".tsv")
        ]
        self.assertEqual(len(reports), 1)
        with open(os.path.join(self.output_dir.name, reports[0]), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("legacy_genomefile", report)
        self.assertIn(legacy_file.file_path, report)
        self.assertIn("backfill_to_datafile_filerelation", report)

    def table_counts(self):
        return {
            "genomefile": GenomeFile.objects.count(),
            "datafile": DataFile.objects.count(),
            "filerelation": FileRelation.objects.count(),
        }
