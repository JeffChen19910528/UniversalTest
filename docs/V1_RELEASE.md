# V1.0 Release Manifest

```text
Version:        1.0.0
Release date:   2026-08-09
Python:         3.11+
License:        UNLICENSED (see pyproject.toml)
```

Version source: `src/universal_test/__init__.py::__version__` — the single
place this literal is defined; `pyproject.toml` reads it dynamically
(`dynamic = ["version"]`). CLI `tool_version` fields, `--version` output,
and packaging metadata all derive from this one attribute.

## Test count

```text
563 passed, 0 failed
```

(`python -m pytest -q`, full suite, no test skipped or deleted to reach
this count.)

## Release artifacts

```text
dist/universal_test-1.0.0-py3-none-any.whl
dist/universal_test-1.0.0.tar.gz
```

Built via `python -m build` (an added `dev`-only build dependency, never a
runtime one). Both verified installable into a clean virtual environment;
package contents audited (source + packaging metadata only — no test
fixtures, reports, caches, or secrets; see `docs/V1_RELEASE_CHECKLIST.md`).

## Supported

- **Discovery**: 12 languages, common frameworks/infrastructure/CI
  systems, 6 databases (evidence only), OpenAPI/Swagger/GraphQL/REST-
  routing evidence, common test frameworks — all read-only.
- **Functional/performance testing**: OpenAPI 3.x REST APIs.
- **Database assessment** (read-only, metadata only): SQL Server,
  PostgreSQL, MySQL, SQLite.
- **Baseline/regression comparison**: functional (per-test-ID),
  performance (direction-aware, tolerance-based), database/discovery
  (informational schema-change detection), assessment-category
  transitions.
- **CI Quality Gate**: deterministic `fail_on`/`warn_on` policy, stable
  `0/1/2/3` exit-code contract, GitHub Actions/GitLab CI/Jenkins starting-
  point templates.
- **Reports**: `report.json`/`report.md`/`report.html`.

## Optional

```bash
pip install "universal-test[database]"
```

Installs `psycopg2-binary` (PostgreSQL), `mysql-connector-python` (MySQL),
`pyodbc` (SQL Server — also needs an OS-level ODBC driver). SQLite needs no
extra (Python standard library). None of these are required for Core,
Discovery, REST/OpenAPI testing, Performance testing, Assessment,
Regression, the Quality Gate, or Reporting — verified in a clean base
install with zero database drivers present.

## Known limitations

See `docs/V1_FREEZE.md`'s "Known limitations" section for the full list.
Headline items: no numeric quality score (by design); no AI-assisted
analysis anywhere (fully deterministic); database/discovery regression
severity is always informational (no "baseline policy" concept yet); only
SQLite has live-database integration tests in the automated suite; CI
provider templates are structurally validated only, never run against a
live GitHub/GitLab/Jenkins instance.

## Safety guarantees

- No network request without an explicit `--target`; no substitute-target
  guessing from an OpenAPI document's `servers:` entry.
- No database connection without an explicit `--database-profile`
  (`readonly: true` mandatory); no arbitrary-SQL-execution capability
  anywhere in the codebase.
- No repository script is ever executed by discovery or any other
  command; the only external process the tool ever runs is a read-only
  `git rev-parse`/`git status --porcelain`.
- No credential is ever read from a scanned repository, and none — nor a
  cookie/Authorization header/connection string — is ever written into a
  report, log, or exception (redaction verified against real HTTP
  responses, not just pattern-matching unit tests).
- `--ci` and CI-environment detection never authorize network traffic or
  relax any safety gate by themselves.
- A saved baseline is immutable; only `baseline save`, to its own
  explicit `--output` path, ever writes one.
- Every performance-testing numeric knob has a hard ceiling independent
  of configuration.

Full detail, including how each guarantee was verified: `docs
/V1_HARDENING_AUDIT.md` and `docs/V1_FREEZE.md`.
