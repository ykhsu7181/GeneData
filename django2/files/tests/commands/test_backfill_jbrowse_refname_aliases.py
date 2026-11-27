import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


COMMAND = "files.management.commands.backfill_jbrowse_refname_aliases"


class BackfillJBrowseRefnameAliasesCommandTests(SimpleTestCase):
    def run_command(self, **options):
        stdout = StringIO()
        defaults = {
            "asset_codes": ["ANN"],
            "username": "owner",
            "stdout": stdout,
        }
        defaults.update(options)
        call_command("backfill_jbrowse_refname_aliases", **defaults)
        return json.loads(stdout.getvalue())

    @patch(f"{COMMAND}.inspect_reference_name_cache")
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_dry_run_validates_without_writing(
        self, command_user, profile_assets, inspect
    ):
        profile_assets.return_value = ([SimpleNamespace(asset_code="ANN")], object())
        inspect.return_value = (
            SimpleNamespace(),
            {"reference_lengths": {"chr1": 4}},
        )
        result = self.run_command(dry_run=True)
        self.assertEqual(result[0]["status"], "ready_for_build")
        self.assertEqual(result[0]["reference_count"], 1)
        profile_assets.assert_called_once()
        inspect.assert_called_once()

    @patch(f"{COMMAND}.build_reference_name_cache")
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_apply_writes_rebuildable_cache(self, command_user, profile_assets, build):
        profile_assets.return_value = ([SimpleNamespace(asset_code="ANN")], object())
        build.return_value = ("cache.json", {"reference_lengths": {"chr1": 4}})
        result = self.run_command()
        self.assertEqual(result[0]["status"], "built")
        self.assertEqual(result[0]["reference_count"], 1)

    @patch(f"{COMMAND}.build_reference_name_cache", side_effect=RuntimeError("broken"))
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_failure_returns_nonzero(self, command_user, profile_assets, build):
        profile_assets.return_value = ([SimpleNamespace(asset_code="ANN")], object())
        with self.assertRaisesRegex(CommandError, "cache builds failed"):
            self.run_command()
