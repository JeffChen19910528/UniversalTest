# V1.0 Release Checklist

Verified during V1.0 Release Engineering (2026-08-09), after the V1
Hardening / Architecture / Safety Audit (`docs/V1_HARDENING_AUDIT.md`).
Every item below was actually executed and observed, not assumed.

- [x] **Version 1.0.0 frozen** — single source of truth:
      `src/universal_test/__init__.py::__version__ = "1.0.0"`.
      `pyproject.toml` reads it dynamically (`dynamic = ["version"]` +
      `[tool.setuptools.dynamic]` `attr = "universal_test.__version__"`) —
      no second, independently-maintained version literal exists anywhere
      in the repository.
- [x] **Package builds** — `python -m build` succeeds from a clean
      `dist/`/`build/`/`*.egg-info`, producing both artifacts.
- [x] **Wheel installs** — `universal_test-1.0.0-py3-none-any.whl`
      installed cleanly into a throwaway virtual environment via `pip
      install`.
- [x] **Sdist builds** — `universal_test-1.0.0.tar.gz` produced alongside
      the wheel by the same `python -m build` invocation.
- [x] **CLI `--version` works** — `universal-test --version` prints
      `universal-test 1.0.0` (ASCII-safe, deterministic, verified in the
      clean install).
- [x] **CLI `--help` works** — verified for the top-level parser and
      every subcommand (`scan`, `test`, `performance`, `database`,
      `assess`, `baseline`) in the clean install; all exit 0, no mojibake.
- [x] **Base installation works** — `pip install` (no extras) resolves to
      exactly `PyYAML`, `httpx`, `jsonschema` (+ their transitive deps) —
      no database driver, browser driver, or CI SDK. `scan`, `test`,
      `performance --dry-run`, `assess`, `baseline save`/`compare` all ran
      successfully in this base install.
- [x] **Optional database installation works** — `pip install
      universal-test[database]` resolves `psycopg2-binary`,
      `mysql-connector-python`, and `pyodbc` correctly.
- [x] **Clean environment verified** — a throwaway venv
      (`.venv-release-test`, removed after use, never committed) was used
      for every installation/CLI check above, not the development `.venv`.
- [x] **E2E smoke test passes** — the canonical
      `tests/fixtures/e2e-project/` fixture exercised via the installed
      wheel against the real offline fixture HTTP server and a real
      SQLite file: `scan` (0), `test --target` (0, 5/5 passed),
      `performance --dry-run` (0, no traffic sent), `database --dry-run`
      without a profile (2 — correctly refused, since dry-run still needs
      to know which database to plan for), `assess --target` (0),
      `baseline save` (0), `baseline compare` (0, read-only, `PASS`).
- [x] **Full test suite passes** — `python -m pytest -q`: **563 passed, 0
      failed** (unchanged from the post-audit count — release engineering
      added packaging/config changes, not new pytest coverage; the wheel-
      based E2E smoke test above was run as a scripted manual verification
      against the built artifact, matching this checklist item's own
      "before: 563 / after: 563 / added: 0" scope).
- [x] **Package contents audited** — wheel contains only
      `universal_test/**` source + `dist-info` metadata (verified via
      `zipfile -l`, no test/fixture/report/cache files). Sdist initially
      leaked 2 stray top-level `tests/` files due to missing sdist file-
      selection rules (setuptools' default heuristic, not intentional
      inclusion) — fixed by adding `MANIFEST.in` (`prune tests`,
      `examples`, `docs`, `reports`, `plugins`, `schemas`, `.venv`; exclude
      `__pycache__`/`*.pyc`); re-verified clean after the fix (0 suspect
      entries).
- [x] **No secrets in artifacts** — neither the wheel nor the sdist
      contains any credential, `.env` file, local database file, or
      generated report — confirmed by full content listing (both
      artifacts contain only source code, packaging metadata, and
      `README.md`).
- [x] **README finalized** — rewritten as V1.0 user documentation (What
      It Does / Installation / Quick Start / Commands / Configuration /
      Reports / Regression / Safety Model / Supported Technologies /
      Limitations / Development) — development/Phase-history framing
      removed from the user-facing sections; every configuration example
      re-verified to parse against the real schema
      (`load_config()`), every command example re-verified against real
      CLI output.
- [x] **Configuration docs finalized** — README's "Configuration" section
      shows every current section (`performance.thresholds`,
      `regression.performance`, `quality_gate.fail_on`/`warn_on`,
      `ci.retry.count`, `database.enabled`) with its actual default value,
      re-verified by loading the exact YAML shown through `load_config()`.
- [x] **CI docs finalized** — README's "CI/CD" section documents the
      exit-code contract, the Quality Gate policy, the pull-request
      workflow, immutable-baseline handling, and links to all three
      provider templates; explicitly states `--ci` never implies `--yes`
      and CI-environment detection never bypasses authorization.
- [x] **Safety docs finalized** — README's "Safety Model" section covers
      repository (read-only), network (explicit `--target` only),
      database (explicit `--database-profile`, no arbitrary SQL),
      secrets (redacted, never read from the repo), CI (never
      auto-authorizes), and performance (hard ceilings) — matching
      `docs/V1_FREEZE.md`'s safety guarantees verbatim in substance.
- [x] **CHANGELOG 1.0.0 finalized** — `## [1.0.0]` section added with a
      concise capability summary (not a phase-by-phase commit log); the
      existing detailed Phase 0-8 history preserved underneath as
      "Full development history", clearly separated so a reader wanting
      just the release notes doesn't have to wade through development
      narrative.
- [x] **`V1_FREEZE.md` consistent** — re-checked against the actual
      installed package: supported databases, CLI commands, exit codes,
      and configuration section names all match what the clean-install
      verification above actually observed.
- [x] **`V1_HARDENING_AUDIT.md` consistent** — no changes needed; release
      engineering introduced no new findings that would invalidate it
      (the version-source consolidation and `MANIFEST.in` addition are
      packaging concerns, not architecture/safety findings).

## Not part of this checklist (explicitly out of scope)

Per the release engineering brief's own scope: no new adapter, CI
provider, or database engine was added; no Post-V1 feature was
implemented (candidates recorded in `docs/POST_V1_BACKLOG.md` instead).
