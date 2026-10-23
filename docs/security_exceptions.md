# Security exceptions

## SEC-DB-001: Historical database credential exposure

Status: **Accepted Risk / Known Exception**

The repository history and the current development settings may contain an
existing database credential that could still be active. The P0 admin-session
hardening does not change that password, remove the existing fallback, or
rewrite Git history. It must therefore not be described as a complete Security
Gate pass.

Required controls:

- Production must explicitly provide `GENEDATA_DB_PASSWORD`; it must not rely
  on the development-settings fallback.
- This P0 change must not add or duplicate plaintext database credentials.
- The database account must be restricted to the required hosts and minimum
  privileges.
- The database port must not be directly reachable from the public internet.
- Repository access must remain restricted to authorized maintainers.

Deployment-owner verification remains required for the account host rules,
firewall/security-group rules, and effective production environment variable.
No credential value or infrastructure evidence is stored in this document.

The exception can be closed only after the credential is rotated, removed from
the active source configuration, and any approved Git-history remediation is
completed.

