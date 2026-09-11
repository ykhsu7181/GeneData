# GeneData CI gate

The workflow in `.github/workflows/ci.yml` runs on pull requests, pushes to
`main`/`master`, and manual dispatch.

## Django job

The job starts a disposable MySQL 8 service and supplies all connection values
through environment variables. It runs:

```text
python manage.py check
python manage.py makemigrations --check --dry-run files
python manage.py test files --noinput
python manage.py check --deploy --fail-level ERROR --settings=filemanager.settings_production
```

The MySQL conditional-unique-constraint and long unique `CharField` warnings
remain visible in test output. They are known schema risks and are not silenced.
The deployment check currently prints the outstanding Stage A warnings; it
fails CI on errors. Tightening warnings into a blocking gate requires Stage A
HTTPS/HSTS/cookie decisions.

The former `django2/files/tests.py` was moved into the `files/tests/` package so
the canonical `python manage.py test files` discovery command no longer imports
two competing `files.tests` modules.

## Frontend job

The job uses the committed npm lockfile and runs:

```text
npm ci
npm test
npm run build
```

`npm test` executes all source-level behavior tests. Lint is intentionally not
blocking until the existing lint baseline is assessed and corrected in a
separate change.

The committed `package-lock.json` is the CI dependency source. It has been
synchronized with `package.json`; a local clean install, all 39 behavior tests,
and the production build completed successfully. The build still reports the
existing bundle-size warnings.

## Local database settings

By explicit project decision, the base settings retain the existing local
database password as a fallback. `GENEDATA_DB_PASSWORD` still overrides that
fallback for CI and other environments. This is a documented security
exception: the source tree must not be treated as credential-free, and the
Security Gate remains open while the fallback exists.
The 238 Django tests are discoverable without a module conflict. A local full
run still requires valid credentials for a disposable MySQL test database; the
CI service provides that database independently.
