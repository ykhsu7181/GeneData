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
        self.file = SimpleNamespace(file_path=self.fasta_path)
        self.factory = RequestFactory()

    def _json(self, response):
        response.render()
        return json.loads(response.content.decode("utf-8"))

    @patch("files.query_views.get_context_genome_file")
    def test_chromosomes_return_canonical_fasta_ids(self, get_context_genome_file):
        get_context_genome_file.return_value = (None, None, self.file)

        response = query_chromosomes(self.factory.get("/query/chromosomes/", {"accession": "IR64"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._json(response), ["Chr01", "Chr02"])

    @patch("files.query_views.get_context_genome_file")
    def test_chromosome_length_accepts_raw_or_canonical_id(self, get_context_genome_file):
        get_context_genome_file.return_value = (None, None, self.file)

        raw_response = query_chromosome_length(
            self.factory.get("/query/chromosome-length/", {"accession": "IR64", "chromosome": "contig_01"})
        )
        canonical_response = query_chromosome_length(
            self.factory.get("/query/chromosome-length/", {"accession": "IR64", "chromosome": "Chr01"})
        )

        self.assertEqual(raw_response.status_code, 200)
        self.assertEqual(canonical_response.status_code, 200)
        self.assertEqual(self._json(raw_response)["length"], 4)
        self.assertEqual(self._json(canonical_response)["length"], 4)
