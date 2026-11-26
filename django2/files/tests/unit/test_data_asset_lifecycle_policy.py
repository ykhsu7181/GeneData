from django.test import SimpleTestCase

from files.services.data_asset_lifecycle_policy import (
    LifecyclePolicyError,
    resolve_context_transition,
    resolve_data_asset_transition,
)


class DataAssetLifecyclePolicyTests(SimpleTestCase):
    def test_data_asset_approved_path_and_validation_levels_are_fixed(self):
        submit = resolve_data_asset_transition("submit", "draft", "contributor")
        approve = resolve_data_asset_transition("approve", "submitted", "manager")
        release = resolve_data_asset_transition("release", "approved", "owner")

        self.assertEqual((submit.target, submit.validation_level), ("submitted", "complete"))
        self.assertEqual((approve.target, approve.validation_level), ("approved", "complete"))
        self.assertEqual((release.target, release.validation_level), ("released", "release"))

    def test_return_withdraw_and_archive_require_reason(self):
        self.assertTrue(
            resolve_data_asset_transition("return", "submitted", "manager").reason_required
        )
        self.assertTrue(
            resolve_data_asset_transition(
                "withdraw_approval", "approved", "owner"
            ).reason_required
        )
        self.assertTrue(
            resolve_data_asset_transition("archive", "released", "owner").reason_required
        )

    def test_invalid_state_role_and_unknown_action_fail_closed(self):
        cases = (
            ("approve", "draft", "owner"),
            ("release", "approved", "manager"),
            ("restore", "archived", "owner"),
        )
        for action, status, role in cases:
            with self.subTest(action=action, status=status, role=role):
                with self.assertRaises(LifecyclePolicyError):
                    resolve_data_asset_transition(action, status, role)

    def test_context_has_only_activate_and_archive_paths(self):
        self.assertEqual(
            resolve_context_transition("activate", "draft", "manager").target,
            "active",
        )
        self.assertEqual(
            resolve_context_transition("archive", "active", "owner").target,
            "archived",
        )
        with self.assertRaises(LifecyclePolicyError):
            resolve_context_transition("restore", "archived", "owner")
