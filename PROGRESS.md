# PROGRESS.md

Log of completed work, phase by phase (`skill.md` §31.14, §31.20).

---

## Phase 0 — Repository initialization — ✅ Done (2026-08-09)

**Files created:** `SPECIFICATION.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
`PROGRESS.md`, `CHANGELOG.md`, `README.md`.

**Functionality added:** none (planning only).

**Tests executed:** n/a.

**Known limitations:** none at this stage.

**Next phase:** Phase 1 — Core.

---

## Phase 1 — Core — ✅ Done (skeleton, 2026-08-09)

### Files changed

New Python package under `src/universal_test/`:

- `core/models/` — `enums.py`, `evidence.py`, `test_spec.py`, `result.py`
- `core/assertions/` — `path.py`, `builtin.py`, `engine.py`
- `core/engine/test_engine.py`
- `core/orchestration/orchestrator.py`
- `core/configuration/config.py`
- `core/errors.py`, `core/redaction.py`, `core/logging_setup.py`
- `cli/main.py` (+ `__main__.py` for `python -m universal_test`)
- Placeholder `__init__.py` for `discovery/`, `adapters/`, `testing/`,
  `assessment/`, `reporting/` (module boundaries exist; no logic yet)
- `pyproject.toml`, `.gitignore`
- `docs/README.md`, `examples/README.md`, `plugins/README.md`,
  `schemas/README.md`, `reports/.gitkeep`

Tests under `tests/core/` and `tests/cli/` (see below).

### Functionality added

- **Domain models**: `ResultStatus`, `AssessmentStatus`,
  `DetectionConfidence`, `Severity` enums (kept separate per `skill.md`
  §4.1/§20 — never collapsed into one status); `Evidence`, `TestCase`
  (+`TestTarget`, `AssertionSpec`), `AssertionResult`, `TestResult`,
  `Finding` dataclasses, all with `to_dict()` matching the evidence shape in
  `skill.md` §4.3.
- **Assertion engine**: registry-based `AssertionEngine` with all 13 builtin
  assertions from `skill.md` §9 (`status_code`, `status_code_in`,
  `response_time_less_than`, `json_path_exists`, `json_path_equals`,
  `json_schema_valid` [minimal — see limitations], `header_exists`,
  `header_equals`, `body_contains`, `body_not_contains`, `row_count`,
  `value_equals`, `value_not_null`), all producing structured `Evidence`.
  Custom assertions can be registered at runtime.
- **Test engine**: `TestEngine.run(test_case, executor)` executes one
  `TestCase` via an adapter-shaped executor callable, evaluates its
  assertions, and returns a `TestResult`. Distinguishes `PASSED / FAILED /
  ERROR / UNKNOWN` (a test case with no assertions is `UNKNOWN`, not
  `PASSED` — avoids overclaiming per `skill.md` §4.1).
- **Orchestrator**: `Orchestrator.run_test_cases()` batch-runs a list of
  `TestCase`s and returns a `RunResult` with per-status summary counts.
- **Configuration**: `Config` dataclass tree mirroring `universal-test.yaml`
  (`skill.md` §18) with safe-by-default values (`performance.enabled=False`,
  `database.enabled=False`, `security.enabled=False`, `ai.enabled=False`).
  `load_config()` works with zero config, an explicit file, or a
  `<project>/universal-test.yaml`, plus programmatic overrides; invalid
  YAML/missing files/non-mapping sections raise `ConfigurationError` rather
  than silently proceeding with bad data; unknown keys are ignored (forward
  compatible, non-fatal).
- **Secret redaction**: `core/redaction.py` covers key=value text (logs,
  config dumps), connection-string credentials, and PEM private-key blocks;
  `redact_mapping()` redacts by key name for structured dict/JSON data.
  Wired into `logging_setup.py` so every log record is redacted before
  formatting.
- **Errors**: `UniversalTestError` base with `ConfigurationError`,
  `DiscoveryError`, `AdapterError`, `ExecutionError`, `AssertionEngineError`.
- **CLI skeleton**: `universal-test {scan,assess,test,performance,report,run}
  <path>` with `--config/--output/--format/--verbose/--adapter/--target
  /--dry-run/--safe-mode`. Validates config, refuses `performance` without an
  explicit `--target` (unless `--dry-run`), and otherwise reports which
  future phase implements the command — no silent no-ops, no stack traces.

### Tests executed

```
python -m pytest -q
```

**Result: 51 passed, 0 failed** (Python 3.11.6, `pytest` in a project-local
`.venv`). Coverage: domain models and their `to_dict()` shapes, redaction
(key=value, connection strings, PEM blocks, structured dict redaction), all
13 builtin assertions + unknown-type/missing-param error handling + custom
registration, `TestEngine` (pass/fail/error/unknown-no-assertions paths),
`Orchestrator` summary counts, `Config` loading (defaults, file, missing
file, invalid YAML, non-mapping section, override precedence, unknown-key
tolerance), the full CLI error hierarchy, and CLI routing for every
subcommand including the performance `--target` guard and `--version`.

Manually verified end-to-end via `python -m universal_test scan .`,
`performance .` (refused, exit 2), and `performance . --target
http://localhost:8080` (accepted, exit 0).

### Known limitations

- No discovery, no adapters, no test generation, no report generation —
  every CLI subcommand is a validated routing stub.
- `json_schema_valid` is a minimal type/required-field checker, not full
  JSON Schema draft validation (no `jsonschema` dependency yet — see
  ARCHITECTURE.md §8.4).
- `value_equals`/`value_not_null`/`json_path_*` use a small dotted/bracket
  path resolver, not full JSONPath.
- No integration tests yet against real fixture projects (`skill.md` §21) —
  nothing to discover until Phase 2.
- No `.gitignore`-respecting filesystem walker yet — not needed until
  discovery exists.

### Next phase

Phase 2 — Discovery (filesystem, language, framework, service, API,
database detection). **Per `skill.md` §32, do not start Phase 2 without an
explicit go-ahead — this is the checkpoint.**

---

## Phase 2 — Discovery — ✅ Done (2026-08-09)

### Files changed

New under `src/universal_test/discovery/`: `models.py`, `filesystem.py`,
`repository.py`, `manifests.py`, `language.py`, `project_type.py`,
`framework.py`, `infrastructure.py`, `database.py`, `api.py`,
`test_framework.py`, `secrets.py`, `engine.py`, `serializers.py` (replacing
the placeholder `__init__.py` from Phase 1, which now re-exports `discover`
and `ProjectModel`).

`src/universal_test/cli/main.py` — `scan` is no longer a stub: it calls
`discovery.engine.discover()`, validates `--format` (`text`/`json`/
`markdown` supported now; `html`/`all` correctly error until Phase 5), and
writes to stdout or `--output`.

New tests: `tests/discovery/` (11 files: language/project-type, frameworks,
infrastructure, databases, APIs, test frameworks, secrets, filesystem
exclusions, repository/git, edge cases, serializers) and 7 new cases added
to `tests/cli/test_cli.py` for `scan`'s real behavior. New fixtures:
`tests/fixtures/{python-fastapi,dotnet-api,node-react,docker-project,
database-project,mixed-project}/`.

### Functionality added

- **Repository discovery**: git presence, root, branch, commit, dirty
  working tree — via `git rev-parse`/`status --porcelain` only (read-only,
  10s timeout, gracefully degrades to `UNKNOWN`-ish fields if git is
  missing or the repo can't be inspected). Verified by test to never mutate
  a real repo (`test_git_repo_never_modified_by_discovery`).
- **Filesystem walker**: excludes `node_modules, .git, bin, obj, build,
  dist, target, venv, .venv, __pycache__`, etc.; finds test directories
  (`tests/`, `test/`, `__tests__/`, `spec/`, `specs/`).
- **Manifest reader** (`manifests.py`): one bounded read of `package.json`,
  `pyproject.toml`, `requirements*.txt`, `*.csproj`/`*.sln`, `pom.xml`,
  `build.gradle(.kts)`, `composer.json`, `go.mod`, `Cargo.toml` — shared by
  every detector so language/framework/database detection reasons about
  real project metadata, not just file extensions. Parse failures (invalid
  TOML/JSON) are recorded as warnings and do not abort the scan.
- **Language detection**: 12 languages (Python, JavaScript, TypeScript, C#,
  Java, Go, Rust, PHP, Kotlin, Swift, Solidity, SQL), confidence anchored on
  manifest evidence where available, extension-count volume otherwise.
- **Project type / build system**: python, node, dotnet, java, go, rust,
  php, frontend, generic; pip/poetry, npm/yarn/pnpm, dotnet sdk,
  maven/gradle, go modules, cargo, composer.
- **Framework detection**: ASP.NET Core, WinForms, WPF, React, Angular, Vue,
  Node.js, Express, FastAPI, Django, Flask, Spring Boot, Laravel, Hardhat,
  Foundry — only from concrete manifest-dependency or marker-file evidence
  (verified: `database-project` fixture, which has no web framework
  manifest evidence, correctly yields zero framework detections).
- **Infrastructure**: Dockerfile, Docker Compose, Kubernetes (directory
  name or bounded `apiVersion:`/`kind:` YAML content scan), Terraform,
  GitHub Actions, GitLab CI, Jenkins, Azure Pipelines.
- **Database evidence**: SQL Server, PostgreSQL, MySQL, SQLite, MongoDB,
  Redis — from dependency names, `*.sqlite`/`*.db` files, connection-string
  *patterns* in known config files, and `docker-compose` service images.
  Never opens a connection.
- **API/service evidence**: OpenAPI/Swagger (filename + content
  confirmation), GraphQL (files/dependencies), REST-style routing
  directories (`routes/`, `controllers/`, `api/` — `INFERRED` only, real
  endpoint parsing is Phase 3).
- **Test framework detection**: pytest, unittest, Jest, Vitest, Mocha,
  NUnit, xUnit, MSTest, JUnit, go test, cargo test.
- **Secret pattern scanning**: password/api_key/token/secret/connection-
  string/private-key patterns; only `file`, `line`, `pattern_type` are
  recorded, the matched value is discarded before it reaches a
  `SecretFinding` — verified by
  `test_secret_values_never_appear_in_any_serialized_output`, which asserts
  the fixture's actual secret value string doesn't appear in text/markdown/
  JSON output. Common placeholder values (`REPLACE_ME`, `CHANGEME`, ...) are
  filtered out.
- **`ProjectModel`**: framework-independent normalized result (plain
  dataclasses, `to_dict()`, no Python-specific serialization) — every
  detection carries `confidence: DetectionConfidence` + `evidence:
  list[Evidence]`, never a bare assertion.
- **`universal-test scan`**: `--format text|json|markdown` to stdout or
  `--output <file-or-dir>`; a detector failure is caught per-step and
  surfaces as a `ProjectModel.warnings` entry rather than crashing the scan.

### What's still UNKNOWN / not covered

- OpenAPI/Swagger/GraphQL **endpoint** parsing (paths, schemas) — file/content
  evidence only; Phase 3.
- No source-code import scanning for frameworks (deliberate — avoids
  asserting from a single weak signal); a framework used without a
  corresponding manifest entry or marker file will not be detected.
- Kubernetes and secret detection use bounded heuristic scans (capped file
  counts / regex patterns), not exhaustive YAML/AST parsing — documented as
  best-effort in `ARCHITECTURE.md` §6.2, §10.
- `--format html` / `--format all` for `scan` correctly return exit code 2
  (not implemented) rather than emitting a partial report.
- Repository discovery degrades to `UNKNOWN`-ish fields (`branch=None`,
  `commit=None`) when git is present but the executable can't be found or a
  command fails — this is surfaced via `RepositoryInfo.note`, not silently
  swallowed.

### Tests executed

```
python -m pytest -q
```

**Result: 103 passed, 0 failed** (51 from Phase 1 + 52 new). Breakdown of
new coverage: language/project-type detection across all 6 fixtures +
mixed-project (multi-language), framework detection (including the
"no weak assertions" negative case), infrastructure, databases (including
`docker-compose` service-image evidence), API evidence, test frameworks,
secret detection (including the placeholder-filtering and
value-never-leaks checks), filesystem exclusion of vendor directories, git
repository discovery against a real throwaway `git init` repo (including a
"never mutates the repo" check), 7 edge cases (empty repo, unknown/generic
project, malformed `pyproject.toml`/`package.json`, incomplete project,
nonexistent path, path-is-a-file), and serializer output validation. CLI
gained 7 new `scan`-specific tests (text/json/markdown output, `--output`
file writing, unsupported-format rejection, nonexistent-path handling).

Manually verified end-to-end: `universal-test scan tests/fixtures/mixed-project`
correctly reports both Python/FastAPI and Node/React, Docker, and GitHub
Actions in one pass; `universal-test scan .` against this repo itself
completes cleanly and correctly reports `is_git: false` (this repo has no
`.git` directory).

### Known limitations

- No adapters, test generation, or report generation yet (Phase 3+/5) — only
  `scan` is real; `assess/test/performance/report/run` remain routing stubs.
- Framework/database/test-framework detection is manifest/marker-file driven
  only, by design — no AST or import-graph analysis.
- No caching/incremental discovery yet (skill.md §27) — every `scan` walks
  the full tree; acceptable at current scale, worth revisiting if discovery
  time becomes noticeable on very large repositories.
- Windows console encoding: avoid non-ASCII symbols (e.g. `§`) in
  user-facing CLI strings — confirmed garbled in this environment's default
  codepage during Phase 1 and fixed there; carried forward as a house rule
  for all new CLI/log strings.

### Next phase

Phase 3 — REST Adapter (OpenAPI parser, endpoint model, conservative test
generation, execution, assertions, report output). **Per `skill.md` §32 /
the Phase 2 brief's stop condition, do not start Phase 3 (or performance
testing, browser automation, SQL execution, AI integration) without an
explicit go-ahead.**

