import os
import tempfile
import uuid
from types import SimpleNamespace

from django.test import TestCase

from files.models import DataFile, FileRelation
from files.services.fasta_index_service import find_current_fasta_index


class FastaIndexServiceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.suffix = uuid.uuid4().hex[:10]
        self.genome_path = self._write("genome.IR64.fasta", ">Chr1\nACGT\n")
        self.genome = SimpleNamespace(
            id=999999,
            name="genome.IR64.fasta",
            file_path=self.genome_path,
        )

    def _write(self, name, content):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _relate_index(self, name="genome.IR64.fasta.fai", role="genome_index"):
        path = self._write(name, "Chr1\t4\t0\t4\t5\n")
        data_file = DataFile.objects.create(
            file_code=f"FAI_{self.suffix}_{DataFile.objects.count()}",
            file_name=name,
            file_path=path,
            is_current=True,
        )
        FileRelation.objects.create(
            file=data_file,
            related_type="assembly",
            related_id="42",
            file_role=role,
        )
        os.utime(path, (os.path.getmtime(self.genome_path) + 2,) * 2)
        return path

    def test_returns_fresh_explicitly_related_index(self):
        index_path = self._relate_index()

        resolved = find_current_fasta_index(
            genome_file=self.genome,
            related_type="assembly",
            related_id=42,
        )

        self.assertEqual(resolved, index_path)

    def test_does_not_use_index_from_another_context(self):
        self._relate_index()

        resolved = find_current_fasta_index(
            genome_file=self.genome,
            related_type="assembly",
            related_id=43,
        )

        self.assertIsNone(resolved)

    def test_stale_index_falls_back(self):
        index_path = self._relate_index()
        os.utime(index_path, (os.path.getmtime(self.genome_path) - 2,) * 2)

        resolved = find_current_fasta_index(
            genome_file=self.genome,
            related_type="assembly",
            related_id=42,
        )

        self.assertIsNone(resolved)
