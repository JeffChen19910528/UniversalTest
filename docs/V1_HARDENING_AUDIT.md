# V1 Hardening / Architecture / Safety Audit

Performed before the V1.0 freeze, covering the complete Phase 1-8
repository (`skill.md`, `SPECIFICATION.md`, `ARCHITECTURE.md`,
`ROADMAP.md`, `PROGRESS.md`, `CHANGELOG.md`, `README.md` all read in full,
cross-checked against the actual source). This is not a new feature phase
— see `V1_FREEZE.md` for what V1 promises; this document only records what
was found and fixed while verifying it.

**Result: two real (Critical/High) findings, both fixed and covered by new
regression tests. No architecture boundary violations. No unsafe network/
database/repository-execution behavior found. 563 tests passing (526
before this audit, 37 new).**

---

## Architecture Audit

**PASS**, with one *finding* noted for the record (not a violation — see
below).

Verified by direct `grep`/import inspection, not by trusting prior
documentation:

- `core/` imports no adapter, no `httpx`, no database driver, no CI
  provider SDK, and no `discovery`/`assessment`/`regression`/
  `quality_gate`/`reporting` package. Confirmed empty result for all of:
  `grep -rn "^import httpx\|adapters\." src/universal_test/core/`.
- `assessment/`, `regression/`, and `quality_gate/` import adapter-defined
  **dataclasses only** (`DatabaseDiscoveryResult`, `ProjectModel`,
  `PerformanceResult` — for type hints and reading already-computed
  fields), never an execution entry point. Confirmed: `db_discover`,
  `rest_run`, `PerformanceRunner(` appear nowhere in these three packages.
  Finding (not a violation, recorded for future reference): these
  dataclasses live inside their producing adapter module rather than a
  neutral shared location, so `assessment`/`regression` technically depend
  on `adapters.database`'s import path for a type name. This is
  pre-existing, intentional Phase 5/6 design (already documented in
  ARCHITECTURE.md §9/§10) and causes no behavioral coupling — a future
  phase could hoist these dataclasses into `core.models` if the dependency
  direction ever needs to be stricter, but nothing about V1's actual
  behavior depends on it.
- `quality_gate/engine.py::evaluate()` only reads an already-built
  `ProjectAssessment`/`RegressionSummary` — confirmed no call to
  `build_assessment()` or `compare()` anywhere inside `quality_gate/`.
- `reporting/` imports only domain-model types; contains no
  `compute_overall_status`/`execution_health_status`/`status_from_findings`
  /`evaluate` calls — confirmed empty grep. Pure rendering.
- `cli/main.py` contains no direct `AssessmentStatus`/`Severity` value
  manipulation — confirmed empty grep — meaning it never recomputes a
  judgement the lower layers should own; it only calls
  `build_assessment()`/`compare()`/`evaluate()` and renders/exits.
- `testing/performance/models.py`'s only occurrence of the word `httpx` is
  in its own docstring explaining why it doesn't import it — not an actual
  import (confirmed).

## Data Flow Audit

**PASS.** Traced end-to-end via the new `tests/e2e/test_e2e_pipeline.py`
(§9 below), which exercises every layer against one real fixture project
and asserts the pipeline never crashes, never re-executes a completed
step, and produces byte-identical assessment/regression/quality-gate
content across two runs against the same inputs (timestamps aside —
`test_09_full_pipeline_is_deterministic`).

## Safety Audit

**PASS.**

- **Network**: `grep -rln "httpx\.\|socket\.\|urllib\.request" src/` finds
  exactly two files — `adapters/rest/executor.py` and
  `adapters/rest/performance_executor.py` — both only ever constructed
  when the CLI is given an explicit `--target`. `scan`, `assess` without
  `--target`, `--dry-run`, and `baseline compare` without `--target` all
  have dedicated zero-traffic tests dating back to Phases 2/3/5/7,
  re-verified passing in this audit's full run. OpenAPI `servers` is
  confirmed never read as a target — the only occurrence of `.servers` in
  the entire codebase is in `adapters/rest/models.py`'s `to_dict()` for
  display purposes. `--ci` re-verified to never authorize traffic by
  itself (`test_ci_flag_alone_does_not_authorize_traffic`, plus a new
  parametrized check across `CI`/`GITHUB_ACTIONS`/`GITLAB_CI`
  /`JENKINS_URL`).