---

## Phase 3 — REST/OpenAPI Functional Testing — ✅ Done (2026-08-09)

### Files changed

New under `src/universal_test/adapters/rest/`: `models.py` (normalized
`ApiSpecification`/`ApiEndpoint`/`ParameterModel`/`RequestBodyModel`/
`ResponseModel`/`SecurityScheme`/`SchemaModel`), `openapi_loader.py`
(document loading + internal `$ref` resolution with cycle/depth guards),
`normalizer.py` (OpenAPI 3.x → normalized model; rejects Swagger 2.0 and
missing-`paths` documents), `discovery_bridge.py` (candidate spec discovery,
`MultipleSpecsFoundError`/`NoSpecFoundError`), `request_data.py`
(deterministic value generation), `test_generation.py` (positive/negative
`TestCase` generation + the `_control` skip mechanism), `auth.py` (env-var
credential resolution), `executor.py` (`httpx`-based HTTP execution),
`adapter.py` (`run()` orchestration + `RestAdapter` contract wrapper),
`serializers.py` (dry-run/run-result text/JSON/Markdown).

Modified: `src/universal_test/core/errors.py` (+`OpenApiError`,
`TargetError`, `NetworkError`, `RequestTimeoutError` — additive only);
`src/universal_test/core/assertions/builtin.py` (`json_schema_valid` now
`jsonschema`-backed, explicitly authorized by the Phase 3 brief §10);
`src/universal_test/discovery/api.py` (exported `OPENAPI_NAME_HINTS` for
reuse instead of duplicating the filename heuristic);
`src/universal_test/cli/main.py` (`test` command fully wired: new
`--openapi/--timeout/--bearer-token-env/--api-key-env/--api-key-header
/--basic-auth-user-env/--basic-auth-pass-env` flags, dry-run, missing-target
handling); `pyproject.toml` (+`httpx`, +`jsonschema`).

New tests: `tests/adapters/rest/` (`test_parsing.py`, `test_dry_run.py`,
`test_execution.py`, `test_secret_redaction.py`, `test_request_data.py`,
`test_auth.py`, plus `fixture_server.py`/`conftest.py` test infrastructure),
`tests/cli/test_cli_test_command.py`, 4 new cases added to
`tests/core/test_assertions.py` for the `jsonschema` upgrade. New fixtures:
`tests/fixtures/openapi-{basic,auth,invalid,multiple,schema}/`.

### Functionality added

- **OpenAPI parsing**: OpenAPI 3.x only (Swagger 2.0 rejected with a clear
  `OpenApiError`, not partially parsed); internal `$ref`s resolved
  recursively with cycle detection and a depth cap; external `$ref`s left
  unresolved with a warning — **never fetched over the network**
  (`ARCHITECTURE.md` §2/§7.1 explains why no OpenAPI-parsing library was
  added instead of writing this by hand).
- **Multi-spec safety**: reuses `discovery.api`'s exact filename heuristic
  (now exported as `OPENAPI_NAME_HINTS`) so `scan` and `test` agree on
  candidates; more than one candidate without `--openapi` raises
  `MultipleSpecsFoundError` with a sorted, deterministic candidate list —
  never picks one arbitrarily (verified:
  `test_multiple_specs_without_explicit_selection_raises`).
- **Normalized API model**: `ApiSpecification`/`ApiEndpoint`/etc. — plain
  dataclasses with `to_dict()`, no OpenAPI-parser-specific object leaks past
  `adapters/rest/`; Core imports none of it.
- **Conservative test generation**: positive tests built only from
  documented `example`/`default`/`enum`/`minimum`/safe format defaults —
  never fabricated; when confidence is insufficient the endpoint's test is
  generated (visible in dry-run) but marked to skip execution and resolves
  to `UNKNOWN`. Up to 3 negative tests per endpoint (missing required
  parameter, missing required body field, invalid type, unsupported content
  type), generated only when a concrete documented error status exists to
  assert against — no fuzzing.
- **Assertion engine reuse**: zero new assertion types; generated tests use
  only `status_code`/`status_code_in`/`json_schema_valid`, all pre-existing.
- **Authentication**: bearer/API-key/basic schemes detected from
  `securitySchemes`; credentials read only from named environment variables
  (`--bearer-token-env NAME`, etc.) — never guessed, never read from the
  scanned repository, never used to attempt a login probe. An endpoint
  requiring auth with no matching credential is marked `SKIPPED` and never
  executed (verified: `test_auth_required_without_credentials_is_skipped`).
- **Target safety**: `--target` always wins over the spec's own `servers`
  entry (verified: `test_target_override_wins_over_spec_servers`); omitting
  `--target` (without `--dry-run`) still completes discovery/generation and
  then prints the required "No execution target specified" /
  "analyzed successfully, but no HTTP requests were executed" message and
  exits non-zero, rather than silently doing nothing or guessing a target.
- **HTTP execution**: `httpx`-based; distinguishes `NetworkError`
  (connection refused) / `RequestTimeoutError` / `TargetError` (other
  request failures) from assertion `FAILED` — a target that's merely
  unreachable is never reported as "the API is broken" (verified:
  `test_connection_failure_is_an_error_not_a_failed_assertion`,
  `test_timeout_is_an_error_with_a_distinct_exception_type`,
  `test_auth_required_with_wrong_bearer_token_fails_not_errors` — the last
  proving a *wrong* credential correctly becomes `FAILED`, not `ERROR`).
- **Schema validation**: `json_schema_valid` upgraded from Phase 1's minimal
  checker to the `jsonschema` library (full draft support); a malformed
  schema is reported as a schema error, never silently passed or conflated
  with an API failure; PASS/FAIL verified against a real server response
  (`test_schema_validation_pass_and_fail`, using the `openapi-schema`
  fixture's intentionally-mismatched `/widgets-broken` endpoint).
- **Secret redaction**: the executor never returns sent auth headers/query
  params in the context `AssertionEngine` evaluates, and response
  headers/body are passed through `core.redaction` before being stored —
  verified end-to-end (`test_secret_redaction.py`: token/API-key absent from
  `TestCase`/`TestResult`/text/markdown/JSON output, including when the
  *wrong* token is sent and echoed nowhere).
- **CLI**: `universal-test test <path> --target <url> [--openapi PATH]
  [--dry-run] [--format text|json|markdown] [--output PATH]
  [--bearer-token-env NAME] [--api-key-env NAME] [--api-key-header NAME]
  [--basic-auth-user-env NAME] [--basic-auth-pass-env NAME] [--timeout SEC]`.
  Dry-run output matches the brief's required shape exactly ("Discovered: N
  endpoints" / "Generated: M test cases" / per-test "Expected: ..." /
  "No HTTP requests executed.").

### Test generation and execution behavior (examples)

Against `tests/fixtures/openapi-basic` (`GET/POST /users`, `GET /slow`):
`universal-test test <path> --dry-run` reports 3 endpoints discovered, 5
test cases generated (1 positive GET, 1 positive POST, 2 conservative
negatives on POST, 1 positive GET /slow), each with its expected status, and
zero HTTP requests sent. Against `tests/fixtures/openapi-auth` (`GET
/secure`, `security: [bearerAuth]`) with no `--bearer-token-env`: the one
generated test is `SKIPPED` with reason "authentication required (scheme(s):
bearerAuth) but no matching credentials were supplied"; with a correct
`--bearer-token-env`, it `PASSED`; with an incorrect one, it `FAILED` (the
server correctly returned 401, which didn't match the expected 200 — an
assertion failure, not an execution error).

### Tests executed

```
python -m pytest -q
```

**Result: 160 passed, 0 failed** (102 from Phase 1+2 minus one test that was
restructured for Phase 3's real `test` command, plus 59 new). New coverage:
OpenAPI parsing (`$ref` resolution, multi-spec ambiguity + explicit
selection, invalid/Swagger-2.0 rejection), request-data generation (every
branch: string/format defaults, integer/array/object construction,
`allOf` merging, `oneOf`/unconfident cases), auth resolution (env-var
reading + warning-on-unset, all four scheme types), dry-run (proves
`make_executor` is never called), and — against the fully offline stdlib
`http.server`-based fixture in `tests/adapters/rest/fixture_server.py` (no
external network access anywhere) — real GET/POST success, negative-test
validation, auth pass/fail/skip, schema-validation pass/fail, connection
refusal, timeout, and the `--target`-overrides-`servers` guarantee. Plus 6
new CLI-level tests (`tests/cli/test_cli_test_command.py`) and 4 new
`jsonschema`-upgrade tests in `tests/core/test_assertions.py`.

Manually verified end-to-end via a throwaway local server: `universal-test
test <path> --dry-run`, `universal-test test <path>` (no target — correct
error + exit code 2), and `universal-test test <path> --target
http://127.0.0.1:<port>` (real execution, correct PASS/SKIPPED
classification, valid `--format json` output).

### Known limitations

- Only OpenAPI 3.x is supported (Swagger 2.0 rejected, not converted).
- External `$ref`s are never resolved (left as-is with a warning) —
  deliberate safety choice, not a parsing gap to "fix" later without
  re-considering the safety tradeoff.
- `security` requirement semantics are OR-only across scheme names (no
  AND-within-one-requirement-object modeling).
- No unified `report.json/.md/.html` — `scan` and `test` each still have
  their own lightweight serializers; Phase 5 introduces the real report
  generator covering both (and eventually assessment/regression) in one
  shape.
- Single global timeout per `test` run (no per-request override).
- `AdapterInfo`/`RestAdapter`'s generic contract class is REST-specific for
  now (not yet factored into a shared location) since it's still the only
  adapter — intentional, per the project's "don't build abstractions before
  a second consumer exists" rule (documented in ARCHITECTURE.md §10.11).

### Next phase

Phase 4 — Performance (concurrency engine, latency measurement, percentiles,
threshold evaluation, baseline comparison). **Per `skill.md` §32 / the
Phase 3 brief's stop condition, do not start Phase 4 (or SQL execution,
browser automation, the regression engine, AI integration, security
exploitation) without an explicit go-ahead.**

