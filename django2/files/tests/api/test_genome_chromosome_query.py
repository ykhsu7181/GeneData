import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from files.query_views import query_chromosome_length, query_chromosomes


class GenomeChromosomeQueryTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.fasta_path = os.path.join(self.temp_dir.name, "genome.fa")
        with open(self.fasta_path, "w", encoding="utf-8") as handle:
            handle.write(
                ">contig_01 description OriSeqID=Chr01 source=assembly\n"
                "ACGT\n"
                ">Chr02 description\n"
                "ACGTA\n"
            )
        self.file = SimpleNamespace(file_path=self.fasta_path, name="genome.fa")
        self.accession = SimpleNamespace(id=1, accession="IR64")
        self.index_path = f"{self.fasta_path}.fai"
        with open(self.index_path, "w", encoding="utf-8") as handle:
            handle.write("IndexedChr\t99\t0\t0\t0\n")
        self.factory = RequestFactory()
        index_patcher = patch("files.query_views.find_current_fasta_index", return_value=self.index_path)
        self.find_index = index_patcher.start()
        self.addCleanup(index_patcher.stop)

    def _json(self, response):
        response.render()
        return json.loads(response.content.decode("utf-8"))

    @patch("files.query_views.get_context_genome_file")
    def test_chromosomes_are_read_from_fasta_index(self, get_context_genome_file):
        get_context_genome_file.return_value = (self.accession, None, self.file)

        response = query_chromosomes(self.factory.get("/query/chromosomes/", {"accession": "IR64"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._json(response), ["IndexedChr"])

    @patch("files.query_views.get_context_genome_file")
    def test_chromosome_length_is_read_from_fasta_index(self, get_context_genome_file):
        get_context_genome_file.return_value = (self.accession, None, self.file)

        response = query_chromosome_length(
            self.factory.get("/query/chromosome-length/", {"accession": "IR64", "chromosome": "IndexedChr"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._json(response)["length"], 99)

    @patch("files.query_views.get_context_genome_file")
    def test_chromosomes_and_length_prefer_related_fai(self, get_context_genome_file):
        get_context_genome_file.return_value = (self.accession, None, self.file)
        self.find_index.return_value = self.index_path

        chromosomes = query_chromosomes(
            self.factory.get("/query/chromosomes/", {"accession": "IR64"})
        )
        length = query_chromosome_length(
            self.factory.get(
                "/query/chromosome-length/",
                {"accession": "IR64", "chromosome": "IndexedChr"},
            )
        )

        self.assertEqual(self._json(chromosomes), ["IndexedChr"])
        self.assertEqual(self._json(length), {"length": 99})

    @patch("files.query_views.get_context_genome_file")
    def test_unindexed_fasta_returns_controlled_error(self, get_context_genome_file):
        get_context_genome_file.return_value = (self.accession, None, self.file)
        self.find_index.return_value = None

        response = query_chromosomes(
            self.factory.get("/query/chromosomes/", {"accession": "IR64"})
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self._json(response)["code"], "fasta_index_unavailable")