- **Database**: `DatabaseDriver` (the only class any engine driver
  implements) has no `execute(sql)` method — confirmed by re-reading
  `adapters/database/base.py`. Every `cursor.execute(...)` call site found
  by `grep` is a **private** `_query()` helper called only with
  hard-coded, parameterized SQL text written by the driver itself, never
  with a string built from repository/user input — confirmed no
  `_query(f"..."` f-string-interpolated SQL exists anywhere. `readonly:
  true` remains mandatory at profile-load time (`profile.py`); SQLite
  connects via a read-only URI (`sqlite.py`). `discovery/database.py`
  (Phase 2 evidence detection) matches dependency-name strings only —
  confirmed it imports no driver and calls no `connect()`.
- **Repository execution**: the only `subprocess`/`os.system` call site in
  the entire `src/` tree is `discovery/repository.py`'s `git rev-parse`
  /`git status --porcelain` (fixed argument list, no `shell=True`, 10s
  timeout) — confirmed by repo-wide grep. Nothing reads or executes
  `setup.py`, `package.json` scripts, a `Makefile`, a `Dockerfile`, or a
  CI config's own commands.

## Secret Leakage Audit

**FAIL → FIXED (Critical).** This audit's most important finding.

`core/redaction.py`'s `_KEY_VALUE_PATTERN`/`_SENSITIVE_KEY_PATTERN` never
covered `Cookie`/`Set-Cookie` at all. Reproduced concretely before fixing:

```python
>>> redact_mapping({'Set-Cookie': 'sessionid=abc123XYZ; HttpOnly'})
{'Set-Cookie': 'sessionid=abc123XYZ; HttpOnly'}   # leaked, unredacted
```

Since `adapters/rest/executor.py` passes every response header through
`redact_mapping()` before it reaches `TestResult`/`report.json`/`.md`
/`.html`/a saved baseline, a real target that set a session cookie in its
response would have had that cookie value written straight into every
output format this tool produces. **Fixed** by adding `cookie`/
`set[_-]?cookie` to both redaction patterns
(`src/universal_test/core/redaction.py`), so a `Set-Cookie`/`Cookie`
header's value is now fully redacted regardless of its content, the same
guarantee `password`/`token`/`api_key` already had. Verified with:

- 5 new unit tests (`tests/core/test_redaction.py`) covering the mapping
  path, the free-text path, and case-insensitive key matching (`cookie`,
  `Cookie`, `set-cookie`, `Set-Cookie`, etc.).
- 1 new **real HTTP** integration test
  (`tests/adapters/rest/test_secret_redaction.py::
  test_set_cookie_response_header_never_appears_in_output`) — a new
  `/with-cookie` fixture-server route actually sends a `Set-Cookie` header
  and the test asserts the real session value never appears in any of
  `TestResult`/text/JSON/Markdown output.

Every other secret type the brief asks about was already covered before
this audit and re-verified passing: Bearer token, API key, DB
password/connection-string, and Authorization header — across
`report.json`/`.md`/`.html`, `baseline.json`, `TestResult`,
`PerformanceRequest.to_dict()` (headers deliberately excluded by design),
`DatabaseInfo`/`DatabaseProfile.to_dict()`, `AssessmentFinding`, and the
Quality Gate's own output (`test_bearer_token_never_appears_in_quality_gate_output`,
which deliberately uses a *wrong* token so the finding text is actually
populated with real content, not skipped because nothing failed).

## CLI Contract Audit

**FAIL → FIXED (High): Windows console compatibility.**

`--help` output for every subcommand (`scan/test/performance/database
/assess/baseline/baseline save/baseline compare`) was re-verified clean
(exit 0, no mojibake) — the existing house rule against `§`/em dash in
`argparse` `help=` strings and logged/printed error messages (established
during Phases 6-7) held for everything added in Phase 8.

However, a **content-level** instance of the same underlying bug class was
found: several `AssessmentFinding`/`RegressionFinding` description strings
and two report-renderer template strings still contained a raw em dash
(`—`), which reaches the console verbatim whenever that finding text is
rendered and printed without `--output` (e.g. `assess --format html` or
`--format markdown` with no `--output`, which `print()`s the rendered
report directly). Reproduced concretely:

```python
>>> print('vulnerability finding — it is a pattern match only.')
vulnerability finding <?>X it is a pattern match only.   # garbled on this Windows console
```

**Fixed** (7 files, all replaced with a plain ASCII hyphen, matching the
established house rule): `assessment/configuration_assessment.py`,
`assessment/database_assessment.py` (×2), `regression/discovery_compare.py`,
`regression/engine.py`, `reporting/html_report.py` (×2),
`reporting/markdown_report.py` (×3). Verified empirically:
`assess --format html`/`--format markdown` (no `--output`) against a
fixture that actually triggers each of these lines no longer produces any
mojibake. A new **durable regression test**
(`tests/test_windows_console_compatibility.py`, 5 tests) exercises the
actual finding-generation code paths (not a static grep) so a future
reintroduction is caught even via string concatenation/f-string assembly
rather than a literal.

Otherwise: `--format`/`--output`/`--dry-run`/`--yes`/`--ci`/`--target`
semantics are consistent across every command that defines them (verified
by re-reading `_add_common_args`/`_add_pipeline_args`/`_add_assess_args` —
one shared definition per flag, never redefined ad hoc per subcommand).
Error messages are specific per failure mode (`ConfigurationError` text
names the exact bad field/value; `DiscoveryError`/`OpenApiError`
/`RegressionError`/`DatabaseError` are each distinguishable in logs).

## Exit Code Audit

**PASS.** New `tests/cli/test_exit_code_matrix.py` (15 tests) makes the
full contract explicit and independently diagnosable per scenario:

| Scenario | Exit | Verified |
|---|---|---|
| Success, no target | 0 | ✅ |
| Success, target, all passing | 0 | ✅ |
| Warning-level result (no fail_on match) | 0 | ✅ |
| Quality Gate failure (real assertion mismatch) | 1 | ✅ |
| Wrong credential (real 401, not missing) | 1 | ✅ |
| Invalid `--format` for `assess` | 2 | ✅ |
| Nonexistent project path | 2 | ✅ |
| Invalid/unloadable `--baseline` | 2 | ✅ |
| Unreachable target (connection refused) | 3 | ✅ |
| Timeout (transport wipeout, not an assertion failure) | 3 | ✅ |
| Missing target (functional stays `NOT_ASSESSED`) | 0 | ✅ |
| Missing credential (auth-required test `SKIPPED`) | 0 | ✅ |
| Correct credential | 0 | ✅ |
| Non-interactive confirmation declined (`--performance` without `--yes`) | 0 (Performance `NOT_ASSESSED`, not a hard failure) | ✅ |

The timeout case is the subtlest and most important: a `RequestTimeoutError`
produces a **total** transport wipeout (`Functional Health: FAIL`), which
the Quality Gate's infra-error short-circuit correctly routes to exit `3`,
not `1` — confirmed by an actual `--timeout 0.05` against the fixture
server's real 300ms `/slow` endpoint, not a mocked timeout.

Per the brief's scope: this full `0/1/2/3` contract applies to `assess`
only. `scan`/`test`/`performance`/`database`/`baseline save`/`baseline
compare` were confirmed **unchanged** — still their pre-existing `0`/`2`
convention — by re-running their full pre-existing test suites unmodified.

## Configuration Audit

**PASS**, plus 3 new edge-case tests. `universal-test.yaml` re-verified
for: defaults, an explicit file, partial override, full override, unknown
top-level section (ignored, non-fatal), unknown key within a known section
(ignored), wrong type for a section (raises `ConfigurationError`), invalid
YAML (raises), and now additionally: a completely empty config file, an
empty `{}` mapping, and a section present but with a `null` value (`key:`
with nothing after the colon) — all three correctly fall back to that
section's defaults rather than crashing.

