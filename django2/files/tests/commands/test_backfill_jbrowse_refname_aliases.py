import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Assembly


COMMAND_MODULE = "files.management.commands.backfill_jbrowse_refname_aliases"


class BackfillJBrowseRefnameAliasesCommandTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.report_dir = Path(self.temporary_directory.name) / "reports"
        self.assemblies = []
        for index in range(2):
            accession = Accession.objects.create(accession=f"ACC{index}")
            self.assemblies.append(
                Assembly.objects.create(
                    accession=accession,
                    name=f"Assembly {index}",
                    assembly_code=f"ASM_{index}",
                )
            )

    @staticmethod
    def _ready_result(assembly_id, mode, output_dir):
        return {
            "assembly_id": assembly_id,
            "status": "ready_for_build" if mode == "dry_run" else "built",
            "write_performed": mode == "apply",
        }

    def _run(self, **options):
        stdout = StringIO()
        defaults = {
            "all_assemblies": True,
            "dry_run": True,
            "report_dir": str(self.report_dir),
            "stdout": stdout,
        }
        defaults.update(options)
        call_command("backfill_jbrowse_refname_aliases", **defaults)
        return json.loads(stdout.getvalue())

    def test_all_requires_report_directory(self):
        with self.assertRaisesRegex(CommandError, "report-dir"):
            call_command(
                "backfill_jbrowse_refname_aliases",
                all_assemblies=True,
                dry_run=True,
            )

    def test_batch_checkpoint_and_resume_process_next_assembly(self):
        with patch(
            f"{COMMAND_MODULE}.Command._run_one_safely",
            side_effect=self._ready_result,
        ) as run:
            first = self._run(batch_size=1)

        self.assertEqual(run.call_count, 1)
        self.assertEqual(first["processed_this_run"], 1)
        self.assertEqual(first["remaining_count"], 1)
        self.assertTrue(Path(first["checkpoint_path"]).is_file())
        self.assertTrue(Path(first["json_report"]).is_file())

        with patch(
            f"{COMMAND_MODULE}.Command._run_one_safely",
            side_effect=self._ready_result,
        ) as resumed:
            second = self._run(batch_size=1, resume=True)

        resumed.assert_called_once_with(
            self.assemblies[1].id, "dry_run", None
        )
        self.assertEqual(second["remaining_count"], 0)

    def test_rate_limit_is_applied_between_batch_items(self):
        with patch(
            f"{COMMAND_MODULE}.Command._run_one_safely",
            side_effect=self._ready_result,
        ), patch(f"{COMMAND_MODULE}.time.sleep") as sleep:
            self._run(rate_limit_seconds=0.25)

        sleep.assert_called_once_with(0.25)
