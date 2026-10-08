import csv
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from files.models import Accession, Assembly


COMMAND_MODULE = "files.management.commands.build_jbrowse_indexes"


class BuildJBrowseIndexesBatchCommandTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.report_dir = Path(self.temporary_directory.name) / "reports"
        self.assemblies = []
        for index in range(1, 4):
            accession = Accession.objects.create(accession=f"ACC{index}")
            self.assemblies.append(
                Assembly.objects.create(
                    accession=accession,
                    name=f"Assembly {index}",
                    assembly_code=f"ASM_{index}",
                    is_default=True,
                )
            )
        placeholder_accession = Accession.objects.create(accession="PLACEHOLDER")
        self.placeholder = Assembly.objects.create(
            accession=placeholder_accession,
            name="default",
            assembly_code=None,
            is_default=True,
        )

    def _ready_result(self, assembly_id, output_root=None):
        return {
            "assembly_id": assembly_id,
            "assembly_code": f"ASM_{assembly_id}",
            "accession": f"ACC{assembly_id}",
            "status": "ready_for_build",
            "write_performed": False,
        }

    def _run_batch(self, **options):
        stdout = StringIO()
        defaults = {
            "all_assemblies": True,
            "dry_run": True,
            "report_dir": str(self.report_dir),
            "stdout": stdout,
        }
        defaults.update(options)
        call_command("build_jbrowse_indexes", **defaults)
        return json.loads(stdout.getvalue())

    def test_all_requires_report_directory(self):
        with self.assertRaisesRegex(CommandError, "report-dir"):
            call_command(
                "build_jbrowse_indexes",
                all_assemblies=True,
                dry_run=True,
            )

    def test_all_excludes_strict_placeholder_assemblies(self):
        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ) as inspect:
            summary = self._run_batch()

        inspected_ids = {call.args[0] for call in inspect.call_args_list}
        self.assertNotIn(self.placeholder.id, inspected_ids)
        self.assertEqual(inspected_ids, {item.id for item in self.assemblies})
        self.assertEqual(summary["total_assembly_count"], 3)

    def test_batch_size_writes_checkpoint_and_audit_reports(self):
        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ) as inspect:
            summary = self._run_batch(batch_size=2)

        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(summary["total_assembly_count"], 3)
        self.assertEqual(summary["processed_this_run"], 2)
        self.assertEqual(summary["successful_this_run"], 2)
        self.assertEqual(summary["failed_this_run"], 0)
        self.assertEqual(summary["successful_checkpoint_count"], 2)
        self.assertEqual(summary["failed_checkpoint_count"], 0)
        self.assertEqual(summary["remaining_count"], 1)

        checkpoint = json.loads(
            Path(summary["checkpoint_path"]).read_text(encoding="utf-8")
        )
        expected_ids = {str(item.id) for item in self.assemblies[:2]}
        self.assertEqual(set(checkpoint["processed"]), expected_ids)

        json_report = json.loads(
            Path(summary["json_report"]).read_text(encoding="utf-8")
        )
        self.assertEqual(len(json_report["results"]), 2)
        with Path(summary["tsv_report"]).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, dialect="excel-tab"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["success"], "True")

    def test_resume_continues_with_next_pending_assembly(self):
        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ):
            self._run_batch(batch_size=2)

        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ) as inspect:
            summary = self._run_batch(batch_size=2, resume=True)

        inspect.assert_called_once_with(
            self.assemblies[2].id,
            output_root=None,
        )
        self.assertEqual(summary["processed_this_run"], 1)
        self.assertEqual(summary["skipped_from_checkpoint"], 2)
        self.assertEqual(summary["remaining_count"], 0)

    def test_failure_is_reported_without_stopping_later_items(self):
        def inspect(assembly_id, output_root=None):
            if assembly_id == self.assemblies[0].id:
                raise RuntimeError("broken source")
            return self._ready_result(assembly_id)

        with patch(f"{COMMAND_MODULE}.inspect_jbrowse_assembly", side_effect=inspect):
            summary = self._run_batch()

        self.assertEqual(summary["processed_this_run"], 3)
        self.assertEqual(summary["successful_this_run"], 2)
        self.assertEqual(summary["failed_this_run"], 1)
        self.assertEqual(summary["failed_checkpoint_count"], 1)
        report = json.loads(
            Path(summary["json_report"]).read_text(encoding="utf-8")
        )
        failed = [item for item in report["results"] if not item["success"]]
        self.assertEqual(failed[0]["status"], "inspection_failed")
        self.assertEqual(failed[0]["error"], "broken source")

    def test_retry_failed_only_reprocesses_failed_checkpoint_entries(self):
        failed_id = self.assemblies[0].id

        def first_inspection(assembly_id, output_root=None):
            if assembly_id == failed_id:
                return {
                    "assembly_id": assembly_id,
                    "status": "invalid_annotation_format",
                    "write_performed": False,
                }
            return self._ready_result(assembly_id)

        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=first_inspection,
        ):
            self._run_batch()

        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ) as inspect:
            summary = self._run_batch(resume=True, retry_failed=True)

        inspect.assert_called_once_with(failed_id, output_root=None)
        self.assertEqual(summary["processed_this_run"], 1)
        self.assertEqual(summary["remaining_count"], 0)

    def test_apply_uses_separate_checkpoint_from_dry_run(self):
        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            side_effect=self._ready_result,
        ):
            dry_run_summary = self._run_batch(batch_size=1)

        built_result = lambda assembly_id, output_root=None: {
            "assembly_id": assembly_id,
            "status": "built",
            "write_performed": True,
        }
        with patch(
            f"{COMMAND_MODULE}.build_jbrowse_assembly_indexes",
            side_effect=built_result,
        ) as build:
            apply_summary = self._run_batch(
                dry_run=False,
                apply=True,
                batch_size=1,
                resume=True,
            )

        self.assertEqual(build.call_count, 1)
        self.assertNotEqual(
            dry_run_summary["checkpoint_path"],
            apply_summary["checkpoint_path"],
        )

    def test_fail_on_error_raises_after_writing_reports(self):
        with patch(
            f"{COMMAND_MODULE}.inspect_jbrowse_assembly",
            return_value={
                "assembly_id": self.assemblies[0].id,
                "status": "missing_genome",
                "write_performed": False,
            },
        ), self.assertRaisesRegex(CommandError, "reports were written"):
            self._run_batch(batch_size=1, fail_on_error=True)

        self.assertTrue(list(self.report_dir.glob("*.json")))
        self.assertTrue(list(self.report_dir.glob("*.tsv")))