`regression.performance` and `quality_gate.fail_on`/`warn_on` (both
dict-valued, both with non-empty defaults) were specifically re-verified:
a partial override of one sub-key preserves every other default — the
exact class of bug found and fixed in Phase 7
(`_build_section()`'s dict-merge). No regression of that fix was found;
`quality_gate`'s nested-merge tests
(`test_quality_gate_nested_policy_merge_keeps_other_categories`) pass
using the identical merge code path.

`quality_gate.fail_on`/`warn_on` additionally get **shape validation**
(`_validate_quality_gate_policy()`, added in Phase 8) that a malformed
policy (non-mapping, non-list value, non-string list item) raises
`ConfigurationError` immediately — re-verified with 3 dedicated tests.

## Reporting Audit

**PASS.** `report.json` carries `schema_version` (`"1.0"`, `assessment
/models.py::SCHEMA_VERSION`); `baseline.json` carries its own
`schema_version` (`regression/models.py::SCHEMA_VERSION`, currently also
`"1.0"` but tracked independently) and `load_baseline()` refuses any
unrecognized value outright (`RegressionError`, re-verified:
`test_incompatible_schema_version_raises`). `report.md`/`.html` were
re-checked against `report.json` for the same core findings/category
statuses — they render from the identical `AssessReportBundle`, so there
is exactly one source of truth per run, not three independently-computed
outputs. No raw credential/Authorization header/cookie reaches any of the
three formats (re-verified end-to-end, see Secret Leakage Audit above).
Report generation determinism re-confirmed both at the renderer level
(`test_report_generation_is_deterministic`, same bundle rendered twice)
and now at the full-CLI level (`test_09_full_pipeline_is_deterministic`,
two independent `assess` invocations, timestamps aside).

## CI Audit

**PASS.** Simulated `CI`/`GITHUB_ACTIONS`/`GITLAB_CI`/`JENKINS_URL`
environment variables (never a real connection to any provider) confirm:
no interactive prompt is ever shown when non-interactive; `--ci` alone
never authorizes traffic (`--yes` still required); `--yes` alongside
`--ci` executes real traffic correctly; all four exit codes are reachable
and correct under simulated CI; `report.json` is valid JSON in every case;
`report.md`/`.html` are always written alongside it; and the artifact path
(`--output reports/`) is exactly what was requested, not provider-dependent.
The three CI templates (`examples/ci/*`) were re-validated: both YAML
files parse, all three mention `--ci`/`--yes`/`--baseline`, and none
contains a hardcoded credential.

## Dependency Audit

**PASS**, no changes needed. Three hard dependencies (`PyYAML`, `httpx`,
`jsonschema`) — all confirmed actually imported and used (`jsonschema` has
a documented, tested fallback if ever absent, despite being a declared
dependency — extra defense-in-depth, not dead code). Three optional
database-driver dependencies (`psycopg2-binary`, `mysql-connector-python`,
`pyodbc`) — confirmed imported **lazily**, inside each driver's own
`__init__`, never at module load time (`grep` for a top-level `import
pyodbc`/`psycopg2`/`mysql.connector` anywhere in `src/` returns nothing).
No CI-provider SDK, no browser-automation dependency, no unused or
duplicated dependency found. `dev` extra (`pytest`) is correctly scoped
out of the base install.

## Test Quality Audit

**PASS**, spot-checked rather than exhaustively re-read given 563 tests.
The specific categories the brief calls out by name were checked directly:

- **Database**: `tests/adapters/database/test_sqlite_driver.py` runs real
  queries against real fixture `.sqlite` files (foreign keys, indexes,
  views, `ANALYZE`-based row counts, a real write-attempt raising against
  the read-only connection) — not mocked.
- **CI**: `tests/cli/test_cli_quality_gate.py` and the new
  `test_exit_code_matrix.py` run the actual `main()` CLI entry point
  against the real offline fixture HTTP server, including a genuine
  connection-refused probe socket and a genuine 300ms-delayed timeout —
  not simulated return values.
- **Quality Gate**: `tests/quality_gate/test_engine.py` covers every rule
  in the vocabulary against hand-built (not mocked) `ProjectAssessment`
  /`RegressionSummary` objects — appropriate here since the gate's job is
  pure policy evaluation over already-computed data, so unit-level
  hand-built inputs are the correct level of test, backed by the CLI-level
  integration tests above for the full pipeline.
- **Regression**: `tests/cli/test_cli_baseline_command.py`'s functional
  regression test uses the fixture server's real, counter-based
  `/unstable` endpoint to produce an actual PASS-then-FAIL transition on
  the same test ID across two live HTTP runs — not a mocked status flip.
- **Secret redaction**: now backed by a real HTTP round-trip for every
  secret type (bearer token, API key, DB password, connection string,
  and — after this audit's fix — cookie), not string-pattern unit tests
  alone.

No tautological tests (asserting a constant against itself) or
implementation-detail-only tests were found in the sampled files. All new
tests added by this audit follow the same real-integration standard
(e.g. `test_e2e_pipeline.py` uses the real fixture server and a real
SQLite file throughout, never a mock).

## Documentation Audit

**PASS**, minor stale-reference fixes only, already applied. Cross-checked
`README.md`/`SPECIFICATION.md`/`ARCHITECTURE.md`/`ROADMAP.md`
/`PROGRESS.md`/`CHANGELOG.md` for: Phase status (all eight phases correctly
marked ✅ Done, Phases 9-11 correctly ⬜ Not started), supported databases
(SQL Server/PostgreSQL/MySQL/SQLite consistent everywhere), CLI commands
(all eight implemented commands listed consistently), exit codes (`0/1/2/3`
contract stated identically in `ARCHITECTURE.md` §13, `SPECIFICATION.md`
§4.11, and `README.md`'s CI/CD section), configuration section names
(`regression`, `quality_gate`, `ci` all documented where used), and report
schema (`schema_version` presence documented in both `ARCHITECTURE.md` and
`SPECIFICATION.md`). No completed item found still marked "planned"; no
V1 non-goal (security scanner, penetration tester, browser automation,
autonomous AI tester, fuzzing framework) is claimed as a capability
anywhere in `README.md` or `SPECIFICATION.md` — both explicitly disclaim
each of these.

## Dead Code Audit

**FAIL → FIXED (Low).** Ran `pyflakes` (not previously part of this
project's toolchain; used here as a one-time audit pass, not added as a
new dependency) across `src/` and `tests/`. Found and removed:

- `adapters/rest/adapter.py`: unused `dataclasses.field` and
  `core.models.result.TestResult` imports.
- `discovery/serializers.py`: an f-string with no placeholder
  (`f"- Git: yes"` → `"- Git: yes"`).
- 4 unused test-file imports (`os` in `test_auth.py`, `ErrorType` in
  `test_performance_execution.py`, `Path` in `test_cli.py`,
  `DatabaseDetection` in `test_report_renderers.py`) and one f-string
  missing a placeholder in `test_cli_database_command.py`.

No obsolete stubs, superseded commands, unused modules, duplicate
orchestration, or stale TODO/FIXME/HACK comments were found (a repo-wide
grep for `TODO|FIXME|XXX|HACK` returned zero matches). `report`/`run`
remain intentional, honest routing stubs (not dead code — they correctly
name the phase that implements them, per `skill.md` §4.1's "never silently
no-op" rule). Re-ran `pyflakes` after cleanup: clean on both `src/` and
`tests/`.

## Remaining Risks

- The dataclass-import coupling noted under Architecture Audit
  (`assessment`/`regression`/`reporting` importing `adapters.database`'s
  `DatabaseDiscoveryResult` type) is a soft architectural wart, not a
  behavioral risk — flagged for awareness, not required to fix before V1.
- `report`/`baseline.json`'s `SCHEMA_VERSION` are both currently `"1.0"`
  independently (not versioned in lockstep) — intentional per their
  separate audiences, but worth double-checking they don't need to move
  together if a future phase changes one shape without the other.
- CI provider templates remain unvalidated against a live GitHub/GitLab
  /Jenkins instance (explicitly out of scope per the Phase 8 brief and
  this audit's own instruction not to connect to any of them) — a real
  first live run on each provider is the natural remaining validation
  step, owned by whichever project first adopts a template.
- No load/stress testing of the tool's own discovery/report-generation
  pipeline beyond the ~260-file self-scan and 5-iteration repeat measured
  in §13 (flat ~0.24s per scan, no growth, ~0.7MB peak traced memory) — a
  much larger repository (tens of thousands of files) was not available to
  test against in this environment.

## V1.0 Recommendation

**Ready for V1.0 freeze** once this audit's fixes are accepted. Both
Critical/High findings (cookie redaction, Windows console garbling in
finding text) are fixed and covered by durable regression tests, not just
patched ad hoc. No architecture boundary violations, no unsafe network/
database/repository-execution behavior, and no overclaiming language were
found. See `V1_FREEZE.md` for the frozen capability/contract surface.
