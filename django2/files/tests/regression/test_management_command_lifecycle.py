from pathlib import Path

from django.test import SimpleTestCase

from files.management.command_lifecycle import (
    COMMAND_LIFECYCLE,
    RETIRE_PENDING_USAGE_CONFIRMATION,
)


class ManagementCommandLifecycleTests(SimpleTestCase):
    def test_every_files_command_has_an_explicit_lifecycle(self):
        command_dir = Path(__file__).resolve().parents[2] / "management" / "commands"
        command_names = {
            path.stem
            for path in command_dir.glob("*.py")
            if path.stem != "__init__"
        }

        self.assertEqual(set(COMMAND_LIFECYCLE), command_names)

    def test_demo_and_one_off_cleanup_commands_require_usage_confirmation(self):
        self.assertEqual(
            COMMAND_LIFECYCLE["cleanup_data"],
            RETIRE_PENDING_USAGE_CONFIRMATION,
        )
        self.assertEqual(
            COMMAND_LIFECYCLE["seed_ir64_demo_hierarchy"],
            RETIRE_PENDING_USAGE_CONFIRMATION,
        )