---

## Phase 4 — Performance Testing — ✅ Done (2026-08-09)

### Files changed

New `src/universal_test/testing/performance/` package (technology-independent,
no `httpx` import): `models.py` (`LoadProfile`, `PerformanceRequest`,
`PerformanceSample`, `LatencyStats`, `PerformanceMetrics`,
`PerformanceThresholdResult`, `LevelResult`, `PerformanceResult`),
`percentiles.py` (nearest-rank percentile algorithm), `metrics.py`
(sample aggregation), `thresholds.py` (independent threshold evaluation),
`planner.py` (`build_load_profile()` with hard safety ceilings),
`runner.py` (`PerformanceRunner`, `ThreadPoolExecutor`-based), `serializers.py`
(plan/result text/JSON/Markdown).

New under `src/universal_test/adapters/rest/`: `performance_executor.py`
(httpx-based `PerformanceExecutor`), `performance.py` (endpoint selection +
request building, `resolve_performance_target`/`resolve_auth_headers`),
`url_utils.py` (extracted `substitute_path_params`, now shared by
`executor.py` and `performance_executor.py`).

Modified: `src/universal_test/adapters/rest/test_generation.py`
(`_build_positive_request` renamed to public `build_positive_request` for
reuse); `src/universal_test/discovery/api.py` (`_OPENAPI_NAME_HINTS`
exported as `OPENAPI_NAME_HINTS`, reused by `discovery_bridge.py`, no
behavior change); `src/universal_test/cli/main.py` (`performance` command
fully wired: `_add_auth_args` factored out and shared with `test`, new
`_add_performance_args`, `_run_performance`, `_parse_concurrency_arg`).
No `pyproject.toml` changes — zero new dependencies.

New tests: `tests/testing/performance/` (`test_percentiles.py`,
`test_metrics.py`, `test_thresholds.py`, `test_runner.py`,
`test_planner.py`), `tests/adapters/rest/test_performance_execution.py`,
`tests/cli/test_cli_performance_command.py`. Extended
`tests/adapters/rest/fixture_server.py` with `/fast`, `/error`, `/unstable`
routes + `reset_unstable_counter()`. Modified `tests/cli/test_cli.py` (2
Phase 1 stub-era tests replaced with tests matching `performance`'s real,
now-implemented behavior).

### Functionality added

- **Load profiles**: `baseline` (forces concurrency=1), `load` (default
  `[1, 10]`), `stress` (auto-generated step sequence up to
  `--max-concurrency`, stops on a configurable error-rate/P95 condition —
  defaulting to `error_rate_percent > 50%` if the user gave none — so a
  stress run always terminates for two independent reasons even with zero
  extra flags), `custom` (explicit `--concurrency` required, never
  defaulted). Verified: `test_stress_profile_stops_on_error_rate`,
  `test_stress_defaults_a_stop_condition_when_none_given`.
