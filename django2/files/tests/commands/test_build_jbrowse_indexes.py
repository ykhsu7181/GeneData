import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


COMMAND = "files.management.commands.build_jbrowse_indexes"


class BuildJBrowseIndexesCommandTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(username="owner")
        self.annotation = SimpleNamespace(asset_code="ANN")
        self.reference = SimpleNamespace(asset_code="REF")
        self.context = SimpleNamespace(reference_asset=self.reference)

    def run_command(self, **options):
        stdout = StringIO()
        defaults = {
            "asset_codes": ["ANN"],
            "dry_run": True,
            "username": "owner",
            "stdout": stdout,
        }
        defaults.update(options)
        if defaults.get("apply"):
            defaults.pop("dry_run", None)
        call_command("build_jbrowse_indexes", **defaults)
        return json.loads(stdout.getvalue())

    @patch(f"{COMMAND}.resolve_jbrowse_asset_context")
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_dry_run_resolves_dataasset_without_writes(self, command_user, profile_assets, resolve):
        command_user.return_value = self.user
        profile_assets.return_value = ([self.annotation], object())
        resolve.return_value = self.context
        result = self.run_command()
        self.assertEqual(result[0]["status"], "ready_for_build")
        self.assertFalse(result[0]["write_performed"])
        resolve.assert_called_once()

    @patch(f"{COMMAND}.build_reference_name_cache")
    @patch(f"{COMMAND}.build_annotation_feature_index_for_asset")
    @patch(f"{COMMAND}.build_annotation_tabix_index")
    @patch(f"{COMMAND}.build_reference_fasta_index")
    @patch(f"{COMMAND}.resolve_jbrowse_asset_context")
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_apply_runs_all_dataasset_builders(
        self, command_user, profile_assets, resolve, build_fai, build_tabix,
        build_features, build_cache,
    ):
        command_user.return_value = self.user
        profile_assets.return_value = ([self.annotation], object())
        resolve.return_value = self.context
        build_fai.return_value = (SimpleNamespace(file_code="FAI"), 2)
        build_tabix.return_value = SimpleNamespace(file_code="TBI")
        build_features.return_value = (SimpleNamespace(feature_count=3), True)
        build_cache.return_value = ("cache.json", {})
        result = self.run_command(dry_run=False, apply=True)
        self.assertEqual(result[0]["status"], "built")
        self.assertTrue(result[0]["write_performed"])
        build_fai.assert_called_once()
        build_tabix.assert_called_once()
        build_features.assert_called_once()
        build_cache.assert_called_once()

    @patch(f"{COMMAND}.resolve_jbrowse_asset_context", side_effect=RuntimeError("broken"))
    @patch(f"{COMMAND}.profile_assets")
    @patch(f"{COMMAND}.command_user")
    def test_failure_is_reported_and_returns_nonzero(self, command_user, profile_assets, resolve):
        command_user.return_value = self.user
        profile_assets.return_value = ([self.annotation], object())
        with self.assertRaisesRegex(CommandError, "builds failed"):
            self.run_command()
