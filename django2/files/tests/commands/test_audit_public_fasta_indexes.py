import hashlib
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from files.models import Accession, Assembly, DataFile, FileRelation
from files.services.fasta_index_service import build_fasta_index


class AuditPublicFastaIndexesCommandTests(TestCase):
    def setUp(self):
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
        accession = Accession.objects.create(accession="IR64")
        self.assembly = Assembly.objects.create(
            accession=accession,
            name="IR64 v1",
            assembly_code="ASM_IR64",
        )
        fasta_path = self.root / "genome.IR64.fasta"
        fasta_path.write_bytes(b">Chr01\nACGT\n")
        index_path, _entries = build_fasta_index(str(fasta_path))
        self.genome = self.make_file("GENOME", fasta_path)
        self.index = self.make_file("INDEX", Path(index_path))
        self.relate(self.genome, "genome_fasta", True)
        self.index_relation = self.relate(self.index, "genome_index", False)

    def make_file(self, code, path):
        content = path.read_bytes()
        return DataFile.objects.create(
            file_code=code,
            file_name=path.name,
            file_path=str(path),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            access_level=DataFile.ACCESS_LEVEL_PUBLIC,
            publication_status=DataFile.PUBLICATION_RELEASED,
            published_at=timezone.now(),
        )

    def relate(self, data_file, role, primary):
        return FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id=str(self.assembly.id),
            file_role=role,
            is_primary=primary,
        )

    def test_reports_pass_for_released_fresh_index(self):
        stdout = StringIO()

        call_command(
            "audit_public_fasta_indexes",
            "--assembly",
            "ASM_IR64",
            stdout=stdout,
        )

        self.assertIn("PASS", stdout.getvalue())
        self.assertIn("total=1 pass=1 failed=0", stdout.getvalue())

    def test_fails_when_index_relation_is_missing(self):
        self.index_relation.delete()
        stdout = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "audit_public_fasta_indexes",
                "--assembly",
                "ASM_IR64",
                stdout=stdout,
                stderr=StringIO(),
            )

        self.assertIn("MISSING_INDEX", stdout.getvalue())