- **Request source reuse**: `resolve_performance_target()` prefers the
  project's OpenAPI spec and Phase 3's own `build_positive_request()` (now
  public) for the request body — never regenerates a different request per
  call, so results are comparable across concurrency levels (verified:
  `test_endpoint_resolution_reuses_phase3_request_generation`). Falls back
  to explicit `--endpoint`/`--method` only when no spec is discoverable;
  never scans for an unknown API. Multi-endpoint/multi-spec ambiguity still
  refuses to guess (reuses Phase 3's `MultipleSpecsFoundError`).
- **Bounded concurrency**: `ThreadPoolExecutor(max_workers=concurrency)` —
  verified with a real in-flight-request tracker that the configured max is
  never exceeded (`test_bounded_concurrency_never_exceeds_configured_max`).
  Two execution modes (fixed request count, fixed duration) both bounded.
  Cooperative cancellation via `threading.Event`, verified to stop before a
  later concurrency level starts (`test_cancellation_stops_before_later_levels`)
  and to actually shorten wall-clock run time, not just flip a flag.
- **Percentiles**: documented nearest-rank algorithm (not an unexplained
  one-liner), with explicit tests for 0/1/2 samples, identical values,
  small and 1000-sample datasets.
- **Metrics**: total/successful/failed counts, error rate, RPS defined
  against wall-clock duration (not summed per-request time — verified:
  `test_aggregate_rps_uses_wall_clock_not_sum_of_durations`), zero-sample
  case never fabricates a result (`latency=None`, `rps=0.0`, no
  divide-by-zero).
- **Error classification**: `HTTP_ERROR`/`TIMEOUT`/`NETWORK_ERROR`/
  `TARGET_ERROR` distinguished from each other and from success; the
  executor's contract requires it to never raise so every attempted
  request — success or failure — reaches aggregation
  (`test_failed_requests_are_captured_not_raised` and siblings for
  network-error/timeout).
- **Threshold evaluation**: independent, unit-tested component (not
  hardcoded in the runner), reusing `core.models.enums.AssessmentStatus`;
  `p50/p90/p95/p99_ms`, `error_rate_percent`, `min_rps`; `NOT_ASSESSED` on
  zero samples rather than a fabricated pass; unrecognized keys warned, not
  silently dropped. Wired to `universal-test.yaml`'s existing
  `performance.thresholds` section (defined since Phase 1, unused until
  now) — verified end-to-end via a real config file.
- **CLI safety**: `--target` required unconditionally, **including
  `--dry-run`** (deliberately stricter than `test`); every numeric knob
  passes through `planner.py`'s hard ceilings regardless of what the CLI
  itself validates; non-`--dry-run`/non-`--yes` runs print the plan +
  estimated request count and require `y`/`yes` confirmation; a
  non-interactive session without `--yes` is refused rather than hanging.
  No "looks like production" URL heuristic — the brief is explicit the tool
  can't reliably know this, so the safeguard is the plan + confirmation,
  not a guess.
- **Secret redaction**: verified end-to-end that a bearer token supplied via
  `--bearer-token-env` never appears in `text`/`json` CLI output
  (`test_bearer_token_never_appears_in_performance_output`), consistent
  with Phase 3's guarantee for functional testing.

### Bug found and fixed during implementation

`time.monotonic()` has ~15.6ms resolution on this Windows Python build
(`GetTickCount`-backed), which silently produced `duration_seconds=0.0`
(and therefore `rps=0.0`) for any concurrency level that completed within
one tick — reproduced with a two-level `[1, 5]` run against a fast local
server where the second level's numbers were exactly zero. Fixed by
switching every interval-timing call in `testing/performance/runner.py` and
`adapters/rest/performance_executor.py` to `time.perf_counter()` (the
stdlib-recommended high-resolution timer for measuring short durations).
Manually re-verified after the fix; also why the test suite includes
multi-level runs and real (if fast) local-server integration tests rather
than only synthetic zero-latency fakes, which wouldn't have caught this.
Documented as a house rule in ARCHITECTURE.md §11.12: default to
`perf_counter()` for interval timing in this project going forward.

### Tests executed

```
python -m pytest -q
```

**Result: 234 passed, 0 failed** (160 from Phases 1-3 + 74 new). New
coverage: percentiles (edge cases: 0/1/2 samples, identical values, large
datasets), metrics aggregation (zero samples, mixed error types, wall-clock
RPS), threshold evaluation (all pass, one/multiple failures, boundary
equality, NOT_ASSESSED, unrecognized-key warnings), the runner (concurrency
1 and >1, measured bounded-concurrency, duration-mode timing, every error
type captured not raised, cancellation, stress stop conditions, run
timeout), the planner (every safety ceiling, every profile default), REST
performance execution against a real local server (fast/error/unstable/slow
endpoints, a genuine connection refusal via bind-then-close, threshold
evaluation against real traffic, auth headers applied), and CLI-level
coverage (missing target incl. dry-run, invalid concurrency/duration
/requests, custom-without-concurrency, `--yes` skipping the prompt, secret
redaction).

Manually verified end-to-end via a throwaway local server: `performance
--dry-run` (plan shown, nothing sent), `performance` with no `--target`
(refused, exit 2, even with `--dry-run`), `performance --profile stress
--dry-run` (auto-generated steps + default stop condition shown), and a
real execution with `--concurrency 1,5 --requests 20 --yes --format json`
(correct per-level RPS/percentiles after the timing fix above) plus a
`universal-test.yaml`-supplied threshold flowing into the printed plan.

### Known limitations

- No regression/baseline-comparison engine — explicitly excluded from this
  phase by its own brief (§20); threshold evaluation is per-run only, not
  compared across runs or versions.
- CLI `Ctrl+C` doesn't yet cancel a running performance test gracefully;
  the cancellation API exists and is tested for programmatic callers, but
  isn't wired to `SIGINT` in the CLI.
- One global per-request timeout per run (same limitation as Phase 3).
- OpenAPI `security` OR-only flattening (inherited from Phase 3).
- No unified `report.json/.md/.html` — `performance` has its own
  lightweight serializers like `scan`/`test`, pending Phase 5.

### Next phase

Per the Phase 4 brief's stop condition, **do not start** the regression
engine, historical baseline comparison, CI/CD integration, the SQL adapter,
the browser adapter, AI integration, security scanning, the blockchain
adapter, or distributed load testing without an explicit go-ahead. The
natural next candidates once approved: Phase 5 (unified JSON/Markdown/HTML
report generator, tying discovery + functional + performance results
together) or the regression engine explicitly deferred from this phase.

---

## Phase 5 — Unified Assessment & Reporting — ✅ Done (2026-08-09)

### Files changed

New `src/universal_test/assessment/` package: `models.py`
(`AssessmentFinding`, `AssessmentCategory`, `CoverageItem`,
`UnassessedArea`, `ProjectAssessment`, `SCHEMA_VERSION = "1.0"`), `rules.py`
(`compute_overall_status()`, `execution_health_status()`),
`discovery_assessment.py` (Project Discovery / Build Health / Test
Infrastructure), `functional_assessment.py`, `performance_assessment.py`,
`testability_assessment.py`, `configuration_assessment.py`, `engine.py`
(`build_assessment()` orchestration + coverage/unassessed computation +
fixed `LIMITATIONS` text).

New `src/universal_test/reporting/` package: `report_bundle.py`
(`AssessReportBundle`), `json_report.py`, `markdown_report.py`,
`html_report.py`.

Modified: `src/universal_test/cli/main.py` (`assess` command fully wired:
`_add_assess_args` reusing `_add_performance_args` plus a new
`--performance` opt-in switch, `--format` default overridden to `all`,
`_run_assess`/`_maybe_run_assess_performance` orchestration); `pyproject.toml`
(+`norecursedirs = ["fixtures", ...]` — fixes a pytest test-collection
clash unrelated to Phase 5 logic, surfaced by adding a second fixture
project with a `tests/test_main.py`; no dependency changes).

New tests: `tests/assessment/` (`test_rules.py`, `test_discovery_assessment.py`,
`test_configuration_assessment.py`, `test_testability_assessment.py`,
`test_functional_assessment.py`, `test_performance_assessment.py`,
`test_engine.py`), `tests/reporting/test_report_renderers.py`,
`tests/cli/test_cli_assess_command.py`. Modified `tests/cli/test_cli.py`
(removed "assess" from the generic stub-command parametrize list, added a
real-behavior test for the no-`--output` default-to-`reports/` path).
New fixtures: `tests/fixtures/{healthy-project,failed-functional-project,
slow-project,unknown-project,partial-project}/`.

### Functionality added

- **Unified `ProjectAssessment` model**: reuses `AssessmentStatus`
  (`PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED`) and `Severity` from Phase 1
  rather than inventing new enums; status and severity kept strictly
  separate on every finding.
- **Deterministic overall-status rule** (`assessment/rules.py`):
  `FAIL > WARNING > UNKNOWN > PASS`, `NOT_ASSESSED` categories excluded
  from the vote, all-`NOT_ASSESSED` resolves to `UNKNOWN` rather than a
  silent `PASS`. No magic numbers, no weighting — exhaustively unit-tested
  (every pairwise status combination, not just headline cases).
- **Seven category assessors**: Project Discovery, Build / Project Health,
  Testability, Functional Health, Performance, Configuration Hygiene, Test
  Infrastructure — each a pure function over already-computed Phase 2-4
  results. Testability and Configuration Hygiene are structurally capped
  below `FAIL` (poor testability is a limitation, not a defect; a secret
  *pattern* match is not a confirmed vulnerability) — verified by
  `test_testability_never_reaches_fail` and
  `test_secret_pattern_is_warning_never_fail`.
- **Shared execution-health ladder** (`execution_health_status()`): used by
  both Functional Health and Performance — `UNKNOWN` (nothing attempted) →
  `FAIL` (100% transport failure — target unreachable) → `WARNING` (partial
  failure) → `PASS`. Verified with a **real** connection failure (a
  bind-then-close probe socket, not a mock) reaching `FAIL`, and a real
  mismatched-response fixture (`failed-functional-project`, expects 200,
  server returns 500) reaching `WARNING` via an actual assertion mismatch,
  not a simulated one.
- **Performance threshold breaches cap at `WARNING`**, matching the Phase 5
  brief's own worked example (P95 FAIL + error-rate PASS → "Overall:
  WARNING") — verified end-to-end against the `slow-project` fixture with a
  deliberately tight `p95_ms` threshold from a real `universal-test.yaml`.
- **Coverage**: five fixed items (Discovery, API Discovery, Functional
  Execution, Performance Execution, Database), each with a `reason` when
  below 100% — no invented per-detector percentages.
- **Unknown / Not Assessed**: always includes "Business logic correctness"
  (no formal spec exists to check against, ever) plus whichever of
  database/auth/functional/performance prerequisites were actually missing
  that run — a first-class report section, never merged into a passing
  result.
- **Functional/performance generation is always attempted**, execution only
  with `--target` (functional) or `--target` + `--performance` +
  confirmation (performance) — every way generation/execution can be
  withheld (no spec found, multiple specs ambiguous, no target, `--dry-run`,
  confirmation declined) becomes a specific reason string surfaced in the
  report rather than a crash or a silently empty category.
- **`--performance` is opt-in and never hidden in defaults**: `assess
  ./project` alone sends zero network traffic (verified:
  `test_default_run_sends_no_network_traffic_and_succeeds`); `--performance`
  reuses the *exact* same safety gate as the standalone `performance`
  command (interactive confirmation / `--yes`, every planner safety
  ceiling) — not a relaxed version.
- **Reports**: JSON (schema-versioned, `discovery`/`functional`
  /`performance` as full raw sections plus the `assessment` rollup),
  Markdown (brief's exact 12-section order), HTML (offline, no CDN/external
  JS, every scanned-project-derived string `html.escape()`d — verified with
  a `<script>` tag embedded in a fixture's file path). No `Jinja2`
  dependency added. Deterministic: same input renders byte-identical output
  twice (`generated_at` aside).
- **CLI**: `assess` defaults `--format` to `all`, and defaults `--output` to
  `./reports/` (the directory reserved but unused since Phase 1) when
  producing all three formats with no explicit `--output`.

### Tests executed

```
python -m pytest -q
```

**Result: 317 passed, 0 failed** (234 from Phases 1-4 + 83 new). New
coverage: the overall-status rule (16 parametrized cases plus dedicated
"NOT_ASSESSED never forces PASS/FAIL alone" and "single FAIL among many
PASSes still fails" checks) and `execution_health_status()`'s four-way
ladder; all seven category assessors independently (discovery-derived ones
against real fixture projects, functional/performance ones against
hand-built `RunResult`/`PerformanceResult` objects); `build_assessment()`
end-to-end against the five new fixtures; JSON/Markdown/HTML renderers
(schema version, required sections, offline-safety, HTML-escaping,
determinism, secret redaction); and full CLI integration against the
existing offline fixture server — default-safe (no traffic), default
format (three files), single-format (one file), healthy vs. failed
functional execution, a genuine unreachable-target `FAIL`, performance
staying `NOT_ASSESSED` without the flag, a real threshold breach via
`--performance --yes` with a config-file threshold, an unknown project
leaving both execution categories `NOT_ASSESSED`, `--dry-run` never
executing even with a target, bearer-token redaction across all three
output formats, and multi-spec ambiguity degrading gracefully rather than
crashing the whole command.

Also fixed, in the course of writing Phase 5's fixtures: a latent pytest
test-collection bug where two fixture projects both shipping a
`tests/test_main.py` caused an import-file-mismatch collection error
(`pyproject.toml`'s new `norecursedirs` excludes `tests/fixtures/**`
entirely, since those files are fixture content, not this project's own
tests) — and a stale Phase 1-era CLI test (`tests/cli/test_cli.py`) that
still treated `assess` as an unimplemented stub, which was silently writing
real report files into the repo's own `reports/` directory every time the
suite ran; replaced with a test that asserts the real default-output-path
behavior against a monkeypatched working directory.

Manually verified end-to-end via a throwaway local server: `assess`
with no flags (zero traffic, `NOT_ASSESSED` functional/performance),
`assess --target <url>` (real functional execution, correct PASS/WARNING),
`assess --target <url> --performance --yes` (real performance execution,
threshold evaluation), and inspected the resulting `report.json`/`.md`
/`.html` by hand for correctness and redaction.

### Known limitations

- No regression/baseline-comparison engine, no historical trend, no CI
  quality gate — explicitly out of scope for this phase per its own brief
  (§25).
- No numeric quality score, by design (brief §5) — some users may want one
  eventually; that would need empirical validation first, per skill.md §12.
- Coverage stays at five fixed, mostly-binary items rather than a
  finer-grained breakdown, to avoid implying precision the evidence doesn't
  support.
- `report`/`run` remain routing stubs; `report`'s intended functionality is
  already covered by `assess`.
- Recommendations are deterministic template strings keyed by finding type,
  generated inline at finding-construction time rather than through a
  separate lookup-table module — intentional (no second source of truth to
  keep in sync), but means adding a new finding type means writing its
  recommendation text at the same call site, not in one central registry.

### Next phase

Per the Phase 5 brief's stop condition, **do not start** the regression
engine, historical baseline comparison, CI/CD integration, the SQL adapter,
the browser adapter, AI integration, a security scanner, the blockchain
adapter, or distributed testing without an explicit go-ahead.

---

## Phase 6 — Read-Only SQL Database Adapter — ✅ Done (2026-08-09)

### Files changed

New `src/universal_test/adapters/database/` package: `models.py`
(`DatabaseEngine`, `DatabaseColumn`, `PrimaryKey`, `ForeignKey`,
`DatabaseIndex`, `RowCountEstimate`, `DatabaseTable`, `DatabaseView`,
`DatabaseSchema`, `DatabaseInfo` — normalized, engine-independent, all
`to_dict()`), `base.py` (`DatabaseDriver` ABC — the entire adapter surface,
deliberately with no `execute(sql)` method — plus `discover_database()`,
the generic metadata-walking orchestration shared by every engine),
`profile.py` (`DatabaseProfile`/`DatabaseCredentials`,
`load_database_profile()` — YAML parsing with the mandatory
`readonly: true` refusal and env-var-only credential resolution),
`sqlite.py`/`postgresql.py`/`mysql.py`/`sqlserver.py` (one driver per
engine, each implementing `DatabaseDriver` with fixed, read-only,
parameterized metadata queries; the three server drivers import their
optional dependency lazily inside `__init__` so a missing driver never
breaks anything outside this module), `adapter.py` (`discover()` —
profile -> driver -> `DatabaseDiscoveryResult`, catching every connection/
timeout/driver/metadata failure into a `not_assessed_reason` rather than
raising), `serializers.py` (dry-run plan + result text/JSON/Markdown, same
convention as every other phase's lightweight serializers).

New `src/universal_test/assessment/database_assessment.py`
(`assess_database_health()` — an eighth assessment category, structurally
capped so a schema observation like "zero foreign keys" or a connection
failure never reaches `FAIL`; `database_testability_signal()` feeding
Phase 5's existing testability row).

Modified: `src/universal_test/core/errors.py` (+`DatabaseError(AdapterError)`
-> `DatabaseDriverUnavailableError`/`DatabaseConnectionError`
/`DatabaseTimeoutError`, additive only); `src/universal_test/assessment/engine.py`
(`build_assessment()` gained a `database_result` parameter, an eighth
category in the rollup, a real "Database" coverage percentage instead of
the fixed 0% placeholder, and a "Database integration" unassessed-area
entry when no profile was given); `src/universal_test/assessment/testability_assessment.py`
(database-testability row now sourced from `database_assessment
.database_testability_signal()` instead of a coarse discovery-only guess);
`src/universal_test/reporting/report_bundle.py` (`AssessReportBundle`
gained `database_result`); `src/universal_test/reporting/{json,markdown,html}_report.py`
(new `database` JSON key / "Database Health" Markdown+HTML section, schema/
table/view breakdown when connected); `src/universal_test/cli/main.py`
(new `database` subcommand fully wired: `--database-profile/--dry-run
/--format/--output`; `assess` gained an opt-in `--database-profile` flag
using the exact same "omit it, zero connections are made" pattern as
`--performance`); `pyproject.toml` (+`[project.optional-dependencies]
.database` group: `psycopg2-binary`, `mysql-connector-python`, `pyodbc` —
none a hard dependency; a code comment documents the "Core must work with
zero of these installed" rule directly next to the declaration).

New tests: `tests/adapters/database/` (`test_profile.py`, `test_sqlite_driver.py`,
`test_driver_unavailable.py`, `test_adapter.py`, `conftest.py`),
`tests/assessment/test_database_assessment.py`,
`tests/cli/test_cli_database_command.py`. New fixtures:
`tests/fixtures/database/{sqlite-basic,sqlite-relations}/app.db` (real
SQLite files — `sqlite-relations` has a foreign key, two indexes including
a unique one, a view, and a table with no primary key, specifically to
exercise the "informational, not a defect" assessment rules).

### Functionality added

- **`DatabaseDriver` has no arbitrary-SQL-execution method** — the Phase 6
  brief's primary safety requirement (§7/§19) implemented as a structural
  absence, not a keyword blocklist: `list_tables/list_views/list_columns
  /get_primary_key/list_foreign_keys/list_indexes/get_safe_row_count` is
  the entire contract every engine driver implements.
- **Explicit-connection-only, safe-by-default profile**: discovering
  "PostgreSQL detected" during `scan` never implies permission to connect;
  only `--database-profile <path>` does, and the profile's `readonly` field
  must be the literal `true` — anything else (including an absent key)
  refuses to connect rather than assuming safety (verified:
  `test_readonly_not_true_refuses_to_load`/similar in
  `tests/adapters/database/test_profile.py`). Credentials are read only
  from named environment variables, never the profile file itself.
- **Four engines**: SQL Server (`pyodbc`, `sys.*` catalog views),
  PostgreSQL (`information_schema`/`pg_catalog`, system schemas excluded
  from application-table scope), MySQL (`information_schema`), SQLite
  (stdlib `sqlite3`, opened via a read-only URI so the connection itself
  cannot write — verified with a real write attempt raising
  `sqlite3.OperationalError` in `test_readonly_connection_rejects_writes`).
  All three server drivers are optional, adapter-local dependencies
  (`pip install universal-test[database]`); a missing driver resolves to
  `NOT_ASSESSED` with reason "Database driver is not installed," verified
  end-to-end for all three engines plus a check that a missing driver never
  triggers an automatic `pip`/`subprocess` install attempt.
- **Normalized model**: `DatabaseInfo` and friends — the assessment/
  reporting layers never see a raw `pyodbc`/`psycopg2`/`mysql.connector`
  /`sqlite3` cursor or row object.
- **Safe row counts**: prefers each engine's catalog/metadata-based
  estimate (SQL Server `sys.dm_db_partition_stats`, PostgreSQL
  `pg_stat_user_tables`, MySQL `information_schema.tables.table_rows`,
  SQLite `sqlite_stat1`) over `SELECT COUNT(*)`; `value=None` when no safe
  estimate is available — never fabricated, never an expensive full scan of
  an unfamiliar large table (verified against the real `sqlite-relations`
  fixture: `test_row_count_uses_catalog_estimate_after_analyze`).
- **Never a defect verdict from a schema observation**: zero foreign keys,
  a missing primary key, or a partially-discoverable schema are `INFO`/
  `WARNING`-severity findings under a category status that never reaches
  `FAIL`; a connection failure/timeout/missing driver is `NOT_ASSESSED`,
  also never `FAIL` — an access/environment problem is not evidence the
  assessed project's database is broken (both invariants directly tested in
  `tests/assessment/test_database_assessment.py`).
- **Timeouts**: `connect_timeout_seconds`/`query_timeout_seconds`
  (default 10s each, configurable in the profile) applied via each engine's
  own native timeout mechanism.
- **CLI**: `universal-test database <path> --database-profile <path.yaml>
  [--dry-run] [--format text|json|markdown] [--output PATH]`. Missing
  `--database-profile` refuses outright (exit 2) without attempting a
  connection. `--dry-run` prints the plan (engine, host/path, the fixed
  read-only operation list, "Mode: READ ONLY") and never constructs a
  driver — verified via a driver-construction spy
  (`test_dry_run_never_connects`).
- **`assess` integration**: new opt-in `--database-profile` flag; omitted,
  `Database Health` is `NOT_ASSESSED` with reason "database
  credentials/access were not explicitly configured" and zero database
  connections are attempted — matching `assess`'s existing zero-traffic-
  by-default guarantee for functional/performance testing (verified:
  extends `test_default_run_sends_no_network_traffic_and_succeeds`'s
  coverage to include the database category).
- **Reports**: `report.json` gains a `database` key (`null` when not
  assessed); `report.md`/`report.html` gain a "Database Health" section
  with the same schema/table breakdown the standalone `database` command
  shows. No credential ever reaches any renderer — structurally impossible,
  since `DatabaseProfile.to_dict()` never has a username/password field to
  serialize in the first place.

### Tests executed

```
python -m pytest -q
```

**Result: 370 passed, 0 failed** (317 from Phases 1-5 + 53 new). New
coverage: `DatabaseProfile` loading (every refusal path: non-`true`
readonly, missing engine/host/database/path, invalid YAML, malformed
credentials section, env-var credential resolution, `to_dict()` never
exposing a credential value), real read-only SQLite discovery against two
fixture databases (`sqlite-basic`: a plain table with a primary key;
`sqlite-relations`: a foreign key, unique and non-unique indexes, a view, a
table with no primary key, and `ANALYZE`-based row-count estimation),
write-rejection on the read-only connection, absence of any
`execute`/`execute_sql`/`query` method on the driver, graceful one-table-
failure survival during a scan, missing-driver handling for all three
server engines (including proof that nothing auto-installs), `discover()`'s
full success/failure/timeout/unsupported-engine matrix, the "Database
Health" assessment category's every status path (not assessed / connection
failed / connected-with-warnings / zero-FK-is-info / no-PK-is-info), and
CLI coverage for `database` (missing profile, dry-run never connecting,
invalid profile file, missing credentials, redacted output across all
three formats).

Manually verified end-to-end: `universal-test database
tests/fixtures/database/sqlite-relations --database-profile <profile.yaml
pointing at app.db, readonly: true>` produces the correct schema/table/FK
/index/row-count breakdown; the same command with `--dry-run` prints the
plan and touches no file handle; omitting `--database-profile` from both
`database` and `assess` refuses/reports `NOT_ASSESSED` without any
connection attempt; a profile with `readonly` omitted or set to `false` is
rejected at load time with a clear `ConfigurationError`.

### Known limitations

- Only SQLite has live-database integration tests in the automated suite;
  SQL Server/PostgreSQL/MySQL are covered by missing-driver-handling tests
  and code review against the same `DatabaseDriver` contract, not a live
  server — per the Phase 6 brief §20's explicit instruction not to make the
  general test suite depend on Docker/an external database service.
- No schema diff / migration validation / baseline comparison — explicitly
  out of scope for this phase (brief §25), deferred alongside the
  regression engine already deferred from Phase 4.
- No arbitrary SQL execution capability exists at all, by design — this is
  a permanent property of the adapter, not a temporary limitation to lift
  later.
- Row-count estimates depend on each engine's own statistics being
  reasonably current (e.g. SQLite needs `ANALYZE` to have been run for
  `sqlite_stat1` to exist); when no estimate is available, `value=None`
  rather than a guessed or expensive exact count.
- Driver dependencies are grouped into one `[database]` extra covering all
  three server engines together, rather than one extra per engine.

### Next phase

Per the Phase 6 brief's stop condition, **do not start** the regression
engine, historical baseline comparison, CI/CD integration, the browser
adapter, AI integration, a security scanner, the blockchain adapter, or
distributed testing without an explicit go-ahead.

---

## Phase 7 — Regression / Baseline Comparison Engine — ✅ Done (2026-08-09)

### Files changed

New `src/universal_test/regression/` package: `models.py`
(`ChangeType`, `MetricDelta`, `RegressionFinding`, `RegressionCategory`,
`RegressionSummary`, and the `BaselineSnapshot` family —
`SourceInfo`/`DiscoverySnapshot`/`FunctionalSnapshot`/`FunctionalTestEntry`
/`PerformanceSnapshot`/`PerformanceLevelSnapshot`/`DatabaseSnapshot`
/`DatabaseTableSnapshot`/`AssessmentSnapshot`/`AssessmentCategorySnapshot`,
all with `to_dict()`/`from_dict()`), `snapshot.py` (`build_snapshot()` —
compacts already-computed Phase 2-6 results into a `BaselineSnapshot`),
`baseline_store.py` (`save_baseline()`/`load_baseline()` — schema-version
compatibility check, immutability), `rules.py`
(`status_from_findings()` — the one severity-to-status rule every
comparator uses), `functional_compare.py`, `performance_compare.py`,
`database_compare.py`, `discovery_compare.py`, `assessment_compare.py`
(the five category comparators), `engine.py` (`compare()` orchestration,
reusing `assessment/rules.py::compute_overall_status()` unmodified for the
overall rollup), `serializers.py` (standalone `baseline compare`
text/json/markdown).

Modified: `src/universal_test/core/errors.py` (+`RegressionError`,
additive only); `src/universal_test/core/configuration/config.py`
(+`RegressionConfig` with a `performance: dict[str, float]` field carrying
safe non-zero defaults, registered in `Config`/`_SECTION_TYPES`; also
fixed `_build_section()` — see "Bug found and fixed" below);
`src/universal_test/reporting/report_bundle.py` (`AssessReportBundle`
gained `regression: RegressionSummary | None`);
`src/universal_test/reporting/{json,markdown,html}_report.py` (new
`regression` JSON key / "Regression" Markdown+HTML section);
`src/universal_test/cli/main.py` (new `baseline save`/`baseline compare`
subcommands; `assess` gained an opt-in `--baseline <path>` flag; the
discovery+functional+performance+database pipeline previously inlined in
`_run_assess()` was factored out into `_run_pipeline()`, and
`_add_assess_args()`'s flag-adding logic into `_add_pipeline_args()`, both
now shared by `assess`/`baseline save`/`baseline compare` rather than
duplicated).

New tests: `tests/regression/` (`test_functional_compare.py`,
`test_performance_compare.py`, `test_database_compare.py`,
`test_discovery_compare.py`, `test_assessment_compare.py`,
`test_engine.py`, `test_baseline_store.py`, `test_models.py`,
`test_snapshot.py`), `tests/cli/test_cli_baseline_command.py`. Extended
`tests/core/test_config.py` with 3 new `RegressionConfig` cases. New
fixture: `tests/fixtures/regression-project/` (a single `GET /unstable`
endpoint, used to produce a real, deterministic PASS-then-FAIL transition
against the existing offline fixture server's `/unstable` route).

### Functionality added

- **`BaselineSnapshot` stores structured evidence, not a status string**
  (brief §2): tool/schema version, project path, git commit/branch/dirty
  (captured but never the sole comparison identity — brief §2's explicit
  warning), and compact discovery/functional/performance/database/
  assessment summaries. `build_snapshot()` builds one from the *same*
  `ProjectModel`/`RunResult`/`PerformanceResult`/`DatabaseDiscoveryResult`
  /`ProjectAssessment` objects `build_assessment()` already produced —
  never re-discovers, re-executes, or re-queries anything.
- **Immutable baseline, read-only compare** (brief §4): `save_baseline()`
  is the only function that ever writes a baseline file, always to the
  caller's explicit `--output` path (no hidden default location — brief
  §3); `load_baseline()` only ever reads. Verified: a baseline file's bytes
  and mtime are provably unchanged after `baseline compare` runs against it
  (`test_compare_is_read_only_never_modifies_the_baseline_file`,
  `test_load_never_writes_back_to_the_file`).
- **Schema-version compatibility is strict, tool-version is not** (brief
  §18): an unrecognized `schema_version` raises `RegressionError`
  immediately (`universal-test.baseline` files are never partially parsed);
  a tool-version mismatch is recorded as a `warnings` entry with both
  versions shown, not an error.
- **Functional regression compares by test ID** (brief §7, called out as
  the most important requirement): `PASSED -> FAILED/ERROR` is a `HIGH`
  finding; `PASSED -> SKIPPED/UNKNOWN` is a `MEDIUM` "changed" finding; an
  unchanged status (including an unchanged *failure* — brief §6's own
  worked example) produces no new finding; `ADDED`/`REMOVED` test IDs never
  themselves become a regression finding (brief §7: "不要直接判定 removed test
  為 regression"). Aggregate per-status count deltas are recorded
  alongside the per-test findings, not instead of them.
- **Performance regression respects metric direction and configurable
  tolerance** (brief §8/§9/§10): latency (P50/P90/P95/P99) and error rate
  are `lower_is_better`; RPS is `higher_is_better`; every tolerance comes
  from a `thresholds: dict[str, float]` parameter — the comparator itself
  has no hard-coded percentage. `RegressionConfig.performance` supplies
  safe non-zero defaults (10% for latency/RPS, 1 percentage point absolute
  for error rate) so ordinary measurement noise (P95 200ms -> 202ms) is
  never flagged without configuration. Levels are matched by concurrency;
  a zero baseline value for a percent-based metric is `NOT_COMPARABLE`
  rather than a divide-by-zero or a false regression (brief §21's "zero
  baseline value"/"zero current value" test cases).
- **Database and discovery changes are always `Severity.INFO`** (brief
  §11/§12), which structurally caps both categories at `PASS` via the one
  shared `status_from_findings()` rule — a table/column/detected-technology
  appearing or disappearing is reported, never scored as a defect, unless a
  project later configures an explicit stricter "baseline policy" (brief's
  own words; not built this phase — nothing specifies its shape yet).
- **Assessment-category regression uses the brief's literal severities**
  (brief §13/§14): `PASS -> WARNING` = `MEDIUM`, `PASS -> FAIL` /
  `WARNING -> FAIL` = `HIGH`; any transition touching `UNKNOWN`/
  `NOT_ASSESSED` is skipped (missing data isn't a regression, brief §5) and
  an improving transition produces no finding.
- **No numeric quality score** (brief §15): `RegressionSummary.status` is
  `PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED`, the exact same vocabulary
  Phase 5 already established; the overall value is computed by *reusing*
  `assessment/rules.py::compute_overall_status()` directly, not a new rule.
- **CLI safety matches `assess`'s exactly, not a looser variant** (brief
  §17): `baseline save`/`baseline compare` share `assess`'s entire
  `--target`/`--performance`/`--database-profile` opt-in flag set and
  safety gates via one factored-out `_run_pipeline()`/`_add_pipeline_args()`
  pair — `baseline compare` without `--target` sends zero network traffic
  and reports `Functional: NOT_ASSESSED`, verified end-to-end.
- **Reports**: `report.json` gains a `regression` key (`null` without
  `--baseline`); `report.md`/`report.html` gain a "Regression" section
  (status, baseline/current metadata, one block per category with its
  findings) using the exact same rendering conventions every other section
  already uses.

### Bug found and fixed during implementation

Writing Phase 7's own `RegressionConfig` test surfaced a real, pre-existing
bug in `core/configuration/config.py::_build_section()`: it replaced a
dict-valued config field (`performance.thresholds`,
`regression.performance`) wholesale on any override, rather than merging
over the field's default. Since `regression.performance`'s default carries
six threshold keys (unlike `performance.thresholds`'s empty-dict default,
which made this invisible before now), overriding just one threshold in
`universal-test.yaml` (e.g. `p95_percent: 25`) would have silently dropped
the other five defaults — meaning every metric except the one explicitly
configured would stop being checked for regression at all. Fixed by merging
dict-valued fields over their dataclass defaults in `_build_section()`; the
existing `performance.thresholds` behavior is unaffected (merging into an
empty default dict is a no-op). Covered by
`test_regression_partial_threshold_override_keeps_other_defaults`
(`tests/core/test_config.py`).

### Tests executed

```
python -m pytest -q
```

**Result: 456 passed, 0 failed** (370 from Phases 1-6 + 86 new). New
coverage: every comparator in isolation against hand-built snapshot
dataclasses (functional: every status transition including an unchanged
failure and a mixed regression+improvement run; performance: below/at/
above tolerance, latency/throughput/error-rate regression, zero-baseline
and zero-current edge cases, an empty-thresholds-dict never flagging
anything; database/discovery: added/removed/changed always `INFO`, status
never leaves `PASS`; assessment: all three brief-specified severity
transitions plus indeterminate/improvement/mismatched-category
non-findings), the comparison engine (overall rollup reuse, tool-version-
mismatch warning), baseline storage (round-trip, missing file, invalid
JSON, non-baseline JSON, incompatible schema version, read-twice-never-
writes), full model round-trips, and `build_snapshot()` against a real
`discover()` result. CLI integration coverage: `baseline save` without
`--output` refused, a valid baseline file's shape, zero-network-traffic
default, `baseline compare` missing `--baseline` / nonexistent path /
incompatible schema version all refused, read-only-baseline verification,
zero-network-traffic without `--target`, a same-project no-op comparison
resolving to `PASS`, a **real** functional regression (a genuine
PASS-then-FAIL transition on the same test ID via the fixture server's
deterministic `/unstable` endpoint, not a mock), a **real** performance
regression (`/fast` vs. the fixture server's actual 300ms `/slow` delay), a
**real** database schema-change comparison (reusing Phase 6's
`sqlite-basic`/`sqlite-relations` fixture databases), `assess --baseline`
report integration (including graceful degradation on an invalid
`--baseline` path — logs an error, doesn't crash), and bearer-token
redaction across both `baseline save`'s output file and `baseline
compare`'s output.

Manually verified end-to-end via the offline fixture server: `baseline save
./project --output baseline.json` (real snapshot written), `baseline
compare ./project --baseline baseline.json` (real PASS comparison against
itself), and inspected the resulting `regression.json`/text output by hand
for correctness and redaction.

### Known limitations

- No "baseline policy" configuration to escalate database/discovery schema
  changes past `INFO` severity — the brief names this as a future concept
  without specifying its shape (§11), so nothing was speculatively built.
- No historical/multi-baseline trend tracking — one baseline compared
  against one current run at a time, matching the brief's own scope (§20
  explicitly excludes this).
- No CI/CD integration (exit-code gate wiring, GitHub/GitLab/Jenkins/Azure
  Pipelines annotations) — explicitly deferred to Phase 8 per the brief.
- No AI-assisted regression explanation — fully deterministic, matching
  every prior phase.
- Performance regression matches concurrency levels exactly (e.g. a
  baseline's `[1, 10]` vs. a current run's `[1, 5, 10]` only compares the
  `1` and `10` levels in common) — no interpolation between levels that
  don't match exactly.

### Next phase

Per the Phase 7 brief's stop condition, **do not start** CI/CD integration,
the browser adapter, AI integration, a security scanner, the blockchain
adapter, or distributed testing without an explicit go-ahead.

---

## Phase 8 — CI/CD Integration + Quality Gate — ✅ Done (2026-08-09)

### Files changed

New `src/universal_test/quality_gate/` package: `models.py`
(`QualityGateStatus`, `ExitCode`, `QualityGatePolicy`, `QualityGateRule`,
`QualityGateFinding`, `QualityGateResult`, `exit_code_for()`),
`signals.py` (`collect_rules()` — reads an already-built
`ProjectAssessment`/`RegressionSummary` into infra-vs-quality signal
lists, never re-discovers/re-executes/re-compares anything), `engine.py`
(`evaluate()` — the single policy-application function: classifies
signals against a `QualityGatePolicy`, applies the infra-error
short-circuit, returns a `QualityGateResult`), `serializers.py`
(text/JSON rendering for the `--ci` console summary), `ci_detection.py`
(`detect_ci_environment()` — informational only).

Modified: `src/universal_test/core/configuration/config.py` (+
`QualityGateConfig` with safe default `fail_on`/`warn_on` policy,
+`CiConfig`/`RetryConfig` for bounded CI retry, +`_validate_quality_gate_policy()`
raising a clear `ConfigurationError` on a malformed policy shape, both
registered in `Config`/`_SECTION_TYPES`); `src/universal_test/reporting
/report_bundle.py` (`AssessReportBundle` gained `quality_gate:
QualityGateResult | None`); `src/universal_test/reporting/{json,markdown,html}
_report.py` (new `quality_gate` JSON key / "Quality Gate" Markdown+HTML
section); `src/universal_test/cli/main.py` (`assess` gained `--ci`;
`_run_assess()` now evaluates the Quality Gate after building
`assessment`/`regression` and returns its `ExitCode`; `--baseline` load
failure changed from a silent degrade to `ExitCode.CONFIGURATION_ERROR`;
`_maybe_run_assess_performance()`'s interactive-confirmation check now
also treats `--ci` as forcing non-interactive behavior; `_run_pipeline()`
gained a bounded functional-execution retry on total transport wipeout
only, gated by the new `CiConfig`).

New `examples/ci/`: `github-actions/universal-test.yml`,
`gitlab/universal-test.yml`, `jenkins/Jenkinsfile` — each a documented
template (not a working pipeline), installing `universal-test` as a plain
`pip install`, running `assess --ci --yes --target ... --baseline ...`,
relying on the CLI's own exit code, and uploading `reports/`
unconditionally. `examples/README.md` updated to reference them.

New tests: `tests/quality_gate/` (`test_signals.py`, `test_engine.py`,
`test_ci_detection.py`, `test_serializers.py`, `test_ci_templates.py`),
`tests/cli/test_cli_quality_gate.py`. Extended `tests/core/test_config.py`
with 8 new Quality Gate / CI-retry config cases. Updated 4 pre-existing
tests whose exit-code assertions reflected pre-Phase-8 behavior (see "Two
deliberate exit-code behavior changes" below).

### Functionality added

- **Deterministic, configurable Quality Gate, no scattered `if` statements**
  (brief §1/§2): `quality_gate/engine.py::evaluate()` is the entire
  policy-application logic; `quality_gate/signals.py::collect_rules()`
  only collects what happened, kept deliberately separate so each half is
  independently testable. CI-provider-independent by construction — no
  GitHub/GitLab/Jenkins/Azure logic anywhere in Core or this package.
- **Safe default policy matching the brief exactly** (§3): `critical`/
  `high` regression, a real functional failure, and a performance
  threshold breach fail the build; `medium` regression, a database schema
  change, and a discovery change warn without blocking; `UNKNOWN`/
  `NOT_ASSESSED` never auto-fail (§9) unless a project explicitly opts a
  specific rule in (verified:
  `test_database_not_assessed_can_be_opted_into_failing`).
- **Stable `0/1/2/3` exit-code contract for `assess`** (brief §4): `0` =
  Quality Gate passed (a `WARNING` result still exits `0`), `1` = failed,
  `2` = configuration error, `3` = infrastructure/execution error.
- **A completely unreachable target is `3`, not `1`** (brief §18's most
  consequential rule): `Functional Health`/`Performance` reaching `FAIL`
  (Phase 5's existing "every request failed at the transport layer"
  definition) short-circuits the whole gate result to `ERROR`/exit-3,
  overriding whatever the ordinary findings would have computed — unless a
  project explicitly opts that exact signal into `fail_on`/`warn_on`, in
  which case it's treated as an ordinary quality finding instead (verified:
  `test_functional_unreachable_can_be_opted_into_quality_gate`).
- **`--ci`** (assess-only): forces non-interactive behavior even when
  `sys.stdin.isatty()` reports `True` (some CI runners attach a
  pseudo-tty — verified via a monkeypatched `isatty`), never itself
  authorizes traffic (`--yes` is still required separately, verified:
  `test_ci_flag_alone_does_not_authorize_traffic`), and prints a
  structured console summary instead of two terse lines.
- **CI environment detection is informational only** (brief §6): setting
  `CI`/`GITHUB_ACTIONS`/`GITLAB_CI`/`JENKINS_URL`/etc. only changes a log
  message, verified end-to-end (parametrized over all four brief-named
  variables) to never substitute for `--yes` or send unauthorized traffic.
- **Machine-readable + human-readable output together** (brief §10/§11):
  `report.json` gains a `quality_gate` key; `report.md`/`report.html` gain
  a "Quality Gate" section; none of it can carry a secret (verified with a
  *wrong* bearer token specifically so a real gate failure occurs and the
  finding text is actually populated, not skipped).
- **Baseline strategy documented and enforced**: CI never overwrites
  `baseline.json` as a side effect of running the gate (Phase 7's
  immutability guarantee, unchanged) — every CI template documents
  updating it as its own separate, deliberately-triggered step.
- **Bounded, narrow retry** (brief §19): `ci.retry.count`, hard-capped at
  `MAX_CI_RETRY_COUNT=2` regardless of configuration, retries `assess`'s
  functional-execution step only, and only on a total transport wipeout —
  never a partial failure or a genuine assertion/threshold failure
  (verified: `test_retry_never_applies_to_a_real_assertion_failure`).
- **Three CI provider templates** (brief §12-14): GitHub Actions, GitLab
  CI, Jenkins — each installs `universal-test` as a plain `pip install`
  (no provider SDK, no Jenkins plugin dependency), runs `assess --ci --yes
  --target ... --baseline ... --output reports/`, relies on the CLI's own
  exit code, and uploads `reports/` unconditionally (brief §15). None
  assumes a `localhost` service already exists — the application-startup
  step is always an explicit placeholder.

### Two deliberate exit-code behavior changes to pre-existing tests

Both required by this phase's own brief, not incidental, and both keep the
exact same underlying assertion about category status — only the
exit-code expectation changed to match the new, more specific contract:

1. `test_unreachable_target_is_functional_fail`: `0 -> 3` (brief §18's
   "target unavailable is infrastructure error, not quality regression"
   rule didn't exist before this phase).
2. `test_failed_functional_project_is_warning` and
   `test_performance_with_flag_and_yes_executes_and_breaches_threshold`:
   `0 -> 1` (a real assertion/threshold failure against a live target now
   fails the default Quality Gate, which also didn't exist before this
   phase).

Additionally, `test_assess_invalid_baseline_path_does_not_crash` changed
`0 -> 2`: an explicitly-supplied `--baseline` that can't be loaded is now
a configuration error rather than a silently-degraded success — a
deliberate Phase 8 tightening (assess still writes a full report first).

### Tests executed

```
python -m pytest -q
```

**Result: 526 passed, 0 failed** (456 from Phases 1-7 + 70 new). New
coverage: every rule in the Quality Gate's vocabulary individually
(all-pass, functional/performance real failure vs. unreachable-is-infra-
error plus the explicit opt-in override, all five regression severities,
database not-assessed default-off/opt-in, unknown assessment status never
failing, database/discovery schema-change warnings, mixed findings, a
custom policy disabling a default rule), CI environment detection (every
brief-named variable, specific-marker-preferred-over-generic, empty-string
not detected), serializer output (no secret-shaped content), the three CI
templates (parse, mention the right flags, no hardcoded credentials), and
full CLI-level integration: all four exit codes against the real offline
fixture server (including a genuine unreachable-target `3` via a
bind-then-close probe socket), `--ci` never hanging without `--yes`
(including with a monkeypatched `isatty`), CI env vars never auto-
authorizing traffic (parametrized), bounded retry (disabled by default,
retries exactly once on a real total transport wipeout with `caplog`
verification, never retries a real assertion failure, hard-capped at
`MAX_CI_RETRY_COUNT`), and bearer-token redaction through an actual gate
failure. `tests/core/test_config.py` gained default/custom/nested-merge
/invalid-shape policy cases mirroring Phase 7's regression-config tests.

Manually verified end-to-end via the offline fixture server: `assess --ci`
(structured summary, exit 0), `assess --ci --performance` without `--yes`
under a simulated `GITHUB_ACTIONS=true` environment (correctly refused,
zero traffic sent, exit 0 since performance just degrades to
`NOT_ASSESSED`), and the same command with `--yes` added (real execution).
Both YAML CI templates verified to parse with `yaml.safe_load()`.

### Known limitations

- The `0/1/2/3` exit-code contract and `--ci` apply to `assess` only —
  `scan`/`test`/`performance`/`database`/`baseline save`/`baseline
  compare` keep their pre-existing Phase 1-6 exit-code conventions
  (`0`/`2` only), not retrofitted this phase.
- No performance-execution retry — only the functional-execution step is
  retried on a total transport wipeout; retrying an entire load test was
  considered and deliberately deferred (more expensive, riskier to do
  safely) rather than built speculatively.
- No numeric quality score, still — unchanged from Phase 5/7.
- No automatic branch-protection/PR-blocking configuration — this tool
  produces the exit code and report; wiring that to a provider's branch
  protection rules is the CI template's/project's own responsibility,
  documented but not automated.
- CI provider templates are starting points, not tested against a live
  GitHub/GitLab/Jenkins instance (per the brief's own instruction not to
  actually connect to any of them) — validated only for YAML well-
  formedness and the presence of the expected CLI flags.

### Next phase

Per the Phase 8 brief's stop condition, **do not start** the browser/UI
adapter, AI integration, a security scanner, the blockchain adapter, or
distributed testing without an explicit go-ahead.

---

## V1 Hardening / Architecture / Safety Audit — ✅ Done (2026-08-09)

Not a numbered phase — a full-repository audit across Phases 1-8 before
the V1.0 freeze, per an explicit go-ahead. Full findings, methodology, and
per-section results in `docs/V1_HARDENING_AUDIT.md`; the frozen V1
capability/contract surface in `docs/V1_FREEZE.md`.

### Findings and fixes

Two real (Critical/High) findings, both fixed with durable regression
tests, not ad hoc patches:

1. **Secret leakage (Critical)**: `core/redaction.py` never redacted
   `Cookie`/`Set-Cookie` header values at all — a real target setting a
   session cookie would have had it written verbatim into every report
   format. Fixed by adding `cookie`/`set[_-]?cookie` to both redaction
   patterns; verified with 5 new unit tests plus 1 new real-HTTP
   integration test (a new `/with-cookie` fixture-server route).
2. **Windows console compatibility (High)**: 7 files still contained a raw
   em dash in finding/report text that reaches printed console output
   without `--output` (e.g. `assess --format html` with no `--output`) —
   the same garbling bug class found and fixed in Phases 6/7, reintroduced
   in Phase 7/8 finding-description strings. Fixed across
   `assessment/configuration_assessment.py`, `assessment
   /database_assessment.py`, `regression/discovery_compare.py`,
   `regression/engine.py`, `reporting/html_report.py`,
   `reporting/markdown_report.py`; verified empirically (reproduced the
   garbling before the fix, confirmed clean after) and covered by a new
   durable regression test file
   (`tests/test_windows_console_compatibility.py`) that exercises the
   actual finding-generation code paths, not a static grep.

Dead code cleanup (Low, within this audit's explicit scope): removed 2
unused imports in `adapters/rest/adapter.py`, 1 placeholder-less f-string
in `discovery/serializers.py`, and 4 unused imports + 1 placeholder-less
f-string across test files (found via `pyflakes`, not previously part of
this project's toolchain — used here as a one-time audit pass).

No architecture boundary violations, no unsafe network/database/
repository-execution behavior, and no overclaiming documentation language
were found — see the audit doc's per-section detail.

### New deliverables

- `tests/fixtures/e2e-project/` — the canonical end-to-end fixture: an
  OpenAPI spec (matching real fixture-server routes for functional/
  performance testing), a real SQLite database, Docker/Docker Compose/
  GitHub Actions/pytest evidence, and a fixture secret pattern — used to
  exercise every implemented subcommand in one project.
- `tests/e2e/test_e2e_pipeline.py` (9 tests) — runs `scan`/`test`
  /`performance`/`database`/`assess`/`baseline save`/`baseline compare`
  against the e2e fixture via the real offline fixture server and a real
  SQLite file, including a full-pipeline determinism check.
- `tests/cli/test_exit_code_matrix.py` (15 tests) — makes the `0/1/2/3`
  exit-code contract explicit and independently diagnosable per scenario,
  including the subtle timeout-is-infra-error-not-quality-failure case.
- `docs/V1_HARDENING_AUDIT.md`, `docs/V1_FREEZE.md`.

### Tests executed

```
python -m pytest -q
```

**Result: 563 passed, 0 failed** (526 before this audit + 37 new: 4 cookie-
redaction unit tests, 1 cookie-redaction HTTP integration test, 5 Windows-
console-compatibility regression tests, 9 E2E pipeline tests, 3 config
empty-value edge-case tests, 15 exit-code matrix tests). No existing test
was weakened or deleted.

### Known limitations / remaining risks

See `docs/V1_HARDENING_AUDIT.md`'s "Remaining Risks" section: a soft
architectural dataclass-import coupling (not a behavioral risk), CI
templates unvalidated against a live provider, and no large-repository
(tens-of-thousands-of-files) load test performed in this environment.

### Recommendation

Ready for the V1.0 freeze (see `docs/V1_FREEZE.md`). Do not start Phase 9
(or any of: browser/UI adapter, AI integration, security scanner,
blockchain adapter, GraphQL/gRPC, distributed testing) without an explicit
go-ahead.

---

## V1.0 Release Engineering — ✅ Done (2026-08-09)

Not a numbered phase — packaging the frozen V1 codebase into a cleanly
installable, verified `universal-test` 1.0.0 release, per an explicit
go-ahead following the hardening audit. Full detail in `docs
/V1_RELEASE_CHECKLIST.md` and `docs/V1_RELEASE.md`.

### What changed

- **Version**: `src/universal_test/__init__.py::__version__` bumped to
  `"1.0.0"`, the single source of truth. `pyproject.toml`'s previously
  duplicated `version = "0.1.0"` literal replaced with `dynamic =
  ["version"]` + `[tool.setuptools.dynamic]` reading the same attribute —
  eliminates the two-places-to-update problem rather than just
  hand-syncing both, per the release brief's "不要建立第二套 version system"
  instruction.
- **Packaging**: `build` added as a `dev`-only dependency (never runtime).
  `python -m build` verified producing both
  `universal_test-1.0.0-py3-none-any.whl` and
  `universal_test-1.0.0.tar.gz`. Added `MANIFEST.in` after discovering the
  sdist leaked 2 stray top-level `tests/` files (a setuptools default-
  discovery artifact, not intentional) — now pruned alongside `examples/`,
  `docs/`, `reports/`, `plugins/`, `schemas/`, `.venv/`, and all
  `__pycache__`/`*.pyc`.
- **Clean-environment verification**: a throwaway venv installed the
  built wheel and confirmed `--version`/`--help` (all subcommands), a base
  install with zero database drivers (confirmed via `pip list`), the
  `[database]` extra resolving all three optional drivers, and the full
  `tests/fixtures/e2e-project/` smoke sequence (scan/test/performance
  --dry-run/database --dry-run/assess/baseline save/baseline compare)
  against the real offline fixture server — all before the throwaway venv
  was deleted (never committed).
- **README**: fully rewritten as V1.0 user documentation (What It Does /
  Installation / Quick Start / Commands / Configuration / Reports /
  Regression / Safety Model / Supported Technologies / Limitations /
  Development) — the Phase-by-phase development narrative that had
  accumulated across Phases 2-8 was replaced with plain feature
  descriptions; every configuration example re-verified to parse against
  the real schema, every command example re-verified against real CLI
  output (one stale example output — `test --dry-run`'s endpoint/test
  counts — corrected to match the actual fixture).
- **CHANGELOG.md**: added a concise `## [1.0.0]` release-notes section
  (capability summary, not a phase-by-phase commit log) above the
  existing detailed Phase 0-8 history, now labeled "Full development
  history" and clearly separated from the release notes proper.
- New `docs/V1_RELEASE_CHECKLIST.md`, `docs/V1_RELEASE.md`, `docs
  /POST_V1_BACKLOG.md` (11 candidate post-V1 directions recorded with
  purpose/value/risks/dependency/why-deferred each — none implemented,
  none scheduled).

### Tests executed

```
python -m pytest -q
```

**Result: 563 passed, 0 failed** — unchanged from the post-audit count.
Release engineering verified the *built artifact* (wheel/sdist) via a
scripted manual smoke sequence against a clean virtual environment, not
new pytest coverage — the source-level test suite itself was not modified
this pass.

### Recommendation

V1.0 is released. Do not start Phase 9 or any Post-V1 backlog item
(`docs/POST_V1_BACKLOG.md`) without an explicit go-ahead.

---

## Post-V1 Phase 1 — Non-Technical User GUI / One-Click Desktop — ✅ Done (2026-08-09)

Explicit go-ahead received to build a local, browser-based GUI so a
non-technical user can run a first-pass project health check without
knowing Python/CLI/terminal/pytest/OpenAPI/HTTP/database
drivers/baseline/regression. Full detail in `docs/GUI_ARCHITECTURE.md`,
`docs/GUI_USER_GUIDE.md`, `docs/GUI_SAFETY.md`.

### Architecture decision

Inspected `cli/main.py`'s `_run_pipeline`/`_run_assess` before writing any
GUI code. No existing application/service boundary existed between the
CLI and Core, so a thin new layer was added:
`src/universal_test/application/` (`service.py::AssessmentRequest` /
`run_assessment()` / `AssessmentOutcome`, `events.py::ProgressEvent`).
It calls the exact same Core/adapter entry points the CLI already calls
(`discover()`, `rest_run()`, `resolve_performance_target()` +
`PerformanceRunner`, `db_discover()`, `build_assessment()`,
`regression_compare()`, `qg_evaluate()`, the three `reporting` renderers)
— nothing in Discovery/Testing/Assessment/Reporting was reimplemented or
modified. The one behavioral difference from the CLI: performance testing
replaces the interactive `input()` confirmation prompt with an explicit
`AssessmentRequest.performance_confirmed` boolean the GUI must set from
its own confirmation checkbox — `_run_performance()` requires **both**
`run_performance` and `performance_confirmed` before sending any traffic.

### What changed

- **`src/universal_test/application/`** (new): `AssessmentRequest`,
  `AssessmentOutcome`, `run_assessment()`, `ProgressEvent`
  (`project_scan`/`functional_test`/`performance_test`/
  `database_assessment`/`regression`/`assessment`/`report_generation`
  stages, each `started`/`completed`/`skipped`/`failed`).
- **`src/universal_test/gui/`** (new): `server.py`
  (`ThreadingHTTPServer`, loopback-only — `make_server()` raises
  `ValueError` on any non-loopback host), `runs.py` (`RunRegistry`
  running each assessment on a background thread, `queue.Queue`-fed SSE
  stream), `launcher.py` (`find_free_port()`, `webbrowser.open()` with a
  print-the-URL fallback that never crashes the server), `static/`
  (`index.html`/`style.css`/`i18n.js`/`app.js` — plain vanilla JS, no
  build step, no Node.js; Traditional Chinese default with an English
  toggle; internal enum values stay English and are translated only at
  render time).
- **`cli/main.py`**: added the `gui` subcommand
  (`--port`/`--no-browser`/`--verbose`), dispatched before the
  `--target`/`load_config` logic since `gui` takes no project `path`.
  Every other subcommand is unchanged.
- **`release/windows/`** (new): `launch_gui.py` (PyInstaller entry
  point), `UniversalTest.spec` (bundles `gui/static/*` as data, excludes
  the optional database drivers), `build.ps1`. Built and smoke-tested:
  `dist/windows/UniversalTest/UniversalTest.exe` starts, serves the SPA,
  and answers `/api/version` — verified with a real (non-mocked) run of
  the packaged exe, then the build output was deleted (not committed).
- **`pyproject.toml`**: added a `packaging` extra (`pyinstaller>=6.0`,
  build-time only, never a runtime dependency) and
  `[tool.setuptools.package-data]` so `gui/static/*` ships inside the
  wheel too (verified by inspecting a real built wheel's file list, not
  just PyInstaller's source-tree bundling).
- **Version**: `__version__` bumped `1.0.0` -> `1.1.0` (the single source
  of truth `pyproject.toml` already reads dynamically — no second place
  to update). `dist/` regenerated at both `1.0.0` (restoring what a
  `rm -rf dist` during this pass had deleted — confirmed reproducible
  from source, per the V1.0 release's own claim) and `1.1.0`.
- **Docs**: `docs/GUI_ARCHITECTURE.md`, `docs/GUI_USER_GUIDE.md`,
  `docs/GUI_SAFETY.md` (new); README gained "## Graphical User Interface"
  and "## Windows One-Click Application" sections.
- **CHANGELOG.md**: added a `## [1.1.0]` release-notes section.

### Tests executed

```
python -m pytest -q
```

**Result: 585 passed, 0 failed** (563 unmodified V1.0 tests +
22 new: `tests/application/test_application_service.py` (9),
`tests/gui/test_gui_server.py` (10), `tests/gui/test_gui_launcher.py` (3)
via `tests/cli/test_cli_gui_command.py` (2) — safe defaults, no-target
means no functional execution, the performance two-checkbox gate (both
"opts in but doesn't confirm" and "opts in and confirms, executes"),
database opt-in, progress-event stage ordering, report-file generation
per format, loopback-only binding (`make_server` rejecting `0.0.0.0`),
static path-traversal rejection, the assess -> SSE stream -> result round
trip, and the packaged launcher never blocking on a failed browser open.

### Known limitations

- The packaged exe builds `console=True` on purpose (an intentional
  trade-off, documented in `UniversalTest.spec`): a `console=False`
  windowed build would silence the browser-auto-open failure fallback
  message (brief §20) without adding a GUI toolkit dependency just for a
  fallback dialog.
- Baseline/regression, database-profile, and advanced performance options
  are exposed in the GUI's Advanced Settings but got lighter manual/UI
  polish than the primary "select folder -> start -> results" flow;
  their underlying Application Service Layer paths are exercised by the
  automated test suite, not by interactive browser testing in this pass.
- No accessibility audit (screen reader / full keyboard-navigation pass)
  was performed beyond semantic HTML and visible focus/label wiring.
- `release/windows/build.ps1` originally called the bare `python` on
  PATH rather than the repo's `.venv` interpreter, and PowerShell does
  not turn a native command's non-zero exit code into a terminating
  error by default -- so a machine without PyInstaller on its base
  `python` would see the script print "Built: ..." even though no exe
  was produced. Fixed same-day: the script now prefers `.venv\Scripts
  \python.exe`, checks `$LASTEXITCODE`, and verifies the exe actually
  exists before declaring success. A real `dist\windows\UniversalTest
  \UniversalTest.exe` was built and re-verified (started, served
  `/api/version` as `1.1.0`) after the fix.
- `dist/windows/` (the built exe) is a local build artifact, not
  committed to any release channel — there is no pre-built download; it
  is produced on demand by `release/windows/build.ps1` and is reproducible
  from source at any time, consistent with `dist/`'s wheel/sdist already
  being treated as build output rather than checked-in content.

### Recommendation

Post-V1 Phase 1 is done. Stop here per the phase brief's explicit stop
condition — do not start browser automation testing, AI integration, a
security scanner, a blockchain adapter, GraphQL, gRPC, or distributed
testing without a further explicit go-ahead.

---

## Post-V1 Final QA / Stabilization — ✅ Done (2026-08-10)

Not a new phase — a stabilization pass fixing confirmed defects from an
external audit of the V1.1 GUI. No new features; see `CHANGELOG.md`
`[1.1.1]` for the full user-visible list.

### Files changed

- `src/universal_test/core/logging_setup.py` — `propagate = False` moved
  to import time.
- `tests/conftest.py` — new; imports `logging_setup` during collection so
  the fix above holds regardless of which test module runs first.
- `tests/core/test_logging_setup.py` — new regression coverage.
- `src/universal_test/gui/server.py` — sanitized internal-error responses
  (`error_id` instead of `traceback.format_exc()`), full `quality_gate`
  shape in `_outcome_to_dict()`, new `POST /api/perf/endpoints` route,
  409 on duplicate `/api/assess` while a run is active.
- `src/universal_test/gui/runs.py` — bounded `RunRegistry`
  (`_prune_completed_locked`), `RunAlreadyActiveError`, sanitized
  run-failure error (`error_id`, no raw exception text).
- `src/universal_test/gui/launcher.py` — native-dialog fallback for a
  windowed (no-console) build; guards `print()` against `sys.stdout is
  None`.
- `release/windows/UniversalTest.spec` — `console=False`.
- `src/universal_test/gui/static/{index.html,app.js,i18n.js,style.css}` —
  Regression/Quality Gate result sections, dynamic Regression progress
  stage, API authentication fields, performance endpoint selection UI,
  Start-button double-click guard, Traditional Chinese category labels,
  sanitized fatal-error rendering (`error_id`, no raw detail).
- `tests/gui/test_gui_server.py`, `tests/gui/test_gui_runs.py`,
  `tests/gui/test_gui_launcher.py` — new/expanded regression coverage for
  all of the above.
- `README.md`, `README.zh-TW.md`, `docs/GUI_USER_GUIDE.md`,
  `docs/GUI_SAFETY.md`, `docs/GUI_ARCHITECTURE.md`, `CHANGELOG.md` — kept
  in sync with the above; `README.zh-TW.md` gained the GUI / one-click-app
  sections that only existed in English before.

### Tests executed

Targeted GUI/logging suites, then the full suite (`pytest -q`) — see the
Final QA Report delivered alongside this pass for exact counts.

### Known limitations (updated from the entry above)

- The `console=True` trade-off documented in the original Phase 1 entry
  above is now resolved: the packaged exe builds `console=False`, and the
  browser-auto-open fallback shows a native Tk dialog instead of relying
  on a console window.
- Manual interactive browser testing (Chrome) could not be run in this
  environment (browser extension not connected in this session) — the
  full request/response contract for every fix was instead verified via
  the automated HTTP-level test suite plus manual `curl` round-trips
  against a locally launched server. Visual rendering/CSS/layout of the
  new Regression/Quality Gate/auth/endpoint-selection UI was verified by
  static content assertions and JS syntax checking (`node --check`), not
  by looking at a rendered page. This should be spot-checked in a browser
  before the next release.
- Finding/recommendation text generated by the assessment/regression
  engines themselves remains English-only; only the GUI's own chrome
  (labels, buttons, category names, stage names, empty states, error
  messages) is fully bilingual. Translating dynamically generated finding
  text was out of scope for this pass.

### Next phase

None planned — this was a stabilization pass, not a new phase. Any further
work (Browser Automation, AI, Security Scanner, Blockchain, GraphQL,
gRPC, Distributed Testing) requires an explicit go-ahead per `skill.md`
and is out of scope here.
