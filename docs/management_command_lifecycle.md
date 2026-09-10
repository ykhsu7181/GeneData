# Django management command lifecycle

This inventory is the Stage D retirement gate for commands under
`django2/files/management/commands`. The machine-readable source is
`files.management.command_lifecycle.COMMAND_LIFECYCLE`.

| Status | Meaning | Removal gate |
| --- | --- | --- |
| `active` | Current ingestion, validation, cache, or relationship command | Normal change review |
| `retain_audit` | Read-only migration/archive evidence | Retention period ended and replacement evidence archived |
| `legacy_repair` | Historical import or repair path | Migration audit passes and rollback/evidence is retained |
| `retire_pending_usage_confirmation` | Demo or one-off cleanup candidate | Production scripts, scheduler, runbooks, and logs confirm zero use |

No command is deleted solely because it looks old. In this audit,
`cleanup_data` and `seed_ir64_demo_hierarchy` have no source-code caller and
are retirement candidates, but external production usage has not been proven
absent. They remain available until that evidence is reviewed.

When adding or removing a command, update the registry in the same change. The
regression test fails when a command has no lifecycle classification.
