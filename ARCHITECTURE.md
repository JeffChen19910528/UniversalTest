# ARCHITECTURE.md

## 1. Guiding principle

> Universal Core + Project Adapters + Explicit Evidence (`skill.md` §2)

Core never imports anything language/framework/database/cloud-specific.
Technology-specific code lives only under `adapters/`.

```text
                    Universal Test Core
                           |
        +------------------+------------------+
        |                  |                  |
   Discovery           Adapters           Test Engine
        |                  |                  |
        +------------------+------------------+
                           |
                    Result / Evidence
                           |
                    Assessment Engine
                           |
                     Report Generator
```

## 2. Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Available on this machine (`python` → 3.11.6 with pip), strong stdlib (argparse, dataclasses, logging, json, urllib), mature ecosystem for HTTP/OpenAPI/DB/Playwright adapters needed in later phases, cross-platform, fast to iterate. |
| Packaging | `pyproject.toml` + `setuptools` build backend | Standard, no extra build-tool dependency. |
| CLI framework | stdlib `argparse` | Zero extra dependency for a Phase 1 skeleton; matches "minimal external dependencies" (`skill.md` §25). Revisit only if subcommand ergonomics become a real pain point. |
| Domain models | stdlib `dataclasses` + `enum` | No runtime validation dependency needed yet; explicit, typed, serializable via a thin `to_dict()` helper rather than a framework. |
| Configuration format | YAML (`universal-test.yaml`), parsed with `PyYAML` | Required by `skill.md` §18; PyYAML is the de facto standard, single small dependency. |
| Test framework (for the framework itself) | `pytest` | Required by `skill.md` §21/§24; industry standard, good fixture support for future adapter/CLI/integration tests. |
| HTTP client (Phase 3 — added) | `httpx` | Sync client used by the REST adapter's executor; mature, well-maintained, typed, one clean dependency instead of hand-rolling connection/timeout handling over `urllib`. |
| OpenAPI parsing (Phase 3) | No dedicated library — internal `$ref` resolution + direct dict-walking over the already-parsed YAML/JSON (`PyYAML`/stdlib `json`) | Considered `prance`/`openapi-core`: both pull in heavier transitive dependency chains and (for `prance`) can fetch external `$ref`s over the network by default, which conflicts with "safe by default" (skill.md §4.2) — an implicit outbound request before the user has configured anything is exactly what must not happen. OpenAPI 3.x's `paths`/`components` structure is a stable, well-documented plain-dict shape; internal-ref resolution is ~60 lines of recursive dict walking (`adapters/rest/openapi_loader.py`) with cycle/depth guards. External `$ref`s are deliberately left unresolved with a warning rather than fetched. |
| JSON Schema validation (Phase 3 — added) | `jsonschema` | Explicitly authorized by the Phase 3 brief to replace Phase 1's minimal checker; mature, the de facto standard Python implementation, supports the full JSON Schema vocabulary the minimal checker couldn't (`minLength`, `pattern`, `oneOf`, etc.). |
| Concurrency engine (Phase 4 — added, no new dependency) | stdlib `concurrent.futures.ThreadPoolExecutor` + `threading.Event` (cancellation) + `queue.SimpleQueue` (thread-safe result collection) | I/O-bound HTTP requests are exactly `ThreadPoolExecutor`'s designed use case; `max_workers=N` gives correct bounded concurrency without hand-rolled semaphores. `asyncio` was considered and rejected: it would require an async REST executor variant (and async httpx client) purely to look more "modern," with no behavioral benefit at Phase 4's scale — the brief itself prioritizes correctness/boundedness over performance theater (§8/§19). |
| Interval timing (Phase 4 — added, no new dependency) | stdlib `time.perf_counter()` | Not `time.monotonic()` — see ARCHITECTURE.md §8.4/§11.12 for the real resolution bug this avoided on this Windows Python build. |
| HTML templating (Phase 5+) | `Jinja2` (not yet added) | Deferred until the HTML reporter is built. |
| Browser adapter (Phase 9 — implemented) | Playwright (`playwright>=1.40`, optional `[browser]` extra) | Explicitly preferred by `skill.md` §15. Base install works with zero of it installed (`adapters/browser/executor.py` imports it lazily inside a function, never at module scope); missing install/binary degrades to `NOT_ASSESSED`, never an `ImportError` elsewhere. See §17. |

Dependencies are added only when the phase that needs them starts (`skill.md` §25,
§31.18 — evaluate whether an existing dependency already covers the need before
adding a new one).

## 3. Directory structure

Mirrors `skill.md` §5 with one added level (`src/universal_test/`) for a
standard installable Python package layout.

```text
universal-test/
├── pyproject.toml
├── README.md / SPECIFICATION.md / ARCHITECTURE.md / ROADMAP.md / PROGRESS.md / CHANGELOG.md
├── src/
│   └── universal_test/
│       ├── core/
│       │   ├── models/          # domain models: enums, evidence, test spec, results
│       │   ├── engine/          # assertion evaluation + single-test execution
│       │   ├── assertions/      # assertion registry + builtin assertions
│       │   ├── orchestration/   # run coordination across engine/adapters/assessment
│       │   ├── configuration/   # universal-test.yaml loading + defaults + overrides
│       │   ├── errors.py        # exception hierarchy
│       │   ├── logging_setup.py # structured logging setup
│       │   └── redaction.py     # secret redaction used everywhere output is produced
│       ├── discovery/            # filesystem/language/framework/service/api/database (Phase 2 — implemented)
│       ├── adapters/
│       │   └── rest/             # OpenAPI parsing, test generation, HTTP + performance execution (Phase 3/4 — implemented)
│       │   └── database/        # read-only SQL Server/PostgreSQL/MySQL/SQLite discovery (Phase 6 — implemented)
│       │       # graphql/browser/docker/dotnet/node/python/blockchain: Phase 9+
│       ├── testing/
│       │   └── performance/      # technology-independent load/percentile/threshold engine (Phase 4 — implemented)
│       │       # reliability: later phase; "functional" testing lives in adapters/rest/ (REST is still the only adapter)
│       ├── assessment/            # unified scoring/findings/recommendations (Phase 5 — implemented)
│       ├── reporting/             # json/markdown/html report renderers (Phase 5 — implemented)
│       ├── regression/            # baseline storage + regression comparison (Phase 7 — implemented)
│       ├── quality_gate/          # CI-independent Quality Gate + exit-code contract (Phase 8 — implemented)
│       └── cli/                   # argparse entry point + subcommands
├── tests/                        # mirrors src/ layout
├── docs/
├── examples/                     # fixture projects (Phase 2+)
│   └── ci/                       # GitHub Actions / GitLab CI / Jenkins templates (Phase 8 — implemented)
├── plugins/                      # third-party adapters (later)
├── schemas/                      # JSON Schemas for config/report (later)
└── reports/                      # assess's default output directory (Phase 5); kept via .gitkeep
```

Every package directory (including ones with no Phase 1 logic) gets an
`__init__.py` with a one-line docstring stating which phase populates it, so the
architecture boundary exists in code from day one without pretending the
functionality is implemented.

## 4. Core domain model (Phase 1)

### 4.1 Status vocabularies

Three separate enums, because they answer different questions and conflating
them is exactly the "overclaiming" `skill.md` §4.1 and §20 warn against:

- `ResultStatus` — outcome of *executing* one test: `PASSED, FAILED, SKIPPED,
  ERROR, UNKNOWN`.
- `AssessmentStatus` — outcome of one *assessment category*: `PASS, WARNING,
  FAIL, UNKNOWN, NOT_ASSESSED`.
- `DetectionConfidence` — how a discovery fact was established: `DETECTED,
  INFERRED, NOT_APPLICABLE, UNKNOWN`.

`Severity`: `CRITICAL, HIGH, MEDIUM, LOW, INFO` — attached to findings, not to
raw test results.

### 4.2 Models (`core/models/`)

- `Evidence` — `type: str`, `data: dict`, `description: str | None`. Immutable.
- `TestCase` — framework-independent test spec matching `skill.md` §16
  (`id, name, type, target(adapter, method, path, ...), request, assertions`).
- `AssertionSpec` — `type: str`, `params: dict` (declarative, adapter-agnostic).
- `AssertionResult` — `assertion: AssertionSpec`, `passed: bool`,
  `evidence: list[Evidence]`, `message: str`.
- `TestResult` — `id, category, status: ResultStatus, severity: Severity,
  confidence: float, evidence: list[Evidence], message, recommendation,
  assertion_results: list[AssertionResult]`. Matches the JSON shape in
  `skill.md` §4.3.
- `Finding` — category-level rollup used by the assessment engine:
  `category, status: AssessmentStatus, evidence: list[Evidence], summary,
  recommendation`.

### 4.3 Assertion engine (`core/assertions/`)

`AssertionEngine` is a registry: `register(name, fn)` /
`evaluate(spec: AssertionSpec, context: dict) -> AssertionResult`. Builtin
assertions operate on a generic `context` dict (`status_code`, `elapsed_ms`,
`json`, `headers`, `body`, `rows`) so the engine has no HTTP/DB-specific
imports — adapters populate `context`, Core only evaluates it.

### 4.4 Engine (`core/engine/`)

`TestEngine.run(test_case: TestCase, executor: Callable[[TestCase], dict]) ->
TestResult` — takes an adapter-supplied `executor` callable (returns a context
dict), runs it, evaluates all assertions via `AssertionEngine`, and packages a
`TestResult`. No adapter is wired in yet in Phase 1; tests use a fake executor.

### 4.5 Orchestration (`core/orchestration/`)

`Orchestrator` coordinates a batch run: given a `Config`, a list of
`TestCase`s and an executor, it runs each through `TestEngine`, collects
`TestResult`s, and returns a `RunResult` (results + summary counts). This is
the seam later phases hang discovery → adapters → assessment → reporting off
of; Phase 1 only implements the "run these test cases" slice.

### 4.6 Configuration (`core/configuration/`)

`Config` dataclass tree mirroring `skill.md` §18's `universal-test.yaml`
(`project, assessment, functional, performance, database, security, ai`
sections). `load_config(path=None, overrides=None)` returns defaults if no
file is present — the tool must run with near-zero configuration.

### 4.7 Errors (`core/errors.py`)

`UniversalTestError` (base) →
`ConfigurationError, DiscoveryError, AdapterError, ExecutionError,
AssertionError_` (suffixed to avoid shadowing the builtin `AssertionError`).

### 4.8 Logging & redaction

`logging_setup.configure_logging(verbose: bool)` configures stdlib `logging`
with a formatter that never receives raw secrets: `redaction.redact(text)`
applies the pattern list from `skill.md` §26 and is used by both the logging
formatter and (in later phases) the report writers. The pattern list
covers `password/passwd/pwd/secret/token/api_key/access_key/authorization
/auth/private_key/client_secret` plus `cookie`/`set-cookie` (added during
the V1 hardening audit — a real `Set-Cookie` response header was not
covered by any pattern before that, the audit's most significant finding;
see `docs/V1_HARDENING_AUDIT.md`), connection-string credentials
(`scheme://user:pass@host`), and PEM private-key blocks. `redact_mapping()`
additionally treats any of these as a *sensitive key name* on structured
data (e.g. an HTTP response headers dict), redacting the entire value
regardless of its content — necessary for `Set-Cookie`, whose value never
itself contains a matching keyword the way `token=...` does.

## 5. Adapter contract (defined Phase 1, first implementation Phase 3)

Every adapter implements:

```text
detect(project_path) -> bool
describe() -> AdapterInfo(name, version, capabilities)
discover(project_path) -> DiscoveryResult
generate_tests(discovery_result, config) -> list[TestCase]
execute(test_case) -> dict            # context consumed by AssertionEngine
collect_metrics() -> dict
```

Declared via a small `AdapterInfo` model (name, version, capabilities list) —
Core discovers adapters by capability, never by importing a specific adapter
module. `adapters/rest/adapter.py::RestAdapter` is the first concrete
implementation (Phase 3); see §7 for how it actually wires this together (its
practical entry point is the module-level `run()` function, not just the
class — `RestAdapter` exists to keep the contract shape honest for whichever
adapter comes next).

## 6. Discovery Engine (`discovery/`, Phase 2 — implemented)

Read-only, technology-independent project discovery. `discovery.engine.discover
(project_path) -> ProjectModel` is the entry point; `universal-test scan`
calls it directly.

### 6.1 Pipeline

```text
filesystem.walk()          -> list[ScannedFile]   (vendor/generated dirs pruned)
manifests.load_manifests() -> ManifestBundle       (bounded read of known manifest files)
repository.discover_repository()  -> RepositoryInfo (read-only `git rev-parse`/`status` only)
language / project_type / framework / infrastructure / database / api /
test_framework / secrets  -> per-category Detection lists, each fed `files` + `bundle`
```

Every detector step runs inside a try/except in `engine.discover()`: a single
detector raising does not abort the scan — it's recorded in
`ProjectModel.warnings` and the rest of the scan still completes (skill.md
§4.1/§17 — a partial failure is `UNKNOWN`, not a crash).

### 6.2 Detection method (not "count file extensions")

`discovery.manifests` centralizes reading the handful of well-known manifest
files (`package.json`, `pyproject.toml`, `*.csproj`, `pom.xml`/`build.gradle`,
`go.mod`, `Cargo.toml`, `composer.json`) once, so every detector reasons about
real project metadata instead of guessing from file extensions alone.

- **Language**: manifest/marker-file evidence (e.g. `pyproject.toml` for
  Python, `*.csproj`/`*.sln` for C#) anchors `DetectionConfidence.DETECTED`;
  file-extension counts are supporting evidence and, alone, only reach
  `DETECTED` above a small volume threshold or stay `INFERRED` below it.
- **Framework**: only asserted from a concrete manifest dependency (e.g.
  `fastapi` in `requirements.txt`) or an unambiguous marker file (e.g.
  `manage.py` for Django, `hardhat.config.js` for Hardhat) — no source-code
  import scanning, so a framework is never claimed from a single weak signal.
- **Infrastructure/CI**: filename/path matching (`Dockerfile`,
  `.github/workflows/*.yml`, `*.tf`, ...); Kubernetes additionally does a
  bounded content scan (`apiVersion:` + `kind:`) over a capped number of YAML
  files when no `k8s/`/`kubernetes/` directory exists.
- **Database**: dependency names (`psycopg2`, `Npgsql`, `mongodb.Driver`, ...),
  `*.sqlite`/`*.db` files, and connection-string *patterns* (never live
  connections) in known config files and `docker-compose` service images.
- **Secrets**: `discovery.secrets` scans bounded, non-binary, non-lockfile
  text for `password=`/`token=`/`api_key=`/connection-string/PEM-key
  patterns. Only `file`, `line`, and `pattern_type` are recorded — the
  matched value is discarded before it ever reaches a `SecretFinding`.
  Common placeholders (`CHANGEME`, `REPLACE_ME`, `<PASSWORD>`, ...) are
  filtered to keep signal-to-noise reasonable. A pattern match is evidence of
  a pattern, not a confirmed secret or a vulnerability finding.

### 6.3 Data model (`discovery/models.py`)

`ProjectModel` (root result) composes `RepositoryInfo`,
`LanguageDetection`, `ProjectTypeDetection`, `FrameworkDetection`,
`BuildSystemDetection`, `InfrastructureDetection`, `DatabaseDetection`,
`ApiDetection`, `TestFrameworkDetection`, `SecretFinding` — every one of
these (except `SecretFinding`, whose confidence has a narrower meaning) is a
`Detection`: `name`, `confidence: DetectionConfidence`, `evidence:
list[core.models.Evidence]`. All are plain dataclasses with `to_dict()`, no
Python-specific serialization leaking into the shape — this is the
"framework-independent normalized Project Model" the Phase 2 brief calls for.

### 6.4 Output (`discovery/serializers.py`)

`to_text`/`to_json`/`to_markdown` render a `ProjectModel`. These are
discovery-specific, not the general Phase 5 report generators — `reporting/`
stays empty until Phase 5 defines the full report shape (executive summary,
findings, recommendations, etc. per skill.md §19), so these serializers only
know about `ProjectModel` and live in `discovery/` accordingly.

## 7. REST/OpenAPI Adapter (`adapters/rest/`, Phase 3 — implemented)

`adapters/rest/adapter.py::run(project_path, *, openapi_override, target,
auth_config, timeout_seconds, dry_run) -> RestRunResult` is the entry point
`universal-test test` calls. Core imports none of this; the adapter imports
`core.models`/`core.engine`/`core.orchestration`/`core.errors`/`core.redaction`
freely (the allowed direction per §1).

### 7.1 Pipeline

```text
discovery_bridge.select_specification()  -> Path            (explicit --openapi wins; else exactly one
                                                               candidate required — see §7.2)
openapi_loader.load_document() + resolve_internal_refs()     -> resolved dict
normalizer.parse_specification()                              -> ApiSpecification (adapters/rest/models.py)
test_generation.generate_test_cases()                          -> list[core.models.TestCase]
    |
    +-- dry_run=True  -----------------------------------------> RestRunResult(executed=False), stop here
    |
    +-- target is None ------------------------------------------> RestRunResult(executed=False,
    |                                                                 no_target_reason=...), stop here
    |
    +-- executor.make_executor(target, ...) + core.orchestration.Orchestrator
                                                                 -> RunResult (unmodified Phase 1 code)
                                                                 -> _apply_control_overrides() (see §7.4)
```

### 7.2 Multi-spec safety (Phase 3 brief §1)

`discovery_bridge.find_openapi_candidates()` reuses the exact same filename
heuristic as `discovery.api` (`discovery.api.OPENAPI_NAME_HINTS`, exported
for this purpose) so `scan` and `test` never disagree about what counts as a
candidate. `select_specification()` raises `MultipleSpecsFoundError` (sorted,
deterministic candidate list in the message) when more than one exists and
`--openapi` wasn't given — it never silently picks one. An explicit
`--openapi` always wins outright, without re-scanning.

### 7.3 Normalized model (`adapters/rest/models.py`)

`ApiSpecification` (`title, version, openapi_version, servers, endpoints,
security_schemes, warnings`) composes `ApiEndpoint` (`method: HttpMethod,
path, parameters: list[ParameterModel], request_body: RequestBodyModel|None,
responses: list[ResponseModel], security: list[str]`), `SchemaModel` (a
resolved JSON-Schema dict), and `SecurityScheme`. All plain dataclasses with
`to_dict()`, matching the Phase 2 `ProjectModel` pattern — no OpenAPI-parser
object model leaks past this module. `ApiSpecification.warnings` follows the
same pattern as `ProjectModel.warnings` (Phase 2): unsupported features
(external `$ref`s, Swagger 2.0 documents, schema-validation-not-available,
"no documented response to assert against") are recorded here rather than
silently dropped or turned into a false pass/fail.

`servers` is captured for information only and **never** used as an
execution target — `--target` is the only source of truth (Phase 3 brief §7;
verified by `test_target_override_wins_over_spec_servers`).

### 7.4 Test generation and the `_control` mechanism

`test_generation.py` builds `TestCase`s using the *unmodified* Phase 1
`core.models.TestCase`/`AssertionSpec` shapes and only the assertion types
`AssertionEngine` already supports (`status_code`, `status_code_in`,
`json_schema_valid`) — no new assertion types were added.

Two situations can't be expressed by "run the request and check
assertions": (a) insufficient schema information to build a request
confidently (Phase 3 brief §8), and (b) an endpoint requires authentication
the user didn't supply credentials for (§5 — must be `SKIPPED`, not silently
attempted or silently dropped). Both need a *specific* one of
`ResultStatus.UNKNOWN`/`SKIPPED`, and neither should trigger a real HTTP
call. Rather than teach Core's `TestEngine` a third way to reach these
outcomes, generated `TestCase.request` carries a `"_control"` key:
`{"execute": False, "result_status": "unknown"|"skipped", "reason": str}`.
The executor (§7.5) checks this first and, if `execute` is `False`, returns
without any I/O; since these cases are also generated with `assertions=[]`,
Phase 1's existing `TestEngine.run()` already resolves them to `UNKNOWN`
unmodified. `adapter.py::_apply_control_overrides()` then does one
`dataclasses.replace()` pass after the run, rewriting `status`/`message` for
exactly the entries whose `TestCase` asked for it (matched by list position
— `Orchestrator.run_test_cases` preserves input order). This keeps Core
untouched while still producing the specific status the brief requires.

Negative tests (missing required parameter/body field, invalid type,
unsupported content type) are generated only when (1) a confident positive
baseline request exists to mutate, and (2) OpenAPI documents a concrete
numeric error status to assert against — otherwise the negative case is
skipped with a warning rather than guessed. Capped at 3 per endpoint
(`_MAX_NEGATIVE_TESTS_PER_ENDPOINT`) — deliberately conservative, not fuzzing
(Phase 3 brief §4/§15).

### 7.5 Request data generation (`adapters/rest/request_data.py`)

`generate_value(schema) -> (value, confident)`. Prefers `example` >
`default` > `enum[0]` > a documented `minimum`/format-appropriate safe
default (e.g. `email` format → `test@example.com`); required object
properties are built recursively; `oneOf`/`anyOf` without a discriminating
example return `confident=False` rather than guessing a branch. A `False`
anywhere in a request's required data means that endpoint's positive test
becomes a `_control`-skipped `UNKNOWN` case instead of sending a
partially-invented request.

### 7.6 Authentication (`adapters/rest/auth.py`)

Credentials are read only from named environment variables
(`--bearer-token-env NAME`, never the raw secret as a CLI argument).
`available_scheme_names()` determines which of the spec's declared
`securitySchemes` the supplied `AuthConfig` can satisfy;
`build_auth_headers()` computes the header/query-param to send for one
specific request. Nothing here ever reads a credential out of the scanned
repository or attempts a login — that would be exactly the "guess
credentials" / "bypass authentication" behavior the Phase 3 brief §5
prohibits. Simplification (documented, low-impact): OpenAPI's
AND-within/OR-across `security` requirement structure is flattened to "any
one of these named schemes" — covers the overwhelming majority of real
specs.

### 7.7 HTTP execution (`adapters/rest/executor.py`)

`make_executor(base_url, security_schemes, auth_config, timeout_seconds) ->
Executor` — matches `core.engine.Executor`'s exact signature, so it plugs
into the unmodified `TestEngine`/`Orchestrator`. httpx exceptions are mapped
to distinct `core.errors` subtypes so a report can tell "server unreachable"
apart from "request timed out" apart from "the API returned the wrong
thing": `httpx.ConnectError → NetworkError`, `httpx.TimeoutException →
RequestTimeoutError`, other `httpx.RequestError → TargetError` — all three
still flow through `TestEngine`'s existing generic-exception handling into
`ResultStatus.ERROR`, distinguished by the exception class name recorded in
`Evidence`, not by adding new core status values (Phase 3 brief §14).

**Redaction**: the executor computes and sends auth headers/query params but
never returns them in the context dict it hands to `AssertionEngine` — only
response data goes into `context`. Response headers/body are additionally
passed through `core.redaction.redact`/`redact_mapping` before being placed
in the context, as defense in depth against a target echoing a credential
back. A `TestResult`/`Evidence` built from this context therefore cannot
contain a sent credential by construction, not just by convention — verified
by `tests/adapters/rest/test_secret_redaction.py`.

## 8. Performance Testing Engine (`testing/performance/`, Phase 4 — implemented)

Technology-independent per skill.md §2/the Phase 4 brief §1: **no `httpx`
import anywhere in this package.** `PerformanceRunner` takes a plain
`Callable[[PerformanceRequest], PerformanceSample]`; the REST adapter
supplies one (`adapters/rest/performance_executor.py`). This mirrors the
Core/adapter split `core.engine.TestEngine` already established in Phase 1
— `testing/performance/` is the same pattern one layer up, for load
generation instead of a single functional check.

### 8.1 Pipeline

```text
adapters/rest/performance.py::resolve_performance_target()
    -> (ApiSpecification|None, ApiEndpoint|None, PerformanceRequest, warnings)
       (prefers the project's OpenAPI spec + Phase 3's own request generator;
        falls back to an explicit --endpoint/--method only when no spec exists)

testing/performance/planner.py::build_load_profile()
    -> LoadProfile (every numeric knob clamped to a hard ceiling here,
       independent of CLI-level validation)

testing/performance/runner.py::PerformanceRunner.run()
    -> for each concurrency level: bounded ThreadPoolExecutor batch
       -> testing/performance/metrics.py::aggregate() -> PerformanceMetrics
       -> testing/performance/thresholds.py::evaluate_thresholds()
    -> PerformanceResult
```

### 8.2 Why `ThreadPoolExecutor`, not asyncio

I/O-bound HTTP requests are `ThreadPoolExecutor`'s textbook use case;
`max_workers=concurrency` gives correct bounded concurrency for free. An
asyncio rewrite of the REST executor (and every dependency call site) would
be a strictly larger change for no behavioral benefit at Phase 4's scale —
the brief itself says prefer correctness/boundedness over "looking
efficient" (§8). Two execution modes:

- **Fixed count** (`--requests N`): `N` tasks submitted to a pool sized at
  `concurrency`; the pool's own queueing *is* the bounded-concurrency
  mechanism.
- **Fixed duration** (`--duration S`): `concurrency` worker threads each
  loop "send request, repeat" until a shared deadline or the cancellation
  event fires, pushing samples through a `queue.SimpleQueue` (thread-safe,
  no explicit lock needed) drained after all workers join.

Cancellation is cooperative (`threading.Event`, checked between requests in
duration mode and between concurrency levels always) — Python threads can't
be forcibly killed, and every in-flight request is already bounded by its
own `--timeout`, so waiting for the current batch to finish is the correct
"graceful shutdown," not a compromise. **Known gap**: the CLI does not yet
wire `SIGINT`/Ctrl+C to this cancellation event — the capability exists and
is unit-tested (`tests/testing/performance/test_runner.py`) for programmatic
callers, but interactive Ctrl+C during a real `universal-test performance`
run currently kills the process the normal Python way rather than producing
a partial `PerformanceResult`.

### 8.3 Percentiles — nearest-rank method (documented, not a bare one-liner)

`percentiles.py`: for `n` sorted values and percentile `p`, `rank =
ceil(p/100 * n)` clamped to `[1, n]`, result is `sorted[rank-1]`. Always an
actually-observed sample, never an interpolated synthetic value — see the
module docstring for the full rationale. Edge cases (0/1/2 samples,
identical values, large datasets) are explicit unit tests, not just
implied by the algorithm.

### 8.4 Metrics, error classification, and RPS definition

`PerformanceSample.error_type` is one of `NONE / HTTP_ERROR (status >= 400,
transport succeeded) / TIMEOUT / NETWORK_ERROR / TARGET_ERROR` — set by the
executor, which per its contract **must never raise** (every transport
failure is caught and encoded as a sample so aggregation always sees every
attempted request, success or failure). `metrics.aggregate()` reports
`timeout_count`/`http_error_count` separately but folds `NETWORK_ERROR` and
`TARGET_ERROR` into one `network_error_count` bucket (both mean "the
request layer itself failed," as opposed to a completed HTTP exchange with
an error status — matching the brief §12's grouping without inventing a
narrower 4th field the report doesn't need). RPS is `total_requests /
wall_clock_duration_seconds` — the level's actual elapsed time, not the sum
of per-request durations, which would overstate throughput under
concurrency (brief §11).

**Platform note (real bug found and fixed during implementation)**: interval
timing uses `time.perf_counter()`, not `time.monotonic()`. This project's
Windows Python build's `time.monotonic()` has ~15.6ms resolution (it's
backed by `GetTickCount`), which silently produced a `duration_seconds` of
exactly `0.0` (and therefore RPS `0.0`) for any concurrency level that
completed within one tick — very plausible at higher concurrency against a
fast target. `time.perf_counter()` uses the highest-resolution timer
available on every platform and is what the stdlib docs recommend
specifically for measuring short durations. Caught by manually running a
two-level plan against the local fixture server and noticing the second
level's numbers were exactly zero — not caught by any single-level unit
test, which is why `tests/testing/performance/test_runner.py` includes
multi-level runs and the REST integration tests measure against a real
(if fast) local server rather than only a synthetic zero-latency fake.

### 8.5 Threshold evaluation (`thresholds.py`) — independent, not hardcoded in the runner

`evaluate_thresholds(metrics, thresholds_dict, warnings) ->
list[PerformanceThresholdResult]`, reusing `core.models.enums.
AssessmentStatus` (`PASS/FAIL/NOT_ASSESSED`) rather than inventing a new
status enum. Recognized keys: `p50_ms/p90_ms/p95_ms/p99_ms` (max),
`error_rate_percent` (max), `min_rps` (min) — matching skill.md §10/§13's
example config exactly. A latency/RPS threshold against zero samples is
`NOT_ASSESSED`, never a fabricated pass. Unrecognized keys are warned about,
not silently dropped or fatal. `PerformanceRunner` calls this once per
level; it contains no threshold logic of its own.

### 8.6 Safety bounds (`planner.py`) — Phase 4 brief §3's highest priority

Every path that constructs a `LoadProfile` goes through
`build_load_profile()`, which enforces hard ceilings independent of
whatever the CLI validates: `MAX_CONCURRENCY=200`,
`MAX_REQUESTS_PER_LEVEL=2000`, `MAX_DURATION_SECONDS_PER_LEVEL=300`,
`MAX_LEVELS=10`. `baseline` always forces `concurrency=[1]`; `custom`
requires an explicit `--concurrency` (never silently substitutes a
default); `stress` auto-generates a step sequence capped at
`--max-concurrency` (default 50, itself capped at `MAX_CONCURRENCY`) and
defaults a `stop_on_error_rate_percent=50%` stopping condition when the
user gave none, so a stress run always terminates for *two* independent
reasons (the concurrency cap, and a stop condition) even with zero
extra flags. `--target` is required for `performance` unconditionally,
**including `--dry-run`** — deliberately different from `test`, since a
performance plan without a known target isn't a plan (see §9 below).

### 8.7 CLI confirmation prompt

Non-`--dry-run`, non-`--yes` runs print the same `plan_to_text()` a
dry-run would show, plus the estimated request count, then read `y`/`yes`
from stdin. A non-interactive session (`not sys.stdin.isatty()`) without
`--yes` is refused outright rather than hanging on a prompt nobody can
answer — the brief's own CI note ("提供 `--yes` 用於 CI"). No attempt is
made to detect "this looks like production" from the target URL — the
brief explicitly says the tool cannot reliably know the environment;
instead the plan, size estimate, and confirmation are always shown.

## 9. Assessment & Reporting (`assessment/`, `reporting/`, Phase 5 — implemented)

`assessment/` and `reporting/` were reserved-but-empty since Phase 1
(skill.md §5). Phase 5 populates both, and both stay strictly aggregation
layers: they read the `ProjectModel` (Phase 2), `RunResult` (Phase 3), and
`PerformanceResult` (Phase 4) that already exist and roll them up — nothing
here re-discovers a project, re-executes a request, or recomputes a metric
Phase 2-4 already produced.

### 9.1 Pipeline

```text
discovery.discover()                      -> ProjectModel        (always runs)
adapters/rest/adapter.py::run(dry_run=…)  -> RestRunResult        (target optional; generation always attempted)
adapters/rest/performance.py + testing/performance/runner.py
                                           -> PerformanceResult    (only with --performance, opt-in)
        |
        v
assessment/engine.py::build_assessment()  -> ProjectAssessment
        |
        v
reporting/{json,markdown,html}_report.py  -> report.json / report.md / report.html
```

### 9.2 Domain model (`assessment/models.py`)

Deliberately reuses existing enums instead of inventing new ones:
`AssessmentStatus` (`PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED`, defined since
Phase 1) for `AssessmentCategory`/`AssessmentFinding` status, and
`Severity` for finding severity — status and severity answer different
questions and are never conflated (Phase 5 brief §6). Individual functional
`TestResult`s keep using `ResultStatus` (including `SKIPPED`) exactly as
Phase 3 left them; nothing here changes that.

`AssessmentFinding` (id, category, status, severity, confidence, title,
description, evidence, recommendation) → `AssessmentCategory` (name,
status, summary, reason, findings, evidence) → `ProjectAssessment`
(metadata, `overall_status`, categories, coverage, unassessed,
recommendations, limitations, warnings). All plain dataclasses with
`to_dict()`, same convention as every other phase's models.

### 9.3 Overall-status rule (`assessment/rules.py`) — no magic numbers

```text
FAIL     > WARNING > UNKNOWN > PASS
```

`NOT_ASSESSED` categories are excluded from the vote entirely — a missing
target or disabled performance testing must never push the project toward
FAIL/WARNING/UNKNOWN, and must never count as a silent PASS either. If
*every* category is `NOT_ASSESSED`, the overall result is `UNKNOWN` (nothing
could be judged), not `PASS`. This exact priority order matches the Phase 5
brief §5's own listed order; see `tests/assessment/test_rules.py` for
exhaustive coverage (every pairwise combination, not just the headline
cases) and `rules.py`'s docstring for the full rationale.

A second shared rule, `execution_health_status(total_attempted,
total_transport_failed, total_check_failed)`, is used by *both* Functional
Health and Performance (§9.4) since they ask the same question — "did
execution work, and did what ran pass its checks" — with the same ladder:
`UNKNOWN` (nothing attempted) → `FAIL` (every attempted request failed at
the transport layer — the target itself looks unreachable) → `WARNING`
(some transport or check failures, not a total wipeout) → `PASS`. A target
that's completely unreachable is a stronger, more specific signal than "some
assertions didn't pass," which is why it's the one case that reaches `FAIL`
rather than capping at `WARNING` — verified by
`test_unreachable_target_is_functional_fail` (a real connection failure via
a bind-then-close probe socket, not a mock).

### 9.4 Category assessors

Seven categories (Phase 5 brief §2), each a small pure function taking
already-computed Phase 2-4 results:

- **Project Discovery** / **Build / Project Health** / **Test
  Infrastructure** (`discovery_assessment.py`): read `ProjectModel`
  directly. A discovered language/project-type/build-system/test-framework
  with `DetectionConfidence.DETECTED` evidence passes; `INFERRED`-only
  evidence or nothing found downgrades to `WARNING`/`UNKNOWN` — same
  DETECTED-vs-INFERRED distinction Phase 2 already made, just read here
  rather than re-derived.
- **Testability** (`testability_assessment.py`, Phase 5 brief §11): answers
  "how easy would this be to test right now," never "is this code good."
  Six signals (API spec, test framework, test directories, Docker fixture,
  explicit target, database testability) each rated
  GOOD/PARTIAL/NONE/PROVIDED/UNKNOWN/NOT_ASSESSED; category status is
  `PASS` (≥2 good signals) / `WARNING` (1) / `UNKNOWN` (0) — **capped, never
  reaches `FAIL`**, since poor testability is a limitation to report, not a
  defect to fail the project over.
- **Functional Health** (`functional_assessment.py`): aggregates Phase 3's
  `RunResult.summary` counts (passed/failed/error/skipped/unknown) through
  `execution_health_status()`. `NOT_ASSESSED` when `run_result is None`
  (`--target` wasn't given, or generation failed for a graceful reason —
  see §9.5).
- **Performance** (`performance_assessment.py`): aggregates Phase 4's
  `PerformanceResult` levels the same way, plus one `WARNING`-severity
  finding per `FAIL`ed threshold (never escalated past `WARNING` at the
  category level purely for a threshold breach — matches the Phase 5
  brief's own worked example exactly: P95 FAIL + error-rate PASS →
  "Overall: WARNING", not FAIL). `NOT_ASSESSED` when performance wasn't
  opted into (see §9.6).
- **Configuration Hygiene** (`configuration_assessment.py`): one `WARNING`
  finding per `SecretFinding` from Phase 2 (capped at 25, with a truncation
  note beyond that), **never `FAIL`** — a pattern match is evidence of a
  pattern, not a confirmed secret (same principle as Phase 2's own
  `discovery.secrets`). The matched *value* was never captured anywhere
  upstream (`SecretFinding` doesn't have a value field at all — Phase 2
  design), so there is nothing for this layer to leak even by mistake.

### 9.5 Functional/Performance are always attempted, never forced

`assess` always calls `adapters/rest/adapter.py::run()` (Phase 3, unmodified)
to *generate* functional tests regardless of whether `--target` was given —
so the user always sees what would run — and only *executes* when a target
exists and `--dry-run` wasn't passed. Every way generation/execution can be
withheld becomes a specific `functional_not_run_reason` string surfaced
verbatim in the report (`NoSpecFoundError`/`MultipleSpecsFoundError`/no
target/`--dry-run`) rather than `assess` crashing or silently producing an
empty category — this is the phase-level version of the "one failure
doesn't abort the whole thing" pattern from Phase 2's `discovery.engine`.

### 9.6 Performance is opt-in, with the same safety gate as the standalone command

`--performance` must be passed explicitly; without it (or without
`--target`, or with `--dry-run`), Performance is `NOT_ASSESSED` with a
specific reason and **zero requests are ever sent** — verified end-to-end
by `test_default_run_sends_no_network_traffic_and_succeeds`. When
`--performance` *is* given, `assess` reuses the exact same endpoint
resolution (`adapters/rest/performance.py`), safety-bounded profile
construction (`testing/performance/planner.py`), and interactive
confirmation-or-`--yes` gate as the standalone `performance` command — the
Phase 5 brief's safety principles are not relaxed just because this is a
sub-step of a larger command (§20: "安全原則不能降低").

### 9.7 Coverage & Unknown/Not-Assessed (`assessment/engine.py`)

Five fixed coverage items (Discovery, API Discovery, Functional Execution,
Performance Execution, Database) — not a per-detector percentage, since a
finer breakdown would imply false precision. `Functional Execution`'s
percent is `executed / generated_count`; the rest are binary (100%/0%) with
a `reason` string when 0%. `Database` is 100% when `--database-profile`
successfully connected (Phase 6), and 0% with a specific reason otherwise
(no profile given, or connection/discovery failed) — the same "no invented
precision" principle (Phase 5 brief §5) applies here too: a successful
connection doesn't get a finer per-table percentage. `_compute_unassessed()`
always includes "Business logic correctness" (no formal spec exists to
check against, ever) plus whichever of database/auth/functional/performance
prerequisites were actually missing this run.

### 9.8 Reporting (`reporting/`)

`AssessReportBundle` (`reporting/report_bundle.py`) bundles the
`ProjectAssessment` together with the raw `ProjectModel`/`RunResult`/
`PerformanceResult` it was built from, because the Phase 5 brief's JSON
shape (§14) wants `discovery`/`functional`/`performance` as their own
top-level sections (the full Phase 2-4 detail), not just the assessment
rollup — every renderer takes this one bundle.

- **JSON** (`json_report.py`): `schema_version` field present
  (`SCHEMA_VERSION = "1.0"` in `assessment/models.py`); deterministic except
  for `generated_at`, which never feeds assessment logic (Phase 5 brief §17
  — verified by `test_report_generation_is_deterministic`, which renders
  the same bundle twice and diffs the output).
- **Markdown** (`markdown_report.py`): the exact section order from the
  brief §15 (Executive Summary → Project Discovery → Technology Detection →
  Testability → Functional Testing → Performance → Findings →
  Recommendations → Coverage → Unknown/Not Assessed → Limitations →
  Execution Information). "Technology Detection" reads `ProjectModel`
  directly (languages/frameworks/databases/infrastructure with confidence)
  rather than from the assessment categories, since it's raw evidence
  display, not a judgement.
- **HTML** (`html_report.py`): plain string templates, **no `Jinja2`**
  dependency added (deferred per §2's original Phase 1 rationale — still
  true, a templating engine isn't needed for one moderate-complexity static
  page) — no CDN, no external JavaScript, opens directly from disk. Every
  piece of scanned-project-derived text (finding titles/descriptions,
  evidence values, file paths) goes through stdlib `html.escape()` before
  insertion, since that content originates from the target repository, not
  from this tool — verified by `test_html_escapes_finding_content` with a
  `<script>` tag embedded in a fixture's secret-finding file path.

### 9.9 CLI default output location

`assess` defaults `--format` to `all` (json+markdown+html together, via
`subparser.set_defaults(format="all")` after the shared `--format` flag is
added) — the only subcommand that does. When `--output` isn't given and all
three formats are being produced, they're written to `./reports/` (the
directory `pyproject.toml`'s packaging layout already reserved for exactly
this since Phase 1, previously just a placeholder `.gitkeep`). A single
explicitly-requested format with no `--output` still prints to stdout, same
as every other command.

## 10. Read-Only Database Adapter (`adapters/database/`, Phase 6 — implemented)

`adapters/database/adapter.py::discover(profile: DatabaseProfile) ->
DatabaseDiscoveryResult` is the entry point `universal-test database` and
`assess`'s "Database Health" category call. Discovering database *evidence*
in a project (Phase 2's `discovery.database`) never implies permission to
connect to it — connection only happens when the user supplies an explicit
`--database-profile <path>` (Phase 6 brief §4); nothing here is ever derived
from what `scan` found.

### 10.1 No arbitrary SQL execution — the primary safety mechanism

`adapters/database/base.py::DatabaseDriver` is an `ABC` with **no
`execute(sql)` method anywhere in its contract** — only fixed, read-only
metadata operations: `get_server_version/get_database_name/list_schemas
/list_tables/list_views/list_columns/get_primary_key/list_foreign_keys
/list_indexes/get_safe_row_count/close`. Per the Phase 6 brief §7/§19
("根本不提供 arbitrary SQL execution"), the safety boundary is that the
capability to run app-controlled SQL simply does not exist in this module —
not a `DROP`/`DELETE`/`UPDATE` keyword blocklist bolted onto a generic
executor after the fact, which would be a weaker guarantee.

### 10.2 Profile, credentials, and the read-only-by-default refusal

`adapters/database/profile.py::load_database_profile()` parses a YAML file
matching `skill.md`'s `database:` shape (`engine, host/port/database` or
`path` for SQLite, `credentials.username_env/password_env`,
`readonly`). Two hard requirements enforced at load time, not left to
convention:

- `database.readonly` must be the literal boolean `true`; anything else
  (missing key, `false`, a string) raises `ConfigurationError` and refuses
  to connect — "拒絕執行，而不是假設安全" (brief §6). There is no code path
  that connects with `readonly` unset.
- Credentials are read only from named environment variables
  (`username_env`/`password_env`, same convention as `adapters/rest/auth.py`'s
  `--bearer-token-env`) — never taken directly from the profile YAML, so a
  password is never sitting in a file that might get committed.

`DatabaseProfile.to_dict()` (used everywhere a profile is echoed back —
CLI plan output, assessment evidence, JSON/Markdown/HTML reports) exposes
only connection-identifying fields plus a boolean `credentials: "configured"
/ "not configured"` — the actual username/password are never dataclass
fields that could accidentally be serialized (brief §5's stronger
recommendation: "更理想的是報告根本不要列 username/password").

### 10.3 Engines and optional dependencies

| Engine | Driver | Dependency |
|---|---|---|
| SQL Server | `sqlserver.py` | `pyodbc` (optional extra; also needs an OS-level ODBC driver) |
| PostgreSQL | `postgresql.py` | `psycopg2-binary` (optional extra) |
| MySQL | `mysql.py` | `mysql-connector-python` (optional extra) |
| SQLite | `sqlite.py` | stdlib `sqlite3` only — always available |

`pyproject.toml`'s `[project.optional-dependencies].database` group lists
all three server drivers; none is a hard dependency of the package. Each
driver module does its own `import pyodbc`/`import psycopg2`/`import
mysql.connector` **lazily, inside its own module** — Core, Discovery, the
REST adapter, Performance, and Assessment all import and run correctly with
zero database drivers installed (mirroring the dependency direction diagram
in the Phase 6 brief §3: `Core -> Database Adapter -> {driver}`, never
`Core -> pyodbc`). A missing driver raises
`DatabaseDriverUnavailableError` from inside the engine-specific
constructor, caught by `adapter.py::discover()` and turned into
`NOT_ASSESSED` with reason "Database driver is not installed" — never an
uncaught `ImportError` surfacing elsewhere in the tool.

SQLite is deliberately kept separate from the three server-based drivers
(brief §2): no network connection, no `DatabaseCredentials`, opened via the
read-only URI form `file:<path>?mode=ro` (`sqlite3.connect(uri, uri=True)`)
so the connection itself is incapable of writing regardless of which
queries this module happens to issue — not just a convention, a driver-level
guarantee (brief §11).

PostgreSQL and SQL Server both exclude their engines' built-in system
schemas (`information_schema`/`pg_catalog` for Postgres;
`sys`/`INFORMATION_SCHEMA`/the `db_*` built-in roles for SQL Server) from
`list_schemas()`, so an application's own tables aren't buried under
platform internals unless a schema is genuinely part of the application
(brief §9).

### 10.4 Normalized model (`adapters/database/models.py`)

`DatabaseInfo` (`engine: DatabaseEngine, server_version, database_name,
schemas: list[DatabaseSchema], warnings`) composes `DatabaseSchema` →
(`DatabaseTable`/`DatabaseView`) → `DatabaseColumn`/`PrimaryKey`
/`ForeignKey`/`DatabaseIndex`/`RowCountEstimate` — all plain dataclasses
with `to_dict()`, same convention as every other phase's model. The
assessment layer only ever sees these; no `pyodbc`/`psycopg2`/`mysql
.connector`/`sqlite3` cursor or row object crosses out of
`adapters/database/`.

`base.py::discover_database(engine, driver) -> DatabaseInfo` walks a
connected driver's metadata: one table's or view's metadata query failing
is caught and recorded in `DatabaseInfo.warnings` rather than aborting the
whole scan (same "one failure doesn't abort the batch" pattern as Phase 2's
`discovery.engine` and Phase 3's endpoint parsing). A schema with more than
`MAX_TABLES_PER_SCHEMA` (200) tables is truncated with a warning rather than
scanning an unbounded number of tables in one unfamiliar database (brief
§20's spirit — don't let one large schema make a scan unbounded).

### 10.5 Safe row counts (`RowCountEstimate`)

Each driver's `get_safe_row_count()` prefers a catalog/metadata-based
estimate (SQL Server `sys.dm_db_partition_stats`/`sys.partitions`,
PostgreSQL `pg_stat_user_tables.n_live_tup` /
`pg_class.reltuples`, MySQL `information_schema.tables.table_rows`, SQLite
`sqlite_stat1` when `ANALYZE` has been run) over `SELECT COUNT(*)`, which
can be expensive on a large, unfamiliar table (brief §15). `value: int |
None` — `None` means "could not be safely determined," never "the table is
empty"; `method` records which strategy produced the value
(`catalog_estimate`/`unavailable`), and `confidence` is
`DetectionConfidence.INFERRED` for an estimate, never `DETECTED` (an
estimate is not an exact count).

### 10.6 Timeouts and error classification

`core/errors.py` adds `DatabaseError(AdapterError)` →
`DatabaseDriverUnavailableError`, `DatabaseConnectionError`,
`DatabaseTimeoutError` (additive only). Every driver applies
`profile.connect_timeout_seconds`/`query_timeout_seconds` at connection
time (each engine's native timeout mechanism —
`pyodbc`'s `timeout`, `psycopg2`'s `connect_timeout`, the MySQL connector's
`connection_timeout`, `sqlite3.connect(..., timeout=...)`). A connection
timeout or refusal is caught by `adapter.py::discover()` and reported as
`NOT_ASSESSED` with a specific reason — never as a `Database Health: FAIL`,
since an unreachable/slow database server is an access/environment
condition, not evidence the assessed project's database is broken (brief
§16).

### 10.7 Assessment integration (`assessment/database_assessment.py`)

An eighth category, "Database Health," alongside the existing seven from
Phase 5. `assess_database_health(result: DatabaseDiscoveryResult | None)`:
`result is None` (no `--database-profile` given) or `result.info is None`
(connection/discovery failed) both resolve to `NOT_ASSESSED` — never
`FAIL`, matching the same "connectivity problems aren't the project's
fault" principle as §10.6. When metadata *was* successfully collected,
status is `PASS`/`WARNING` (only on discovery warnings, e.g. a truncated
schema) /`UNKNOWN` (zero tables and views found) — **never `FAIL`**, since
a schema-level observation (missing primary keys, zero foreign keys) is
evidence to report, not a defect verdict (brief §13: "不要把「沒有 foreign
key」直接判定成 database defect" — verified by
`test_zero_foreign_keys_is_info_not_fail`/similar in
`tests/assessment/test_database_assessment.py`). `database_testability_signal()`
feeds Phase 5's existing "Database testability" row in
`testability_assessment.py` with one coarse `GOOD/PARTIAL/NOT_ASSESSED/NONE`
value, keeping the detailed schema breakdown in this category instead of
duplicating it.

### 10.8 CLI and dry-run (`cli/main.py`)

`universal-test database <path> --database-profile <path> [--dry-run]
[--format text|json|markdown] [--output PATH]`. Omitting
`--database-profile` refuses outright (exit 2) with the exact reasoning
from §10 above, rather than attempting any connection. `--dry-run` calls
only `adapters/database/serializers.py::plan_to_text()` — engine,
host/path, the fixed list of read-only operations that would run, "Mode:
READ ONLY" — and never constructs a driver or opens a socket/file handle at
all (verified: `test_dry_run_never_connects`). `assess` gains
`--database-profile` as an opt-in flag (mirroring `--performance`'s opt-in
pattern from Phase 5): omitted, `Database Health` is `NOT_ASSESSED` with
reason "database credentials/access were not explicitly configured" and
zero connection attempts are made — matching `assess`'s existing
zero-traffic-by-default guarantee for functional/performance testing.

### 10.9 Reporting integration (`reporting/`)

`AssessReportBundle` (`reporting/report_bundle.py`) gained a
`database_result: DatabaseDiscoveryResult | None` field alongside the
existing `discovery`/`functional`/`performance` sections.
`json_report.py` emits a `database` top-level key (`null` when no profile
was given or connection failed — never fabricated data);
`markdown_report.py`/`html_report.py` render the "Database Health" category
the same way every other category is rendered, plus the schema/table/view
breakdown when `info` is present. No credential ever reaches any of these
three renderers — `DatabaseProfile.to_dict()` (§10.2) is structurally
incapable of holding one.

## 11. Regression / Baseline Comparison Engine (`regression/`, Phase 7 — implemented)

`regression/` answers a question Phase 5's `assess` alone cannot: not just
"what does this project look like now" but "did it get worse since last
time". It never re-discovers, re-executes, or re-connects to anything
itself — it only compares two already-built snapshots, mirroring how
`assessment/engine.py::build_assessment()` only aggregates Phase 2-4
results rather than recomputing them (Phase 7 brief's own framing).

### 11.1 Pipeline

```text
cli/main.py::_run_pipeline()          -> (model, run_result, perf_result, database_result, ...)
                                          (the exact same discovery+functional+performance+database
                                           pipeline 'assess' already runs — factored out in this phase
                                           so 'assess', 'baseline save', and 'baseline compare' share
                                           one implementation, not three copies)
assessment/engine.py::build_assessment()  -> ProjectAssessment   (unmodified Phase 5 code)
regression/snapshot.py::build_snapshot()  -> BaselineSnapshot    (compacts the above into the persisted/compared shape)
        |
        +-- 'baseline save'  --> regression/baseline_store.py::save_baseline()  -> baseline.json
        |
        +-- 'baseline compare' / 'assess --baseline'
                 |
                 v
        regression/baseline_store.py::load_baseline()  -> BaselineSnapshot (the *old* one, read-only)
                 |
                 v
        regression/engine.py::compare(baseline, current, performance_thresholds)  -> RegressionSummary
```

### 11.2 `BaselineSnapshot` — what gets persisted (brief §2/§3)

`regression/models.py::BaselineSnapshot`: `schema_version, tool_version,
generated_at, project_path, source (git commit/branch/dirty),
discovery (detected item names per category), functional (per-test-ID
status list + aggregate counts), performance (per-concurrency-level
metrics), database (per-table column/PK/FK-count/index-count metadata),
assessment (per-category status)` — every field the brief's §2 explicitly
lists, never just an overall status string. All-plain-dataclass,
`to_dict()`/`from_dict()`, same convention as every prior phase's model.
Source revision (git commit/branch) is captured but is deliberately **not**
the baseline's identity — comparison always proceeds by loading the file
the user pointed `--baseline` at, never by trying to look up "the baseline
for commit X" (brief §2: "Git information 不應該是 baseline comparison 的唯一
identity").

`snapshot.py::build_snapshot()` builds one from the same
`ProjectModel`/`RunResult`/`PerformanceResult`/`DatabaseDiscoveryResult`
/`ProjectAssessment` objects `build_assessment()` already consumed —
compacted (table columns as sorted name lists, not full `DatabaseColumn`
objects; discovery items as name sets, not full `Evidence` chains) so a
baseline file stays a reasonable size without losing what's needed to
detect table/column additions, removals, or per-test-ID transitions.

### 11.3 Storage and immutability (brief §3/§4)

`regression/baseline_store.py`: `save_baseline(snapshot, path)` writes
indented JSON to the caller-controlled `--output` path — storage location
is always explicit, never a hidden default directory (unlike `assess`'s
`./reports/` default; a baseline file is meaningful to keep around
long-term under a name the user chose, e.g. checked into version control).
`load_baseline(path)` only ever reads — **no code path in this package
ever writes to a file it loaded** (`baseline compare` and `assess
--baseline` both call `load_baseline()` and nothing else touches that
path). Verified by `test_load_never_writes_back_to_the_file`
(`tests/regression/test_baseline_store.py`) and a CLI-level byte-for-byte +
mtime check (`test_compare_is_read_only_never_modifies_the_baseline_file`).

### 11.4 Schema-version compatibility (brief §18)

`load_baseline()` requires `schema_version` to be in
`_SUPPORTED_SCHEMA_VERSIONS` (currently `{"1.0"}`) or raises
`RegressionError` immediately — an unsupported version is refused outright,
never partially parsed or guessed at. A **tool**-version mismatch (as
opposed to schema-version) is not an error: `regression/engine.py::compare()`
records both `baseline_meta.tool_version` and `current_meta.tool_version` in
the output and adds a `warnings` entry when they differ, so a reader can see
both — the brief's distinction between "refuse" (schema) and "note" (tool
version) is implemented as two different code paths, not one blanket rule.

### 11.5 Comparison model (brief §5) and the severity rule (brief §14)

`ChangeType`: `ADDED/REMOVED/CHANGED/IMPROVED/REGRESSED/UNCHANGED
/NOT_COMPARABLE` — `ADDED`/`REMOVED` are never themselves a regression
verdict (brief §7: "不要直接判定 removed test 為 regression"); missing data on
either side of a comparison is `NOT_COMPARABLE` at the metric level or
`AssessmentStatus.NOT_ASSESSED` at the category level, never treated as a
regression (brief §5).

`RegressionCategory`/`RegressionFinding`/`MetricDelta` deliberately mirror
`assessment/models.py`'s `AssessmentCategory`/`AssessmentFinding` shape
(same JSON/Markdown/HTML consumer contract) rather than inventing a
parallel vocabulary — `RegressionFinding` is keyed by `change: ChangeType`
instead of `status: AssessmentStatus` since a regression finding answers
"what changed", not "did this pass".

`regression/rules.py::status_from_findings()` is the **one** place severity
becomes a category status (brief §14, applied literally, no invented
scoring):

```text
CRITICAL/HIGH present -> FAIL
MEDIUM/LOW present    -> WARNING
otherwise              -> PASS
```

Every comparator (§11.6-11.9) calls this same function — none of them
computes a category status independently, the same "one canonical rule,
not five bespoke ladders" pattern `assessment/rules.py::compute_overall_status()`
already established for Phase 5. The overall `RegressionSummary.status` is
computed by **reusing** `assessment/rules.py::compute_overall_status()`
directly against the five category statuses (`FAIL > WARNING > UNKNOWN >
PASS`, `NOT_ASSESSED` excluded from the vote) — zero new overall-status
logic was written for Phase 7.

### 11.6 Functional regression (`functional_compare.py`, brief §6/§7)

Compares by **test ID**, not just aggregate counts (brief §7: "這一點非常重要"):
`PASSED -> FAILED/ERROR` is `REGRESSED` (`Severity.HIGH`); `FAILED/ERROR ->
PASSED` is `IMPROVED` (no finding — brief only asks for findings on
regressions, not on every improvement); `PASSED -> SKIPPED/UNKNOWN` is
`CHANGED` (`Severity.MEDIUM` — coverage got worse, but it isn't a hard
failure); an unchanged status (including an unchanged *failure* — brief §6's
worked example: baseline failed=2, current failed=2 -> no new finding) never
produces a finding; a test ID present in only one snapshot is `ADDED`/
`REMOVED` with no finding at all. Aggregate count deltas (`passed_count`,
`failed_count`, etc.) are also recorded as `MetricDelta`s for the report,
alongside the per-test findings — both levels of detail the brief asks for,
not one instead of the other.

### 11.7 Performance regression (`performance_compare.py`, brief §8/§9/§10)

Matched **by concurrency level** (a level present in only one run is noted,
not scored — comparing across different concurrency levels would compare
unlike things). Every tolerance is a parameter (`thresholds: dict[str,
float]`) — the comparator itself contains no hard-coded percentage (brief
§8: "不要 hard-code 5%/10% 到比較器"); `core/configuration/config.py`'s
`RegressionConfig.performance` supplies the *default* value
(`p50/p90/p95/p99_percent=10.0, rps_percent=10.0,
error_rate_absolute=1.0`) used when a project's own `universal-test.yaml`
doesn't override it — without some non-zero default, ordinary measurement
noise (P95 200ms -> 202ms) would be flagged as a regression on every run
(brief §10's explicit noise-tolerance concern).

Metric direction is explicit per metric, not inferred from "current >
baseline" uniformly (brief §9): latency (P50/P90/P95/P99) and error rate
are `lower_is_better` (a *positive* percent/absolute delta beyond tolerance
is a regression); RPS is `higher_is_better` (a *negative* percent delta
beyond tolerance is a regression). Error rate uses an **absolute**
(percentage-point) tolerance rather than a percent-of-baseline one,
since a percent-of-zero baseline error rate is undefined — exactly the
"zero baseline value" edge case the brief's own test list calls out (§21).
A `None` baseline or current value (level missing, or a percent-based
metric with a zero baseline) is `NOT_COMPARABLE`, never treated as a
regression by a stray zero.

### 11.8 Database regression (`database_compare.py`, brief §11)

Every finding here is `Severity.INFO` by construction — `status_from_findings()`
can therefore never push this category past `PASS`, which is the concrete
mechanism behind the brief's "不要把 schema change 自動判定成 defect": a table or
column added/removed, or a foreign-key/index count change, is reported for
visibility, never scored as a defect. Compares Phase 6's normalized model
(table names, column name sets, PK columns, FK/index counts) — the same
compact representation `BaselineSnapshot.database` stores. Phase 7's first
version has no "baseline policy" configuration to opt into stricter
database-schema enforcement (brief §11's last line: "只有在有明確 baseline
policy 時才判定 regression") — not built, since nothing in the brief specifies
its shape; a real candidate to design explicitly in a later phase rather
than guessed at here.

### 11.9 Discovery regression (`discovery_compare.py`, brief §12)

Same INFO-only-severity mechanism as §11.8: a detected language/framework/
database/API/test-framework/infrastructure item appearing or disappearing
between two scans is always `CHANGED`-severity-`INFO`, never `FAIL` — very
plausibly a configuration change (a database driver removed from
`requirements.txt`, a new framework adopted), not a defect. This category
is never `NOT_ASSESSED`: discovery always runs as part of the pipeline, on
both sides of every comparison.

### 11.10 Assessment-category regression (`assessment_compare.py`, brief §13)

Compares each Phase 5 category's status (`Functional Health`,
`Performance`, `Database Health`, etc.) by name between baseline and
current — not just the single overall status (brief §13: "但不要只依 overall
status"). The three worsening transitions the brief names explicitly get
the brief's exact severities: `PASS -> WARNING` = `MEDIUM`, `PASS -> FAIL` =
`HIGH`, `WARNING -> FAIL` = `HIGH`. Any transition involving `UNKNOWN`/
`NOT_ASSESSED` on either side is skipped entirely (missing/undecided data
isn't a regression, brief §5) and an improving transition produces no
finding. Underlying evidence for *why* a category changed status stays in
that run's own `report.json` (already produced by `assess`) — this
comparison only tracks the transition itself, not a duplicate copy of every
finding.

### 11.11 No numeric quality score (brief §15)

Nothing in this package computes or stores a number like "baseline score =
82, current = 75, regression = -7" — `RegressionSummary.status` is one of
`PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED`, exactly the vocabulary Phase 5
already established, for the same reason Phase 5 itself has no score
(ARCHITECTURE.md §9.3, §14 assumption 20/21's "no invented precision"
principle extended here rather than re-litigated).

### 11.12 CLI and safety (brief §16/§17)

`universal-test baseline save <path> --output baseline.json [--target ...]
[--performance ...] [--database-profile ...]` and `universal-test baseline
compare <path> --baseline baseline.json [same flags]` share every flag
`assess` has via a common `_add_pipeline_args()` (`cli/main.py`) — the exact
same OpenAPI/auth/performance/database flags, not a parallel or looser set.
`assess` itself gains an opt-in `--baseline <path>` flag that attaches a
`regression` section to the unified report using the *current* run's
already-computed pipeline results, without executing anything a second
time.

Critically, **neither `baseline save` nor `baseline compare` executes
anything beyond what the shared pipeline would already do for `assess`**
(brief §17: "不要偷偷對 remote target 執行 tests") — functional tests only run
with an explicit `--target`, performance only with `--target` **and**
`--performance` (plus the same interactive confirmation/`--yes` gate Phase
4/5 already established), a database connection only with
`--database-profile`. `baseline compare` without `--target` produces a
`Functional: NOT_ASSESSED` regression category and sends zero HTTP
requests — verified end-to-end
(`test_compare_without_target_sends_no_network_traffic`). There is no
separate, weaker safety story for baseline commands; they reuse the exact
mechanism, not a re-implementation of it (`cli/main.py::_run_pipeline()`
is one function, not three near-duplicates — extracted from the pre-Phase-7
`_run_assess()` body specifically so `assess`/`baseline save`/`baseline
compare` cannot silently drift apart).

### 11.13 Reporting integration

`reporting/report_bundle.py::AssessReportBundle` gained a
`regression: RegressionSummary | None` field. `json_report.py` emits a
`regression` top-level key (`null` when no `--baseline` was given).
`markdown_report.py`/`html_report.py` render a "Regression" section
(status, baseline/current metadata, one block per category with its
findings) using the same rendering conventions — status badges, HTML-escaping
via `html.escape()` — every other section already uses; nothing new was
invented for this one section. The standalone `baseline compare` command's
own `regression/serializers.py` renders the identical `RegressionSummary`
model for its own text/json/markdown output, so the two presentations never
drift into different vocabularies for the same data.

## 12. Quality Gate (`quality_gate/`, Phase 8 — implemented)

```text
Assessment + Regression -> QualityGate Engine -> ExitCode -> CI Adapter/Template
```

`quality_gate/` is CI-provider-independent by construction — no GitHub
Actions/GitLab/Jenkins/Azure Pipelines logic exists anywhere in this
package or in Core (Phase 8 brief §1). Every provider-specific concern
lives in `examples/ci/*` templates (§12.7), which only ever shell out to
the plain `universal-test` CLI.

### 12.1 One evaluation function, no scattered policy

`quality_gate/engine.py::evaluate(assessment, regression, policy) ->
QualityGateResult` is the entire policy-application logic — no other
module re-implements any part of the fail/warn/pass/error decision (brief
§2: "不要 hard-code policy"). Two-step design, deliberately factored so each
half is independently testable:

```text
quality_gate/signals.py::collect_rules(assessment, regression)
    -> (infra_signals: list[QualityGateRule], quality_signals: list[QualityGateRule])
       (collection: "what happened", reading only the already-built
        ProjectAssessment/RegressionSummary — never re-discovers,
        re-executes, or re-compares anything)

quality_gate/engine.py::evaluate(...)
    -> classifies each signal against a QualityGatePolicy.fail_on/warn_on
       ("does policy care") -> QualityGateFinding list -> QualityGateResult
```

### 12.2 Domain model (`quality_gate/models.py`)

`QualityGateStatus`: `PASS/WARNING/FAIL/ERROR` — `ERROR` is deliberately
distinct from `FAIL` (§12.4). `ExitCode` (`IntEnum`): `QUALITY_GATE_PASSED
=0, QUALITY_GATE_FAILED=1, CONFIGURATION_ERROR=2, EXECUTION_ERROR=3` — the
brief's exact contract (§4), one mapping (`exit_code_for()`) from status to
code, never duplicated inline. `QualityGatePolicy` (`fail_on`/`warn_on:
dict[str, list[str]]`) is deliberately decoupled from
`core.configuration.config.QualityGateConfig` (which only exists to load
this shape from `universal-test.yaml`) — the same separation
`regression/performance_compare.py` already has from `RegressionConfig`,
so the evaluator's tests never need a `Config` object. `QualityGateRule`
(a collected signal, pre-classification) and `QualityGateFinding` (a
signal policy actually flagged, with a resolved `level`) are intentionally
two different shapes — `signals.py` only produces the former, `engine.py`
only the latter.

### 12.3 Rule vocabulary (brief §8's minimum list, all present)

| Category | Value | Source | Default |
|---|---|---|---|
| `regression` | `critical`/`high`/`medium`/`low`/`info` | `RegressionFinding.severity` (Phase 7, reused as-is — no new severity vocabulary) | `critical`/`high` → fail; `medium` → warn |
| `functional` | `failure` | Functional Health category == `WARNING` (a real assertion/check failure occurred against a live target) | fail |
| `functional` | `unreachable` | Functional Health category == `FAIL` (total transport wipeout) | not in default policy — see §12.4 |
| `performance` | `threshold` | Performance category == `WARNING` (threshold breach or partial failure, live target) | fail |
| `performance` | `unreachable` | Performance category == `FAIL` (total transport wipeout) | not in default policy — see §12.4 |
| `database` | `not_assessed` | Database Health category == `NOT_ASSESSED` | not in default policy (brief §9) |
| `database` | `schema_change` | Regression's `Database` category has findings | warn |
| `discovery` | `change` | Regression's `Discovery` category has findings | warn |
| `assessment` | any `AssessmentStatus` value | `ProjectAssessment.overall_status` | not in default policy (opt-in catch-all) |

Every rule maps directly onto data Phase 5/6/7 already compute — no new
counting or re-derivation. A value not listed in either `fail_on` or
`warn_on` is neither a failure nor a warning (brief §9): the default policy
deliberately omits `unknown`/`not_assessed`/`skipped`-adjacent values
everywhere, so `NOT_ASSESSED`/`UNKNOWN` never auto-fail a build.

### 12.4 `ERROR` vs. `FAIL` — infrastructure failure is not a quality regression (brief §18)

The single most important design decision in this phase.
`assessment/rules.py::execution_health_status()` (Phase 5, unmodified) already
distinguishes two very different situations under one category status:

- **`WARNING`**: some requests transported fine and returned a response,
  but a check/assertion/threshold didn't pass — a genuine quality signal.
- **`FAIL`**: *every* attempted request failed at the transport layer — the
  target itself looks unreachable, not "the software has a bug".

`quality_gate/signals.py` reads this distinction directly: a `WARNING`
status becomes a normal quality signal (`functional.failure`/
`performance.threshold`, eligible for the usual fail_on/warn_on
classification); a `FAIL` status becomes an **infra signal**
(`functional.unreachable`/`performance.unreachable`), tagged
`is_infra_signal=True`. `engine.py::evaluate()` checks each infra signal
against the policy: if the policy does **not** explicitly list that exact
`(category, value)` pair, the signal short-circuits the entire result to
`QualityGateStatus.ERROR` / `ExitCode.EXECUTION_ERROR` (3) — overriding
whatever the ordinary fail/warn/pass findings would have computed, since
"the target was unreachable" undermines confidence in everything else that
run measured. A project that explicitly opts a value like
`functional: [unreachable]` into `fail_on`/`warn_on` gets the brief's
literal escape hatch ("除非 user explicitly configures otherwise" — §18's
last line): that signal is instead treated as an ordinary quality finding,
contributing to a normal FAIL/WARNING result rather than short-circuiting
to `ERROR`.

Database Health never needs an equivalent `unreachable` signal: Phase 6
already designed it to cap at `NOT_ASSESSED`/`WARNING`/`PASS` and never
reach `FAIL` (ARCHITECTURE.md §10.7) — there is no transport-wipeout state
to distinguish there in the first place.

### 12.5 Configuration (`core/configuration/config.py`)

`QualityGateConfig` (`fail_on`/`warn_on: dict[str, list[str]]`, safe
defaults matching brief §3 exactly) registered in `Config`/`_SECTION_TYPES`
the same way `RegressionConfig` was in Phase 7. The nested-dict-merge fix
`_build_section()` gained in Phase 7 (ARCHITECTURE.md §11's testing note)
applies here for free: overriding `fail_on.regression` in
`universal-test.yaml` preserves `fail_on.functional`/`fail_on.performance`'s
defaults rather than dropping them — exercised directly by
`test_quality_gate_nested_policy_merge_keeps_other_categories`.

**New validation** (`_validate_quality_gate_policy()`, called once at the
end of `load_config()`): unlike most other sections, an unrecognized shape
here (`fail_on` not a mapping, a category's value not a list of strings)
raises `ConfigurationError` immediately rather than being tolerated —
because a malformed policy drives CI exit codes directly, a silent
misconfiguration here would surface as a confusing crash deep inside gate
evaluation (or worse, a gate that silently never fails) instead of a clear,
immediate `exit 2` at the CLI.

`CiConfig` (`retry.count`, default `0`, clamped to `MAX_CI_RETRY_COUNT=2`
in `__post_init__` regardless of what's configured — the same "hard
ceiling independent of validation" pattern
`testing/performance/planner.py` established in Phase 4) supports the
brief's `ci: {retry: {count: N}}` shape (§19).

### 12.6 CLI integration (`cli/main.py`)

**Scope decision**: the full Quality Gate + `ExitCode` contract is wired
into `assess` only, not into `scan`/`test`/`performance`/`database`
/`baseline save`/`baseline compare` — every one of the brief's own CI
templates invokes `assess`, which is already the command that aggregates
discovery + functional + performance + database + regression into one
result the gate can evaluate. Retrofitting the other commands' existing
exit-code conventions (mostly `0`/`2` already, established Phases 1-6) is
out of scope per this phase's "不要重新設計 Phase 1–7" instruction; see §15
assumption for the explicit rationale.

`_run_pipeline()` and `_add_pipeline_args()` (extracted from `_run_assess()`
/`_add_assess_args()` in Phase 7 specifically so `assess`/`baseline save`
/`baseline compare` share one implementation) needed **no changes** for
Phase 8's gate itself — only `_run_assess()` gained the gate-evaluation
step after building its `assessment`/`regression`. `_run_pipeline()` did
gain the bounded functional-execution retry (§12.5's `CiConfig`): after
`rest_run()` returns, `_is_total_transport_failure(run_result)` checks the
same "every executed test errored" condition `execution_health_status()`
uses for `FAIL`, and only then retries — a genuine assertion or threshold
failure is never retried (brief §19: "不要用 retry 掩蓋真實 regression").

**`--baseline` load failure is now a configuration error** (a Phase 8
tightening of Phase 7's `assess --baseline` behavior): Phase 7 originally
logged an error and silently continued with `regression=None`; Phase 8
changes this to `ExitCode.CONFIGURATION_ERROR` (2) — still writing a full
report first (so a CI operator can see what happened), but the exit code no
longer papers over a broken `--baseline` reference in an automated
pipeline. `tests/cli/test_cli_baseline_command.py::
test_assess_invalid_baseline_path_does_not_crash` was updated to assert
`exit_code == 2` (was `0`) to match — a deliberate behavior change this
phase's brief calls for (§18's whole point is exactly this kind of
disambiguation), not a lowered test requirement.

**`--ci`** (assess-only flag): forces the interactive-confirmation check in
`_maybe_run_assess_performance()` to treat the session as non-interactive
*even if `sys.stdin.isatty()` reports `True`* (some CI runners attach a
pseudo-tty) — `getattr(args, "ci", False) or not sys.stdin.isatty()`.
Never implies `--yes` (brief §7's explicit requirement, verified:
`test_ci_flag_alone_does_not_authorize_traffic`) — a performance test still
requires `--yes` alongside `--ci` for any real traffic. When set, `_run_assess()`
prints the full structured `quality_gate/serializers.py::result_to_text()`
block instead of two terse status lines; without it, the existing terse
`Overall Status:`/`Quality Gate:`/`Exit code:` lines print (backward
compatible with `test_overall_status_printed_to_stdout`, a pre-existing
Phase 5 test).

**CI environment detection** (`quality_gate/ci_detection.py::
detect_ci_environment()`): checks `GITHUB_ACTIONS`/`GITLAB_CI`
/`JENKINS_URL`/`TF_BUILD`/`CIRCLECI`/`TRAVIS`/`BUILDKITE`/generic `CI`, logs
"Detected CI environment: X" if found. **Purely informational** — verified
end-to-end that setting any of these env vars never substitutes for
`--yes` (`test_ci_env_var_detection_never_auto_authorizes_traffic`,
parametrized over all four brief-named variables) — brief §6's explicit
warning: "不要因為偵測到 CI 就自動放寬 safety".

### 12.7 Reporting integration

`AssessReportBundle` gained `quality_gate: QualityGateResult | None`.
`report.json` gains a `quality_gate` key (brief §10's machine-readable
JSON requirement — no separate output format was needed since the unified
report already carries it). `report.md`/`report.html` gain a "Quality
Gate" section, placed directly under the Executive Summary /
Critical-Findings banner respectively — the headline decision a CI-focused
reader wants first, before the detailed category breakdown. No finding
title/description in this section can carry a secret: they're sourced
exclusively from `AssessmentCategory.summary`/`RegressionFinding.title`
text, which Phase 5/7 already keep credential-free by construction (never
from a raw request/response header or body) — verified end-to-end
(`test_bearer_token_never_appears_in_quality_gate_output`, using a
*wrong* token specifically so a real gate failure occurs and the finding
text is actually populated, not skipped).

### 12.8 CI provider templates (`examples/ci/`, brief §12-15)

Three templates, each a documented starting point rather than a working
pipeline (a project's own build/deploy/service-startup step is always a
placeholder the user fills in — universal-test never assumes a
`localhost` service exists): `github-actions/universal-test.yml`,
`gitlab/universal-test.yml`, `jenkins/Jenkinsfile`. All three:

- Install `universal-test` as a plain `pip install` — no provider SDK, no
  Jenkins-plugin dependency, matching brief §14's explicit instruction not
  to add a Jenkins SDK to Core (none exists anywhere in this project).
- Run `universal-test assess . --ci --yes --target <url> --baseline
  baseline.json --output reports/` and rely on the CLI's own exit code —
  zero extra shell scripting needed to translate "the tool failed" into
  "the build failed" for the common case.
- Upload `reports/` as a build artifact unconditionally (`when: always` /
  `if: always()` / `archiveArtifacts allowEmptyArchive: true`) — a failing
  Quality Gate is exactly the run whose report a reviewer most wants to see
  (brief §15).
- Document, in a comment block, the same "baseline is read-only, update it
  as its own separate deliberate step" rule as ARCHITECTURE.md §11.3 (brief
  §16) — with a concrete example of *how* to update it (a manually-
  triggered or default-branch-only job), never as a side effect of the
  quality-gate job itself.
- `tests/quality_gate/test_ci_templates.py` verifies the two YAML
  templates parse, all three mention `--ci`/`--yes`/`--baseline`, and none
  hardcodes a credential — without ever contacting GitHub/GitLab/Jenkins.

## 13. CLI (`cli/`)

`argparse`-based; the `universal-test` console script resolves to
`cli.main:run` (which calls `main()` and exits with its return code).
Subcommands: `scan, assess, test, performance, database, baseline, report,
run` (`baseline` has its own `save`/`compare` sub-subparsers, added via a
nested `add_subparsers(dest="baseline_command")` on the `baseline`
subparser). `assess` additionally gets `--ci` (Phase 8, §12.6).
`--config/--output/--format/--verbose/--adapter/--target/--dry-run
/--safe-mode` flags are wired for every subcommand. `_add_auth_args` (the 5
`--bearer-token-env`/`--api-key-env`/`--api-key-header`/`--basic-auth-user
-env`/`--basic-auth-pass-env` flags) is shared by `test`, `performance`,
`assess`, `baseline save`, and `baseline compare`. `test` additionally gets
`--openapi/--timeout`; `performance` gets `--openapi/--endpoint/--method
/--profile/--concurrency/--max-concurrency/--requests/--duration
/--stop-error-rate/--stop-p95-ms/--timeout/--yes`. `_add_pipeline_args()`
(Phase 7 — factored out of what was `_add_assess_args()`) bundles that
entire `performance` flag set plus `--performance` (opt-in) and
`--database-profile`, and is shared by `assess`, `baseline save`, and
`baseline compare` — the three commands that all run the same discovery +
functional + performance + database pipeline (§11.12) get it from one
function, not three copies. `assess` additionally overrides `--format`'s
default to `all` via `subparser.set_defaults(format="all")`, and gets an
opt-in `--baseline <path>` on top of `_add_pipeline_args()`; `baseline
compare` gets a **required** `--baseline <path>` (`baseline save` doesn't
take one — it's the command that creates one). `database` gets
`--database-profile`. `scan` (Phase 2), `test` (Phase 3), `performance`
(Phase 4), `assess` (Phase 5), `database` (Phase 6), and `baseline`
(Phase 7) are fully implemented; `report`/`run` still route to a stub that
names the phase that implements them — the CLI must be runnable and honest
about its own limitations rather than silently no-op'ing.

`test`'s target-safety behavior mirrors `performance`'s (skill.md §4.2) but
is deliberately *not* identical: `performance` refuses outright before
doing anything if `--target` is missing (dry-run included — see §8.6),
whereas `test` always runs discovery + generation first (so the user sees
what was found and what would run) and only withholds *execution* if no
target was given — matching the Phase 3 brief's required message: "The
repository was analyzed successfully, but no HTTP requests were executed."
Both still exit non-zero (2) when execution was withheld or refused.

`performance` (and `assess --performance`) reuse
`core.configuration.Config.performance` (defined since Phase 1, unused
until Phase 4): `config.performance.thresholds` from `universal-test.yaml`
are applied automatically if the file exists at the project root — no new
config schema was needed for either phase.

`baseline compare` (and `assess --baseline`) reuse the same pattern for
regression tolerances: `config.regression.performance` (Phase 7 —
`core/configuration/config.py`'s new `RegressionConfig`) supplies
`p50/p90/p95/p99_percent`, `rps_percent`, `error_rate_absolute`, with safe
non-zero defaults (§11.7) so a project needs zero configuration to get
noise-tolerant regression detection, and can override just the thresholds
it cares about — `_build_section()`'s dict-field merge (added in Phase 7;
see §15 assumption 26) means a partial override in `universal-test.yaml`
keeps the rest of the defaults rather than silently dropping them.

`assess` is the only command with a stable, documented `0/1/2/3` exit-code
contract (Phase 8, §12.1/§12.6): `0` = Quality Gate passed (including a
`WARNING`-level result — a warning never blocks a build), `1` = Quality
Gate failed, `2` = configuration error (bad `--format`, unreadable project
path, an invalid or incompatible `--baseline`), `3` = infrastructure/
execution error (the target was completely unreachable — §12.4). Every
other subcommand keeps its pre-existing Phase 1-6 convention (`0`/`2` only,
no `1`/`3`) — deliberately not retrofitted this phase (§15 assumption 31).

## 14. Testing strategy

- `tests/core/` (Phase 1) unit-tests models, config loader, assertion engine
  (including the Phase 3 `jsonschema`-backed `json_schema_valid`),
  orchestrator (with a fake executor), redaction, errors.
- `tests/discovery/` (Phase 2) unit-tests every detector against
  `tests/fixtures/*` plus edge cases: empty repo, unknown/generic project,
  malformed manifest (invalid TOML/JSON — must warn, not crash),
  excluded-directory pollution, nonexistent path, and a real throwaway
  `git init` repo verifying discovery never mutates it.
- `tests/adapters/rest/` (Phase 3) unit- and integration-tests OpenAPI
  parsing (`$ref` resolution, multi-spec ambiguity, invalid/Swagger-2.0
  rejection), request data generation, auth resolution, dry-run (asserts
  `make_executor` is never called at all), and real HTTP execution against
  a fully offline, stdlib-only loopback `http.server` fixture
  (`tests/adapters/rest/fixture_server.py`) — GET/POST success, validation
  failures, schema-validation pass/fail, connection refusal, timeout, and
  auth pass/fail/skip.
- `tests/testing/performance/` (Phase 4) unit-tests the technology-independent
  engine in isolation with a fake in-process executor (no HTTP at all):
  percentile edge cases (0/1/2 samples, identical values, large datasets),
  metrics aggregation (zero samples, all-success, mixed HTTP/network/timeout
  errors, RPS-uses-wall-clock-not-summed-durations), threshold evaluation
  (all pass, one/multiple failures, boundary equality, `NOT_ASSESSED` on
  zero samples, unrecognized-key warning), the runner (concurrency=1 vs >1
  with a measured bounded-concurrency check, duration-mode timing,
  failed/timeout/network-error samples never raising, cancellation, stress
  stop conditions, run timeout), and the planner (every safety ceiling,
  every profile default). `tests/adapters/rest/test_performance_execution.py`
  integration-tests the REST performance executor against the fixture
  server extended with `/fast`, `/error`, `/unstable` (deterministic
  "every Nth request fails") routes, plus a real connection failure via a
  bind-then-close probe socket rather than an OS-specific "unused port"
  assumption. `tests/cli/test_cli_performance_command.py` covers
  missing-target (dry-run included), invalid `--concurrency`/`--duration`
  /`--requests`, `custom`-without-`--concurrency`, `--yes` skipping the
  prompt, and secret redaction.
- `tests/assessment/` (Phase 5) unit-tests the overall-status rule
  exhaustively (every pairwise status combination, not just headline
  cases), `execution_health_status()`'s four-way ladder, and each of the
  seven category assessors independently — discovery-derived categories
  against real fixture projects, functional/performance categories against
  hand-built `RunResult`/`PerformanceResult` objects (no HTTP needed for
  these pure-aggregation units), configuration hygiene's secret-count
  capping/truncation and redaction, testability's signal-counting ladder
  (including the "never reaches FAIL" invariant), and `build_assessment()`
  end-to-end against five dedicated fixtures (`healthy-project`,
  `failed-functional-project`, `slow-project`, `unknown-project`,
  `partial-project`).
- `tests/reporting/` (Phase 5) validates JSON schema-version presence,
  Markdown's exact required section list, HTML's offline-safety (no
  `<script>`, no CDN reference) and HTML-escaping of scanned-project content
  (a `<script>` tag embedded in a fixture's file path must not survive
  unescaped), deterministic output (same bundle rendered twice byte-for-byte
  equal, `generated_at` aside), and secret-pattern redaction across all
  three formats.
- `tests/cli/test_cli_assess_command.py` (Phase 5) integration-tests the
  full `assess` orchestration against the fixture server: default run sends
  zero network traffic, default format writes all three files, a single
  `--format` writes only that file, functional execution against a healthy
  vs. a deliberately-mismatched-response project (PASS/WARNING vs. real
  fixture behavior, not mocked), a genuinely unreachable target reaching
  `FAIL`, performance staying `NOT_ASSESSED` without `--performance`, a real
  threshold breach via `--performance --yes` against the `slow-project`
  fixture with a tight `p95_ms` threshold, an unknown project leaving both
  execution categories `NOT_ASSESSED`, `--dry-run` never executing even
  with a target, bearer-token redaction across all three output files, and
  multi-spec ambiguity degrading to `NOT_ASSESSED` rather than crashing the
  whole command.
- No external network access anywhere in the entire suite (Phase 3 brief
  §16, reaffirmed by the Phase 4 brief §17 and Phase 5's own fixtures) —
  every HTTP-touching test runs against a local stdlib `http.server`
  fixture.
- `tests/fixtures/*` used only as fixture *content* (sample projects for
  discovery/assessment to scan) are excluded from pytest's own test
  collection via `norecursedirs = ["fixtures", ...]` in `pyproject.toml` —
  needed once two fixtures happened to both ship a `tests/test_main.py`
  and pytest's default collection tried to import both as the same module
  name. Fixed at the config level, not by renaming fixture files to dodge
  the collision.
- Run order: smallest relevant test file first, then `pytest` full suite,
  per `skill.md` §31.8.
- `tests/adapters/database/` (Phase 6) unit-tests: `test_profile.py`
  (readonly-must-be-true refusal, missing engine/host/database, env-var
  credential resolution, `to_dict()` never includes username/password),
  `test_sqlite_driver.py` (real read-only queries against the
  `tests/fixtures/database/{sqlite-basic,sqlite-relations}` fixture
  databases — tables, columns, primary keys, foreign keys across
  `sqlite-relations`, indexes, row-count estimation, write-attempt against
  the read-only connection raising rather than succeeding),
  `test_driver_unavailable.py` (a missing `pyodbc`/`psycopg2`/`mysql
  .connector` import resolves to `DatabaseDriverUnavailableError` ->
  `NOT_ASSESSED`, never an uncaught `ImportError`), `test_adapter.py`
  (`discover()`'s end-to-end orchestration: success, connection failure,
  timeout, unsupported engine — every path returns a
  `DatabaseDiscoveryResult`, never raises). `tests/assessment
  /test_database_assessment.py` covers the "no profile" / "connection
  failed" / "connected with a real schema" / "zero foreign keys is INFO not
  FAIL" / "missing primary key is INFO not FAIL" cases.
  `tests/cli/test_cli_database_command.py` covers missing
  `--database-profile` (refused), `--dry-run` (never connects, verified via
  a driver-construction spy), an invalid profile file, missing credentials,
  and that no format/output ever contains a credential value. PostgreSQL/
  MySQL/SQL Server drivers have no dedicated integration tests requiring a
  live server in this suite (per the Phase 6 brief §20: "SQL Server /
  PostgreSQL / MySQL integration tests 如果需要 external services... 不要讓一般
  test suite 依賴 Docker") — their metadata-query logic is exercised through
  `test_driver_unavailable.py`'s import-guard path and code review against
  the same normalized-model contract SQLite's real-database tests already
  verify end-to-end.
- `tests/regression/` (Phase 7) unit-tests every comparator in isolation
  against hand-built `*Snapshot` dataclasses (no CLI, no HTTP, no
  filesystem) — `test_functional_compare.py` (every transition: PASS->PASS,
  PASS->FAIL/ERROR, FAIL->PASS, PASS->SKIPPED, added, removed, an unchanged
  *failure* not re-reported, mixed regression+improvement in one run,
  aggregate count deltas), `test_performance_compare.py` (below/at/above
  tolerance, latency/throughput/error-rate regression, an RPS increase
  correctly read as improvement not regression, a zero baseline value
  producing `NOT_COMPARABLE` rather than a divide-by-zero, a zero current
  value read as improvement, an empty thresholds dict never flagging
  anything), `test_database_compare.py`/`test_discovery_compare.py` (added/
  removed/changed always `INFO`, status never leaves `PASS`),
  `test_assessment_compare.py` (all three brief-specified severity
  transitions plus the indeterminate/improvement/category-only-on-one-side
  non-findings), `test_engine.py` (overall rollup reuses
  `assessment/rules.py` unmodified, a tool-version mismatch produces a
  warning not an error), `test_baseline_store.py` (round-trip, missing
  file, invalid JSON, non-baseline JSON, incompatible schema version,
  parent-directory creation, and a read-twice-never-writes check),
  `test_models.py` (full round-trip through `to_dict()`/`from_dict()` with
  every optional section populated and with all three optional sections
  `None`), `test_snapshot.py` (`build_snapshot()` against a real
  `discover()` result, with and without functional test results attached).
  `tests/cli/test_cli_baseline_command.py` integration-tests the full
  `baseline save`/`baseline compare`/`assess --baseline` pipeline against
  the same offline fixture server every other phase's CLI tests use, plus
  a dedicated `tests/fixtures/regression-project/` (a single `GET
  /unstable` endpoint) whose deterministic "every Nth request fails"
  behavior — reset via `reset_unstable_counter()`, then one throwaway
  request to advance the counter — produces a *real* PASS-then-FAIL
  transition on the exact same test ID across two live runs, rather than a
  mocked one; a real performance regression using `tests/fixtures
  /unknown-project` (no OpenAPI spec, so `--endpoint /fast` vs. `--endpoint
  /slow` is honored) against the fixture server's real 300ms `/slow` delay;
  a real database schema-change comparison reusing Phase 6's
  `sqlite-basic`/`sqlite-relations` fixture databases as two different
  schema snapshots; every safety property (`--output` required for `save`,
  `--baseline` required for `compare`, incompatible schema version refused,
  the baseline file byte-for-byte and mtime-unchanged after `compare`, zero
  network traffic without `--target`); and bearer-token redaction across
  both `baseline save`'s output file and `baseline compare`'s output.
- One correctness bug found *by* writing Phase 7's config test
  (`test_regression_partial_threshold_override_keeps_other_defaults`) and
  fixed the same session: `core/configuration/config.py::_build_section()`
  previously replaced a dict-valued config field wholesale on any override,
  which silently dropped the other five default regression thresholds the
  moment a project's `universal-test.yaml` overrode just one (e.g.
  `p95_percent: 25` alone would have zeroed out `p50/p90/p99_percent`,
  `rps_percent`, and `error_rate_absolute` entirely, since a missing key
  reads as "no threshold configured" to the comparator). Fixed by merging
  dict-valued fields over their dataclass defaults instead of replacing
  them; `PerformanceConfig.thresholds` (whose own default is `{}`) is
  unaffected by the change since merging into an empty dict is a no-op.
- `tests/quality_gate/` (Phase 8) unit-tests the gate in isolation against
  hand-built `ProjectAssessment`/`RegressionSummary` objects (no CLI, no
  HTTP): `test_signals.py` (each category's `AssessmentStatus` ->
  infra-vs-quality-signal classification, including the "no category
  present produces no signal" edge case), `test_engine.py` (every rule in
  §12.3's table individually — all-pass, functional/performance real
  failure vs. unreachable-is-infra-error, the explicit opt-in override,
  critical/high/medium/low/info regression severities, database
  not-assessed default-off and opt-in, unknown assessment status never
  failing, database/discovery schema-change warnings, mixed fail+warning
  findings, a custom policy disabling a default rule), `test_ci_detection.py`
  (every brief-named env var plus specific-marker-preferred-over-generic
  and empty-string-is-not-set), `test_serializers.py` (text/JSON shape, no
  secret-shaped content), `test_ci_templates.py` (the three CI templates
  parse/contain the expected flags, without contacting any provider).
  `tests/cli/test_cli_quality_gate.py` integration-tests the full exit-code
  contract end-to-end against the real offline fixture server (0 on pass,
  1 on a real functional/performance failure, 2 on bad `--format`/a
  nonexistent path, 3 on a genuinely unreachable target via a bind-then-
  close probe socket), `--ci` (never hangs without `--yes`, forces
  non-interactive behavior even when `sys.stdin.isatty()` is monkeypatched
  to report `True`, never itself authorizes traffic, prints the structured
  summary), CI environment variable detection (parametrized over
  `CI`/`GITHUB_ACTIONS`/`GITLAB_CI`/`JENKINS_URL` — each proven to never
  substitute for `--yes`, plus a `caplog` check that detection is actually
  logged), the bounded retry (disabled by default, retries exactly once on
  a genuine total transport wipeout with a config file enabling it, never
  retries a real assertion failure, and the hard `MAX_CI_RETRY_COUNT`
  ceiling), and bearer-token redaction through a real gate *failure* (a
  wrong token, so the finding text is actually populated with real content
  to check, not skipped because nothing failed). `tests/core/test_config.py`
  gained the Quality Gate policy's default/custom/nested-merge/invalid-shape
  cases, mirroring Phase 7's regression-threshold config tests exactly.

## 15. Explicit assumptions (flag for approval)

1. Python was chosen over Node/.NET because it was already available locally and
   keeps Phase 1 dependency-free; this is reversible but changing it later means
   rewriting Core.
2. `argparse` over `click`/`typer` for the CLI skeleton — revisit if UX needs grow.
3. Directory tree adds one nesting level (`src/universal_test/...`) versus
   `skill.md`'s literal `src/...` to satisfy standard Python packaging; module
   boundaries themselves are preserved exactly.
4. `json_schema_valid` ships Phase 1 as a minimal checker, not full JSON Schema,
   to avoid pulling in the `jsonschema` dependency before it's needed.
5. Discovery's text/JSON/Markdown serializers live under `discovery/`, not
   `reporting/`, since they only understand `ProjectModel` — `reporting/`
   is reserved for the Phase 5 report generators covering the full assessment
   pipeline. `universal-test scan --format html` intentionally errors (exit 2)
   until Phase 5 rather than emitting a half-implemented HTML report.
6. Kubernetes/connection-string/secret detection use bounded heuristic content
   scans (capped file counts, pattern matching) rather than full YAML/config
   parsing, to keep discovery fast and dependency-free; documented as
   best-effort, not exhaustive.
7. No dedicated OpenAPI-parsing library was added (§2 rationale above) —
   internal-`$ref`-only resolution plus direct dict-walking. External `$ref`s
   are left unresolved with a warning rather than fetched, by design.
8. Only OpenAPI 3.x is supported; Swagger 2.0 documents are detected and
   rejected with a clear `OpenApiError` rather than attempting a
   best-effort partial parse.
9. OpenAPI `security` requirements are flattened to OR-only semantics
   (§7.6) — the rare AND-combination-within-one-requirement-object case is
   not modeled.
10. A single `httpx.Client` (one timeout, one connection pool) is created
    per `test` invocation and reused for every generated test case; there is
    no per-request timeout override. Acceptable for Phase 3's functional-test
    scale; revisit if a real project's mixed fast/slow endpoints make one
    global timeout impractical.
11. `AdapterInfo`/`RestAdapter`'s generic contract methods are defined
    directly in `adapters/rest/adapter.py` rather than factored into a shared
    `core`-adjacent location, since REST is still the only adapter that needs
    them. Phase 6's database adapter turned out not to need this shape
    anyway — `discover(profile: DatabaseProfile) -> DatabaseDiscoveryResult`
    is deliberately *not* `detect(project_path)/discover(project_path)`,
    since a database connection is never derived from the scanned project
    (§10 above) — so the `AdapterInfo` contract is still only used by one
    adapter; factor out only if/when a future adapter actually shares REST's
    project-path-driven shape, per the "avoid premature abstraction" rule.
12. `time.perf_counter()`, not `time.monotonic()`, for all Phase 4 interval
    timing — a deliberate, tested choice after finding `monotonic()`'s ~15ms
    resolution on this Windows build produced zero-duration/zero-RPS results
    for fast concurrency levels (§8.4). Any future timing code in this
    project should default to `perf_counter()` for the same reason.
13. `performance` requires `--target` unconditionally, including `--dry-run`
    — different from `test`, where `--dry-run` needs no target. Judgment
    call: a performance *plan* is only meaningful against a known target
    (concurrency/RPS estimates are informational either way, but "what am I
    about to hit" is not optional information the way it arguably is for
    functional dry-run listing).
14. Interactive confirmation (`y`/`N`) is the only safeguard against
    accidental production load beyond the explicit `--target` requirement —
    no URL-pattern-based "this looks like production" heuristic, per the
    brief's own instruction that the tool cannot reliably know the
    environment. `--yes` exists solely for CI/non-interactive use, not as a
    way to skip thinking about the target.
15. No CLI-level `SIGINT`-to-cancellation wiring yet (§8.2) — the
    `PerformanceRunner` cancellation API is complete and tested, but a
    Ctrl+C during a live CLI run does not yet produce a partial
    `PerformanceResult`. Flagged as a known gap, not silently absent.
16. Zero new dependencies were added for Phase 4 — `httpx` (Phase 3) and the
    stdlib (`concurrent.futures`, `threading`, `queue`, `time`) cover
    everything needed.
17. Zero new dependencies were added for Phase 5 either — the offline HTML
    report uses plain string templates + stdlib `html.escape()`, not
    `Jinja2` (still deferred; see §2's original rationale, which still
    holds for one moderate-complexity static page).
18. `assess` defaults to writing all three report formats to `./reports/`
    when `--output` isn't given, reusing the directory `pyproject.toml`'s
    layout already reserved since Phase 1 — a deliberate choice to give
    that placeholder directory a real purpose rather than adding a new
    default location.
19. `assess`'s embedded `--performance` reuses the exact same safety gate
    (interactive confirmation / `--yes` / hard planner ceilings) as the
    standalone `performance` command, rather than a lighter-weight version
    — per the Phase 5 brief's explicit instruction that safety principles
    must not be relaxed inside a larger orchestrating command.
20. Coverage percentages (`assessment/engine.py::_compute_coverage()`) are
    five fixed, mostly-binary items (100%/0% plus one real ratio for
    Functional Execution) rather than a finer per-detector breakdown — a
    more granular number would imply a precision the underlying evidence
    doesn't support, which is exactly the kind of invented precision the
    Phase 5 brief's "no magic numbers" principle (§5) is warning against
    even though that principle is stated for the overall-status rule
    specifically.
21. `execution_health_status()` is shared between Functional Health and
    Performance rather than each category having its own bespoke ladder —
    both ask "did execution work, and did what ran pass its checks" with
    the same four-way answer; a threshold breach in Performance is
    deliberately capped at `WARNING` (matching the brief's own worked
    example) by having the caller downgrade `PASS`→`WARNING` after the
    shared function runs, rather than teaching the shared function itself
    about thresholds — it only knows about transport vs. check failures.
22. The database adapter's `DatabaseDriver` contract has no `execute(sql)`
    method at all, by design (§10.1) — a deliberate choice to make arbitrary
    SQL execution structurally impossible rather than relying on a
    statement-keyword blocklist, which is a strictly weaker guarantee (a
    blocklist can miss a syntax variant; a nonexistent method cannot be
    called). This is the single most consequential safety decision in
    Phase 6 and is not something a later phase should "simplify" by adding
    a generic query method.
23. `database.readonly: true` is required verbatim in the profile YAML
    (§10.2) — any other value, including an absent key, refuses the
    connection outright. This is stricter than most tools' "default to
    safe" pattern (which would default a missing key to `true`) because the
    brief explicitly calls for refusal over assumption (§6: "拒絕執行，而不是假設安全").
24. No dedicated live-server integration tests for PostgreSQL/MySQL/SQL
    Server were added — only SQLite (stdlib, no external service needed)
    gets full live-query integration coverage; the three server drivers are
    covered by import-guard tests (missing driver -> `NOT_ASSESSED`) plus
    code review against the same `DatabaseDriver` contract SQLite's tests
    already exercise end-to-end. Per the Phase 6 brief §20's explicit
    instruction not to make the general test suite depend on Docker/an
    external database service; revisit with an opt-in, skipped-by-default
    integration suite if/when a real project needs one of these three
    engines validated against a live instance.
25. Driver dependencies (`pyodbc`/`psycopg2-binary`/`mysql-connector-python`)
    are declared as one `pip install universal-test[database]` optional-
    dependency group covering all three engines together, rather than three
    separate per-engine extras — simpler for a user who doesn't yet know
    which engine(s) their project uses; revisit only if the combined
    install size becomes a real complaint.
26. `core/configuration/config.py::_build_section()` now merges dict-valued
    config fields over their dataclass defaults instead of replacing them
    wholesale (§13's Phase 7 testing note) — a deliberate, tested behavior
    change discovered while writing Phase 7's own config tests, not a
    pre-planned Phase 7 feature. Applies to every current and future
    dict-valued config field (`performance.thresholds`,
    `regression.performance`), not just the one that surfaced it.
27. `RegressionCategory`/`RegressionFinding`/`MetricDelta`
    (`regression/models.py`) deliberately mirror
    `AssessmentCategory`/`AssessmentFinding`'s shape rather than being
    unified into one shared base class — the two answer different
    questions (`status: AssessmentStatus` = "did this pass" vs. `change:
    ChangeType` = "what changed") and Phase 7 is still the only consumer of
    the regression shape; factor out a shared base only if a third,
    similarly-shaped model appears later, per the project's standing
    "avoid premature abstraction" rule (already applied the same way to
    `AdapterInfo` in assumption 11).
28. `regression/rules.py::status_from_findings()` is a **new**, separate
    function from `assessment/rules.py::compute_overall_status()` — not a
    reuse of it — because it answers a different question (worst finding
    *severity* -> category status, vs. worst *category status* -> overall
    status). The *overall* regression status, by contrast, does reuse
    `compute_overall_status()` directly (§11.5) — reuse where the question
    is identical, a small new function where it genuinely isn't, rather
    than forcing one function to serve both purposes.
29. Database and Discovery regression findings are hard-coded to
    `Severity.INFO` with no configuration to escalate them (§11.8/§11.9) —
    the Phase 7 brief explicitly names this as a future "baseline policy"
    concept (§11: "只有在有明確 baseline policy 時才判定 regression") without
    specifying its shape, so nothing was speculatively built for it; a
    project that needs stricter schema-change enforcement needs a later,
    separately-scoped phase to define what a "policy" actually configures.
30. `cli/main.py::_run_pipeline()` was extracted from what was previously
    `_run_assess()`'s inline body, and `_add_pipeline_args()` was extracted
    from `_add_assess_args()` — both are refactors of existing Phase 5 code
    made *because* Phase 7 needed the identical pipeline for `baseline
    save`/`baseline compare`, not speculative preparation. `_run_assess()`
    behaves identically before and after (the full pre-existing
    `tests/cli/test_cli_assess_command.py` suite passes unmodified),
    confirmed by running it both before and after the refactor.
31. The Phase 8 `0/1/2/3` exit-code contract and `--ci` flag are wired into
    `assess` only, not into `scan`/`test`/`performance`/`database`
    /`baseline save`/`baseline compare` — every CI template the brief
    itself asks for (§12-14) invokes `assess`, which is already the one
    command that aggregates everything the gate needs to evaluate. The
    other commands keep their pre-existing Phase 1-6 exit-code conventions
    unchanged, per this phase's explicit "不要重新設計 Phase 1–7" instruction;
    revisit only if a later phase's brief explicitly asks for the gate on
    another command.
32. **Two deliberate, phase-motivated exit-code behavior changes to
    pre-existing tests**, both required by this phase's own brief, not
    incidental: (a) `test_unreachable_target_is_functional_fail`'s exit
    code changed `0 -> 3` (brief §18's explicit "target unavailable is an
    infrastructure error, not a quality regression" rule didn't exist
    before this phase); (b) `test_failed_functional_project_is_warning`
    and `test_performance_with_flag_and_yes_executes_and_breaches_threshold`
    changed `0 -> 1` (a real assertion/threshold failure against a live
    target now fails the default Quality Gate, which also didn't exist
    before this phase). Each updated assertion still checks the exact same
    underlying category status it always did — only the exit-code
    expectation changed, matching the brief's own new, more specific
    contract, not a lowered bar.
33. `assess --baseline <bad-path>` changed from "log an error and silently
    continue with `regression=None`, exit 0" (Phase 7) to "log an error,
    still write a full report, but exit 2" (Phase 8) — a deliberate
    tightening once exit codes started meaning something specific to a CI
    pipeline: a broken `--baseline` reference silently producing an exit-0
    "everything's fine" result is exactly the kind of ambiguity Phase 8
    exists to remove. `--database-profile` load failure in `assess` was
    **not** given the same treatment and still degrades to `NOT_ASSESSED`
    without affecting the exit code — left alone deliberately, since this
    phase's brief doesn't call out database-profile-loading specifically
    the way it calls out baseline/target handling, and changing it wasn't
    necessary to satisfy any Phase 8 requirement.
34. Bounded CI retry (`CiConfig.retry.count`, brief §19) only ever retries
    the *functional* execution step, and only on a total transport
    wipeout — not performance execution, not a partial failure, not an
    assertion mismatch. Performance retry was considered and deliberately
    left out: re-running an entire load test is materially more expensive
    and riskier (a partially-completed level's samples would need careful
    handling) than re-running a single functional pass, and the brief's own
    framing treats retry as a narrow, "if needed" concession to network
    flakiness (§19: "如果 network instability 需要"), not a general-purpose
    feature — a real project that needs performance-specific retry should
    get a deliberately-scoped follow-up, not a speculative addition here.
35. `QualityGateStatus.WARNING` maps to `ExitCode.QUALITY_GATE_PASSED` (0),
    not a distinct exit code — the brief's own examples never show a
    warning-only run failing a build (§2's `warn_on` vocabulary exists
    precisely to let something be visible without being blocking), and
    introducing a 5th exit code for "passed with warnings" isn't in the
    brief's explicit `0/1/2/3` contract (§4). A CI consumer that wants
    warnings to block a build can promote the relevant rule from `warn_on`
    to `fail_on` in its own policy instead.
36. Frontend framework/language/build-system/test-framework facts reuse the
    existing `FrameworkDetection`/`LanguageDetection`/`BuildSystemDetection`/
    `TestFrameworkDetection` lists on `ProjectModel` rather than duplicating
    them into a parallel frontend-specific model — `FrontendInfo` only
    carries evidence kinds with no existing home (routes/components/forms/
    API-client signals, build/test npm scripts, env-file public key names).
    See §16.

## 16. Frontend / Web Application Analysis Adapter (`discovery/frontend.py`, `adapters/frontend/`, `assessment/frontend_assessment.py` — implemented)

Frontend **discovery + testability assessment** only — no browser/UI
execution. That remains a distinct, unimplemented future capability
(Browser Adapter); every surface (discovery, assessment, CLI, reports, GUI)
says so explicitly rather than letting "frontend detected" be read as
"frontend tested."

### 16.1 Pipeline

`discovery/engine.py`'s existing detector loop gained one more step,
`detect_frontend(files, bundle) -> FrontendInfo`, run unconditionally
alongside languages/frameworks/build-systems/test-frameworks — like every
other detector, a failure here is caught and recorded as a warning, never
aborting the rest of the scan. It is entirely read-only and offline: it
only reads files `filesystem.walk` already collected (bounded, capped file
counts) — it never runs `npm`/`node`/a package manager, launches a browser,
or opens a network connection. `package.json` `scripts` are copied as
inert strings for display, never executed (a malicious `"prepare"` script
in a scanned repository must not run).

### 16.2 What's new vs. reused (§4.1 "never overclaim")

- **Reused as-is**: `framework.py` gained Next.js/Nuxt/Svelte/SvelteKit/
  Solid/Astro (dependency or config-file evidence, same pattern as
  React/Angular/Vue); `project_type.py`'s `detect_build_systems` gained
  Vite/Webpack/Rollup/Turbopack/Angular CLI bundler detections, distinct
  entries from the pre-existing npm/yarn/pnpm package-manager entries so
  "framework" vs. "build tool" vs. "meta-framework" stay distinguishable
  facts, never conflated; `test_framework.py` gained Playwright/Cypress/
  Testing Library/WebdriverIO/Puppeteer/Karma/Jasmine.
- **New** (`discovery/models.py`): `FrontendSignal` (one reusable
  `status`/`count`/`evidence`/`note` shape for routes/components/forms/
  API-client evidence — avoids four near-duplicate classes) and
  `FrontendInfo` (the `ProjectModel.frontend` field), which only holds
  build/test npm scripts, frontend test directories, `.env.example`/
  `.env.template` **key names only** (values are never read into the
  model — mirrors `SecretFinding.to_dict()`'s existing `"value":
  "[REDACTED]"` convention), and the four `FrontendSignal`s.

### 16.3 Bounded heuristic scanning, honestly labeled

Route/component/form/API-client evidence comes from a substring scan of up
to 300 files under recognized frontend source roots (`src/`, `app/`,
`pages/`, `components/`, `routes/`, `views/`). Every `FrontendSignal.note`
states this bound explicitly (e.g. "heuristic, bounded scan of up to 300
frontend source file(s)") so nothing is ever presented as exhaustive route/
component discovery — the wording is always "evidence detected," never
"all routes found."

### 16.4 Adapter (`adapters/frontend/adapter.py`)

Mirrors `adapters/rest/adapter.py`'s shape (free `discover()` function +
`FrontendAdapter` class implementing the §5 `detect/describe/discover/
generate_tests/execute/collect_metrics` contract) for architectural
completeness. `generate_tests()` returns `[]` and `execute()` raises an
explicit `NotImplementedError` — honest stubs, not silent no-ops, since
actual browser/UI test generation and execution is out of scope for this
version.

### 16.5 Assessment (`assessment/frontend_assessment.py`)

A "Frontend / Web Application Health" category, added to
`assessment/engine.py`'s existing category list with **no new
`build_assessment` parameter** — unlike the database category (which needs
an out-of-band connection profile), this only reads `model.frontend`,
already populated unconditionally by `discover()`. Status is capped below
`FAIL` (same rule `database_assessment.py` already enforces for
connectivity problems): missing frontend test tooling is a testability
gap, not proof the frontend itself is broken, so this category only ever
reports `PASS`/`WARNING`/`NOT_ASSESSED`. `_compute_coverage`/
`_compute_unassessed` gained a "Frontend Discovery" (always 100%) and, only
when a frontend was actually detected, a "Browser/UI Execution" item
pinned at 0% with an explicit `NOT_ASSESSED` reason — the concrete
mechanism behind the "frontend detected ≠ frontend tested" rule everywhere
else in this section.

### 16.6 Reporting / CLI / GUI

`reporting/json_report.py` needed **zero changes** — it already serializes
`bundle.model.to_dict()` whole, and `ProjectModel.to_dict()` now includes
`frontend`; the new assessment category/findings flow through the existing
generic `assessment.categories`/`findings` loops the same way. Markdown/
HTML reports and `discovery/serializers.py` (plain `scan`) gained an
explicit "Frontend / Web Application" section with a
"Browser/UI Execution: NOT_ASSESSED" line. The GUI's category grid already
renders every `assessment.categories` entry generically, so the new
category appears automatically; `app.js` additionally appends the same
Browser/UI-not-assessed note directly on the frontend card (not just
buried in the Unassessed list), and `i18n.js` gained the Traditional
Chinese/English category label.

### 16.7 Static Web Analysis (Static Web Analysis brief, extends §16 above)

A frontend does not need a `package.json`/lockfile/config file at all — a
plain HTML/CSS/JS website is a first-class frontend type, not a fallback.
`discovery/models.py` gained a `FrontendType` enum
(`STATIC_WEB`/`FRAMEWORK_WEB`/`FULL_STACK_WEB`/`UNKNOWN_WEB`) and
`FrontendInfo` gained `frontend_type`, `entry_points`, `web_roots`,
`html_page_count`/`css_file_count`/`js_file_count`, `css_frameworks`, and
two more `FrontendSignal`s (`responsive`, `auth_ui`) — reusing the same
`FrontendSignal` shape already established for routes/components/forms/
API-clients rather than inventing per-concept classes (brief §11's "inspect
existing models first" rule, applied again).

**Detection is entirely structural**, never AST-based: `_detect_frontend_flag`
(manifest/config-driven) and the new `_detect_static_web` (HTML-file-driven)
in `discovery/frontend.py` run independently, and either one alone is
sufficient for `detected=True`. `_detect_static_web`'s false-positive guard
(brief §20) treats a lone non-root HTML file under a generated-docs- or
server-template-like directory (`docs/`, `templates/`, `_build/`, `site/`)
with no accompanying CSS/JS as insufficient evidence — never silently
assumed to be the project's real frontend; `coverage/`/`htmlcov/` were
added to `filesystem.py`'s `EXCLUDED_DIR_NAMES` so generated coverage HTML
never even reaches this logic (same mechanism already used for
`node_modules`/`dist`/`build`).

**Framework precedence is structural, not a special case**: `detect_frontend`
now takes `model.frameworks` (already populated earlier in
`discovery/engine.py`'s step loop — the closure captures `model` and reads
`.frameworks` at call time) and checks `has_frontend_framework`/
`has_backend_framework` *before* even looking at the static-web result, so
a React project's own `index.html` can never downgrade its classification
to `STATIC_WEB` (brief §26). `FULL_STACK_WEB` is `has_frontend_framework
or static.detected` **and** a recognized backend web framework
(`BACKEND_WEB_FRAMEWORK_NAMES` — FastAPI/Django/Flask/Express/ASP.NET
Core/Spring Boot/Laravel/Node.js) both present.

The existing bounded-scan machinery (`_scan_signal`, 300-file cap) was
reused as-is for the two new signals plus widened to also scan `.html`/
`.htm` content for routes/forms/API-client markers — no new scanning
infrastructure was introduced. CSS framework evidence
(`_detect_css_frameworks`) matches only filenames and `<link href>`/
content markers for four well-known libraries, deliberately never inferred
from an arbitrary class name (brief §8's explicit "`class=\"container\"`
is not sufficient proof of Bootstrap").

`assessment/frontend_assessment.py`'s summary text branches on
`frontend_type` (a `STATIC_WEB`/`UNKNOWN_WEB` project reports HTML/CSS/JS
counts; everything else keeps the original framework/language/build
summary) but the `PASS`/`WARNING`/`NOT_ASSESSED`-only status cap and the
"no test framework ≠ broken" rule are unchanged and apply identically to
static sites. Reporting/CLI output gained the new fields
(`frontend_type`, `entry_points`, HTML/CSS/JS counts, CSS frameworks,
responsive/auth-UI rows); the GUI needed **no** code change at all — the
category card already renders `category.summary` generically, so the new
static-web summary text appears automatically.

### 16.8 Static Web Capability Detection & Assessment Semantics Hardening (extends §16.7)

A real-world static-web project (essentially one `index.html` with heavy
inline CSS/JS, microphone/speech-synthesis/localStorage usage) surfaced two
gaps: `css_file_count`/`js_file_count` only ever counted *external*
`.css`/`.js` files, so a rich single-file app misreported as "CSS: 0,
JavaScript: 0"; and several `WARNING`-status categories (missing test
framework, missing build system) had no way to be told apart from an
actual application defect, so a non-technical user reading several
`WARNING` rows reasonably (but wrongly) concluded the app itself was
broken.

**New static-web capability detections** (`discovery/frontend.py`, all
reusing the existing bounded 300-file scan and `FrontendSignal` shape, no
HTML parser, `re` used only for simple tag matching — never a DOM parse):
`inline_css_count`/`inline_js_count` (regex-counted `<style>`/`<script
[no src=]>` blocks, additive to the existing external-file counts, never
replacing them), `interactive_ui` (`<button>`/`<input>`/`onclick=`/
`addEventListener(` etc.), `browser_apis` (a name list —
MediaRecorder/getUserMedia/speechSynthesis/AudioContext/storage/
WebSocket/Notification/Geolocation/Clipboard/FileReader/IndexedDB —
deliberately disjoint from `_API_CLIENT_MARKERS` so a microphone API is
never reported as a "backend API client"), `application_pattern`
(`static_multi_page`/`single_page_application`/`static_document`, a
bounded heuristic requiring real supporting evidence before claiming
`single_page_application`), `external_resources` (a few well-known CDN/
font hosts normalized to a friendly label, e.g. "Google Fonts", plus
generic external-stylesheet/script/image markers — never fetched), `csp`
(`Content-Security-Policy` meta/header string presence).

**Auth-UI hardening** (`_scan_auth_ui`): tiered into strong
(`type="password"` → `DETECTED`) vs. weak (`localStorage`/`sessionStorage`/
`Authorization`/`Bearer`, which are common in code that has nothing to do
with a login form — only counted when co-occurring with a `<form>` in the
same file, and capped at `INFERRED`). No marker was ever a bare prose word
("login"/"password"/"authentication"), so a README/comment mention was
already never sufficient; the tiering additionally stops generic storage/
header usage alone from being reported at the same confidence as an actual
password field.

**Assessment semantics — additive, not a replacement.** `overall_status`/
`compute_overall_status`/Quality Gate/regression/baseline/CLI exit codes
are **entirely unchanged** — this was a deliberate design constraint (no
false PASS, no numeric score). Two small additions layer on top instead:

- `FindingClassification` enum (`core/models/enums.py`) +
  `AssessmentFinding.classification` (default `INFORMATIONAL`, so all 12
  pre-existing call sites — verified by grep — needed no signature changes,
  only an explicit value at each site: `FUNC-FAILED`→`DEFECT`,
  `FUNC-ERROR`→`EXECUTION_FAILURE`, `PERF-*` threshold breaches→`DEFECT`,
  `TESTINFRA-001`/`FRONTEND-NO-TEST`/`FRONTEND-NO-BROWSER-TEST`→
  `TESTABILITY_GAP`, `DISC-001`/`CFG-SECRET-*`/`DB-NO-PK`/`DB-NO-FK`→
  `INFORMATIONAL`, `DB-WARN`→`NOT_ASSESSED`).
- `assessment/rules.py::compute_application_health(categories)` — a
  **category-name whitelist**, not a classification-based aggregation:
  `PASS` ("no confirmed defects") unless `Functional Health`/`Performance`
  (the *only* two categories whose status is ever driven by
  `execution_health_status()`, i.e. something that actually ran against
  the live project) report `WARNING`/`FAIL`. Every other category is
  already architecturally incapable of reaching `FAIL` (each module's own
  docstring says so), so a classification-based aggregation was considered
  and rejected as unnecessary complexity — the whitelist is simpler,
  already exactly correct, and trivially unit-tested.
  `ProjectAssessment.application_health` (new field) is computed once in
  `build_assessment` and is completely independent of `overall_status`.
- `ProjectAssessment.assessment_completeness` ("full"/"partial", new
  field) — purely derived from the pre-existing `coverage`/`unassessed`
  lists (`"full"` iff every `CoverageItem.percent == 100.0` and
  `unassessed` is empty); no new detection logic. In practice this is
  always `"partial"` today, since `_compute_unassessed` unconditionally
  includes "Business logic correctness" — an honest reflection that this
  tool can never fully assess that dimension, not a bug.

**Static-web-specific fixes**, independent of the classification work:
`discovery_assessment.py::assess_build_health` now reads `PASS` (not
`WARNING`) when `model.build_systems` is empty and
`model.frontend.frontend_type` is `STATIC_WEB`/`UNKNOWN_WEB` — a real
backend/JS project still has `build_systems` populated via pip/npm/etc.,
so this branch is unreachable for anything but a genuine static site.
`discovery/frontend.py`'s `_detect_static_web` was renamed to public
`detect_static_web` and wired into `project_type.py::detect_project_types`
(called only when the existing `package.json`-driven frontend branch found
nothing) so a plain static site gets a `ProjectTypeDetection(name="frontend")`
entry too — this alone fixes `assess_project_discovery` reading `PASS`
instead of `UNKNOWN` for a valid HTML/CSS/JS site with "0 languages."

**Reporting/CLI/GUI**: `reporting/json_report.py` needed one addition this
time (unlike prior additive-only passes) — its `assessment` sub-dict is
hand-built, not `ProjectAssessment.to_dict()` directly, so
`application_health`/`assessment_completeness` had to be added explicitly.
Markdown/HTML gained an "Assessment Summary" block (Application Health /
Testability / Assessment Coverage, each with a one-sentence explanation)
placed before the existing full category table, not replacing it; findings
gained a `classification` label; Quality Gate gained a fixed clarifying
sentence per pass/fail. The GUI's `_outcome_to_dict` needed **no** backend
change (it already forwards `assessment.to_dict()` whole); `app.js` gained
a `renderAssessmentSummary()` block and a classification badge per
finding, both additive to the existing generic category-grid/finding-list
rendering, not a redesign.

## 17. Browser / Web UI Functional Testing Adapter (`adapters/browser/`, Phase 9 — implemented)

The capability §16 explicitly reserved: real, bounded, explicitly-authorized
browser execution, built on top of §16's `FrontendInfo` discovery evidence
without duplicating any of it.

### 17.1 Reuse, not a second engine

No new test engine, assertion framework, or report format was created.
`adapters/browser/executor.py::browser_session()` yields an `Executor`
(`Callable[[TestCase], dict]`) matching `core/engine/test_engine.py`'s
existing contract exactly — `TestEngine.run(test_case, executor)` already
turns any executor exception into `ResultStatus.ERROR` and a test case with
no assertions into `ResultStatus.UNKNOWN`, so no Core change was needed to
get correct failure classification. `Orchestrator.run_test_cases()` runs
browser `TestCase`s completely unmodified. Browser-specific assertion
evaluators (`adapters/browser/assertions.py`: `visible`, `text_contains`,
`url_equals`, `page_title`, `element_count`, `attribute_equals`,
`input_value`, `checked`/`enabled`/`disabled`, `console_summary`) are
registered onto a dedicated `AssertionEngine(register_builtins=False)`
instance built inside `adapter.py`, never the shared REST/DB default
registry, so assertion-type vocabularies never leak between adapters.

`TestCase.target.extra["steps"]` (the existing `TestTarget.extra: dict`
escape hatch) carries the ordered action list (`navigate`/`click`/`fill`/
`select`/`check`/`uncheck`/`press`/`wait_for`) — no new Core model was
needed; `adapters/browser/models.py::BrowserStep`/`BrowserSelector` are
typed builders for that same dict shape.

### 17.2 Safety boundaries, each backed by a specific module

- **Optional dependency**: `playwright>=1.40` lives in
  `[project.optional-dependencies].browser`; `adapters/browser/executor.py`
  imports it lazily inside `_import_playwright()`, never at module scope —
  the whole package (including `adapter.py`, used unconditionally by
  `assess`'s wiring) imports cleanly with zero Playwright installed.
  Missing Playwright/browser binary raises `BrowserUnavailableError`,
  caught in `adapter.py::run()` *before* `Orchestrator` is ever invoked,
  and reported as `not_assessed_reason` — never `ResultStatus.ERROR`,
  mirroring `DatabaseDriverUnavailableError`'s precedent exactly.
- **Explicit target / target policy**: `adapters/browser/target_policy.py::
  validate_target()` is a pure function (no Playwright import) allowing
  `localhost`/`127.0.0.1`/`::1`/`file://` by default; anything else raises
  `BrowserTargetError` unless `allow_external=True`. Called once in
  `adapter.py::run()` before any browser launches, and again defensively
  inside `browser_session()`.
- **No credential guessing**: the adapter has no login/auth flow at all in
  this version — only env-var-based auth plumbing exists elsewhere in the
  codebase (REST); nothing here reads `.env`, tries default passwords, or
  auto-submits a form it detects.
- **Fresh isolation per run**: `browser_session()` launches exactly one
  `browser.new_context()` per run (fresh cookies/storage/cache), never
  reused across runs; no permission (`microphone`/`camera`/`geolocation`/
  `notifications`/`clipboard`) is ever granted — there is no
  `context.grant_permissions()` call anywhere in this adapter.
- **No arbitrary JS execution**: `_locate()`/`_run_steps()` in
  `executor.py` only ever call named Playwright locator/action methods for
  the fixed `ALLOWED_ACTIONS` set (`adapters/browser/models.py`) — no
  `page.evaluate(...)` exposed as a user action.
- **Bounded timeouts, hard-capped independent of config**:
  `core/configuration/config.py::BrowserConfig.__post_init__` clamps
  `navigation_timeout_seconds`/`action_timeout_seconds` to
  `MAX_BROWSER_TIMEOUT_SECONDS` (120s) and `test_timeout_seconds` to 5x
  that, the same "hard ceiling regardless of what a project configures"
  pattern `CiConfig.retry.count` already established; `NaN`/`+-infinity`
  are explicitly rejected (fall back to the safe default), not merely
  "happened to" clamp via Python's NaN-comparison quirks (Phase 9
  hardening pass fix — see §17.7).
- **TestCase wall-clock timeout is a true hard ceiling, not the sum of
  step timeouts** (Phase 9 hardening pass, §17.7): `executor.py::
  _remaining_ms()` is the single choke point every blocking Playwright
  call in a TestCase goes through — it computes `min(that call's own
  configured timeout, time left in the TestCase budget)` and raises
  `BrowserTimeoutError` outright, before issuing another Playwright call,
  once the budget is exhausted. No watchdog thread/signal is used
  (Playwright's sync API is explicitly single-threaded); per-call
  `timeout=` arguments are the only safe mechanism.
- **Redaction reuse**: `adapters/browser/redaction.py` calls
  `core/redaction.py`'s existing `redact()`/`redact_mapping()` — no second
  redaction system. `executor.py`'s `_executor()` closure calls
  `redact_context()` on the full context dict (console messages, network
  failure reasons, resolved element attributes/values) before it is ever
  handed to the AssertionEngine or turned into `Evidence`.
  `localStorage`/`sessionStorage`/cookies/IndexedDB are never read into
  the context dict in the first place — nothing to redact because it's
  never collected.
- **Process cleanup**: `browser_session()` is a `contextlib.contextmanager`
  with `finally` at every layer (page listeners → context.close() →
  browser.close() → playwright.stop()), so an assertion exception, a
  raised `Browser*Error`, a timeout, or a `KeyboardInterrupt` unwinding
  through the `with` block all still close everything.

### 17.3 Failure classification

`adapters/browser/errors.py` defines `BrowserUnavailableError`/
`BrowserTargetError`/`BrowserTimeoutError`/`BrowserSelectorError`/
`BrowserPermissionRequiredError`/`BrowserNetworkError`, each subclassing an
existing `core/errors.py` type (`AdapterError`/`TargetError`/
`RequestTimeoutError`/`ExecutionError`/`NetworkError`) so `TestEngine`'s
already-correct generic `except Exception -> ResultStatus.ERROR` path
handles all of them without any Core change — only `BrowserUnavailableError`
is special-cased (caught one layer up, in `adapter.py`, before
`Orchestrator` ever runs) since "browser missing" must read as
`NOT_ASSESSED`, not `ERROR`.

### 17.4 Assessment / Reporting / Quality Gate / Regression integration

- `assessment/browser_assessment.py::assess_browser_health()` is the tenth
  category `assessment/engine.py::build_assessment()` aggregates, added to
  `assessment/rules.py::_EXECUTION_DRIVEN_CATEGORY_NAMES` alongside
  `Functional Health`/`Performance` (Browser Testing is real execution
  evidence too, so it can legitimately drag `application_health` to
  `WARNING`/`FAIL` — every other category structurally cannot).
- `reporting/report_bundle.py::AssessReportBundle` gained a
  `browser_result` field; `json_report.py`/`markdown_report.py`/
  `html_report.py` each render the three states (`NOT ASSESSED` / `PASS`
  with target+browser+counts / a status with an execution-failure
  disclaimer) as an additive "Browser Testing" section, and the
  pre-existing hard-coded "browser automation adapter is not enabled"
  string in the Frontend section (§16) was replaced with a pointer to the
  real category status.
- Quality Gate (`quality_gate/engine.py`) needed **zero** changes — a
  "Browser Testing" `AssessmentCategory.status` flows through the existing
  `QualityGatePolicy.fail_on`/`warn_on` data-driven mechanism automatically;
  it is not in the default policy, so `NOT_ASSESSED` never fails CI
  without explicit opt-in.
- `regression/browser_compare.py` mirrors `functional_compare.py`
  file-for-file (per-test-ID PASS→FAIL/ERROR identity comparison, no
  numeric score); `regression/models.py::BaselineSnapshot` gained an
  optional `browser: BrowserSnapshot | None = None` field (defaulted so
  pre-Phase-9 baseline JSON files still load via `from_dict`), wired into
  `regression/snapshot.py::build_snapshot()` and `regression/engine.py::
  compare()`'s existing comparator list.

### 17.5 CLI / Application Service Layer / GUI

- New `universal-test browser install [--engine chromium|firefox|webkit]`
  (thin wrapper around `python -m playwright install <engine>` —
  explicit, never automatic) and `universal-test browser test <project>
  --target <url> [--allow-external] [--screenshots] [--dry-run] [--yes]`,
  following the CLI's existing nested-subparser pattern
  (`cli/main.py`, same shape as `baseline save`/`baseline compare`).
- `assess`/`baseline save`/`baseline compare` gained `--browser`/
  `--allow-external`/`--screenshots` (via `_add_pipeline_args`, shared by
  all three); `cli/main.py::_maybe_run_assess_browser()` mirrors
  `_maybe_run_assess_performance()`'s exact confirmation-gate shape
  (prints the target/safety text, requires `--yes` outside an interactive
  TTY) — browser testing only ever runs when `--browser` AND `--target`
  AND (`--yes` or an interactive "Continue? [y/N]") are all satisfied.
- `application/service.py::AssessmentRequest` gained
  `run_browser`/`browser_confirmed`/`browser_target`/
  `browser_allow_external`/`browser_screenshots`; `browser_confirmed` is
  the GUI's explicit checkbox confirmation, the same shape
  `performance_confirmed` already established (no equivalent of `--yes` is
  ever silently implied by the GUI itself). `_run_browser()` mirrors
  `_run_performance()`; a new `STAGE_BROWSER_TEST` progress stage was added
  to `application/events.py`.
- The GUI reuses the existing single `/api/assess` pipeline rather than
  adding parallel `/api/browser/*` endpoints — browser testing is exposed
  as one more opt-in checkbox (`chk-browser` + `browser-confirm-box`) in
  `gui/static/index.html`, exactly like the pre-existing performance/
  database checkboxes, and its result renders automatically through the
  already-generic `category-grid` loop in `app.js` (no per-category
  special-casing needed, `assessment.categories` just gained one more
  entry). This was a deliberate scope decision: it reuses a
  battle-tested, already-tested pipeline instead of duplicating run
  tracking/SSE-streaming/error-sanitization for a second endpoint.

### 17.6 What remains out of scope (unchanged from the brief)

AI-generated test plans, visual regression, accessibility auditing,
security scanning, distributed/cloud browser providers, automatic project
server startup, arbitrary JavaScript execution as a user action, and
automatic credential discovery/guessing are all still explicitly out of
scope — nothing in this phase's implementation introduces any of them.

### 17.7 Hardening / Real-Project Validation pass

A follow-up pass on the same architecture — no redesign, one real defect
fixed, one real gap closed:

- **TestCase wall-clock timeout**, closing the known limitation the
  original Phase 9 report explicitly flagged ("bounded by the sum of step
  timeouts, not a single hard ceiling"). Implemented via `_remaining_ms()`
  in `executor.py` (see §17.2 above) — verified with a real fixture
  (`tests/fixtures/browser-static-slow/`, a page whose `#ready` element
  only appears after a 10-second `setTimeout`) where `test_timeout_seconds=2`
  with a generous `action_timeout_seconds=10` still completes in ~2.4s,
  not ~10s.
- **`BrowserConfig.test_timeout_seconds` was defined but never actually
  wired to the executor** — a real gap the hardening pass found:
  `browser_session()` had no `test_timeout_seconds` parameter at all.
  Fixed by threading it through `browser_session()` → `adapter.py::run()`/
  `BrowserAdapter.execute()` → `cli/main.py`/`application/service.py`
  (both already read `config.browser.*`, just never this one field).
- **`Authorization: Bearer <token>`/`Basic <credentials>` redaction gap**
  (found during the original Phase 9 pass, documented here for
  completeness): `core/redaction.py`'s key=value pattern previously only
  redacted the scheme word ("Bearer"), not the token itself.
- **`NaN`/`+-infinity` timeout config values** previously passed through
  `BrowserConfig.__post_init__`'s clamp only by accident of Python's NaN
  comparison semantics (`min(nan, cap)` happens to evaluate to `nan`,
  which `max(1.0, nan)` happens to evaluate to `1.0`) rather than by
  explicit, tested intent. `_sanitize_timeout_seconds()` now checks
  `math.isfinite()` explicitly.
- **Real-project validation** (no fabricated results — see `PROGRESS.md`'s
  Phase 9 Hardening entry for the actual matrix): static HTML, a
  single-file rich SPA with `getUserMedia`/`MediaRecorder`/`SpeechSynthesis`
  (`tests/fixtures/frontend-static-rich-spa/`, browser-tested without any
  permission being auto-granted), a React/Vite framework frontend
  (confirmed no `STATIC_WEB` downgrade), a backend-with-templates project
  (confirmed not misclassified as a standalone frontend), an intentionally
  broken frontend (`FAIL`, understandable reason), and an unreachable
  target (`ERROR`/`FAIL` per the existing transport-wipeout rule, with an
  explicit "does not by itself prove the application is defective"
  disclaimer) — all against the real CLI, not simulated.
- **Cancellation regression tests** added (`test_cancellation.py`) proving
  the existing `KeyboardInterrupt`-safe cleanup behavior (§17.2's
  `finally`-at-every-layer design) still holds — no redesign, since it
  already satisfied the requirement.
- **Application Health hint text** ("...driven by something that actually
  executed (Functional/Performance)") was stale — Browser Testing joined
  that execution-driven whitelist in the original Phase 9 pass but the
  human-facing description text in `markdown_report.py`/`html_report.py`/
  `i18n.js` was never updated to say so. Fixed.

## 18. One-Click Web Assessment / Non-Programmer UX (Phase 10 — implemented)

Not a new testing engine — a presentation/orchestration layer making the
existing `scan`/`assess`/`browser test` capabilities usable by someone who
doesn't know those are three different commands. Every rule below exists
to keep it that way: one source of truth for discovery/execution/
assessment/reporting, reused unmodified.

### 18.1 Backend: reuse, not a new pipeline

`cli/main.py::_run_web_assess()` (the `universal-test web assess` command)
is a thin preset over the *existing* `assess` command: its argparse
subparser forces `browser=True` and defaults out the performance/database
surface (`set_defaults(performance=False, database_profile=None, ...)`),
then calls `_run_assess()` **unmodified** for real execution — the same
function `assess` itself calls. Zero duplicate discovery/execution/
assessment/report logic. The only genuinely new code is a `--dry-run`
presentation path that prints a human-readable plan (reusing
`adapters/browser/adapter.py::run(dry_run=True)` and
`adapters/browser/serializers.py::plan_to_text()` — both pre-existing) —
this exists because `assess --browser --dry-run` itself has no equivalent
plan-preview output today (a known pre-existing gap in the general `assess`
command, deliberately left alone here rather than changed, since Phase 10's
scope is the new guided command, not `assess`'s general contract).

The GUI's "Web Assessment" card, similarly, does not introduce a second
run/execution path: it POSTs to the *same* `/api/assess` endpoint the
"Full Assessment" form already used, with a request body preset the same
way the CLI's argparse defaults are (`run_functional: true, run_performance:
false, run_database: false, run_browser: true, browser_target: <target>`),
then reuses the exact same run-tracking (`RunRegistry`), SSE progress
stream, and results-rendering code (`renderResults()`) the existing flow
already had. `gui/server.py`'s only new endpoint is `POST /api/web/detect`
— read-only, calls the existing `discover()` and returns `model.frontend.
to_dict()` plus framework/language names, so the GUI can show a plan
*before* the user commits to running anything (spec section 12) without
re-parsing HTML itself or standing up a second discovery engine.

### 18.2 Web detection

Reuses `discovery/frontend.py`'s existing `FrontendType` enum
(`STATIC_WEB`/`FRAMEWORK_WEB`/`FULL_STACK_WEB`/`UNKNOWN_WEB`) and
`FrontendInfo.detected` unmodified — no second, incompatible web
classification system. `detected: false` (a backend project with no
frontend evidence, e.g. `backend-html-template`) renders as "no web
frontend was detected, you can still use Full Assessment below," never a
failure (spec section 9).

### 18.3 Assessment plan before execution

The plan card (GUI) and the `--dry-run` output (CLI) both show, before
anything executes: detected type + evidence (entry point, framework,
detected browser APIs — straight from `FrontendInfo.to_dict()`), the fixed
list of planned checks (structure discovery, static analysis, browser
smoke test, console-error observation), and the fixed list of what's
*not* included (login, permission verification, visual regression,
security testing, accessibility audit) — spec section 12's exact list,
hard-coded as informational text since the smoke test's scope itself is
fixed (§16/§19 of the Phase 9 spec never changed).

### 18.4 Safety unchanged

No safety gate was loosened to make this "one-click": `--yes`/interactive
confirmation is still required for real browser execution
(`_maybe_run_assess_browser()`'s existing triple-gate — unmodified);
`browser_confirmed` is still a separate explicit GUI checkbox from
`run_browser` (mirrors `performance_confirmed`'s established pattern);
`--allow-external`/`browser_allow_external` still gates non-local targets
(`target_policy.py`, unmodified). The GUI's "external target" warning box
(a client-side prefix-match heuristic, `looksLikeLocalTarget()` in
`app.js`) is presentation-only — the backend's `target_policy.py` remains
the sole authority regardless of what the heuristic shows, exactly as the
spec requires ("The GUI confirmation is additional UX protection, not the
security boundary").

### 18.5 Result summary

`renderAssessmentSummary()` (pre-existing since Phase 8.5/9) already put
Application Health/Testability/Assessment Coverage at the top of the
results screen, each with its own status badge and one-sentence
explanation — exactly the "non-collapsed WARNING soup" spec section 47
asks for. Phase 10 adds one more line to that same card: Browser Testing,
reusing `statusBadge()` unmodified. No numeric score was added anywhere
(spec section 48) — `assessment_completeness` still renders as the literal
string `PARTIAL`/`FULL`, never a percentage.

### 18.6 A real UX bug found and fixed during review

Picking a *different* project folder after already analyzing one left the
previous plan card visible with stale detection data — a user could
plausibly start a Web Assessment against outdated evidence for the wrong
project. Fixed in `btn-pick-folder`'s handler: selecting a new folder now
hides `#web-assess-plan` until the user re-analyzes.

## 19. Web Test Scenario / Workflow Testing (`adapters/browser/scenario_*.py`, Phase 11 — implemented)

An explicit, user-authored, repeatable multi-step Web workflow layer —
"WHAT should be executed" — sitting entirely on top of the existing
Browser Adapter, which remains solely responsible for "HOW browser
operations are executed" (spec §3). No second Playwright execution path,
no second assertion engine, no second timeout mechanism.

### 19.1 A scenario step is one `TestCase`, not a bespoke object

`scenario_runner.py::_build_step_test_case()` synthesizes exactly one
`TestCase` per step — either a single action (`steps: [BrowserStep]`,
`assertions: []`) or a single assertion (`steps: []`,
`assertions: [AssertionSpec]`), never both — and runs it via
`TestEngine.run(test_case, executor)`, the same Core entry point Phase 9's
single-TestCase smoke test already uses. `ScenarioRunner`'s only addition
is the *sequencing*: a plain Python loop over steps that stops at the
first non-PASS result (spec §21), sharing one live `executor` (one browser
context) across the whole scenario. An action step landing on Core's
`ResultStatus.UNKNOWN` (its existing "executed, nothing was asserted"
outcome) is interpreted at the scenario layer as step `PASSED` — a
scenario-specific reading of an unmodified Core signal, not a Core change.

### 19.2 Selector/action/assertion reuse

`scenario_models.py::ASSERT_ACTION_MAP` maps every `assert_*` scenario
action onto an existing `adapters/browser/assertions.py` evaluator name
(`assert_visible` → `visible`, `assert_count` → `element_count`, etc.) —
the scenario layer never defines a new assertion semantic, only a
YAML-friendly name for an existing one. Real actions
(`navigate`/`click`/`fill`/...) reuse `BrowserSelector`/`BrowserStep`
unmodified; `ACTION_ALIASES` (`select_option`→`select`, `wait`→`wait_for`)
and a `role` selector's `name`↔`value` alias are pure scenario-authoring
convenience, resolved before ever touching the shared models.

### 19.3 Timeout cascading — one hard-ceiling mechanism, parameterized

`executor.py`'s `_executor()` closure gained a single small addition:
`test_case.target.extra.get("test_timeout_seconds_override")`, read once
per call, falling back to the session-level `test_timeout_seconds` when
absent (every Phase 9/10 caller — unaffected). `ScenarioRunner` computes
`remaining = scenario_deadline - now()` before every step and passes
`min(step's own timeout, remaining)` as this override — the exact "child
never exceeds remaining parent budget" rule Phase 9 Hardening's
`_remaining_ms()` already enforces one level down, now composed one level
up. No watchdog thread, no second timeout system.

### 19.4 A real relative-navigation bug found and fixed

Building the first real scenario (`login.html` → click → assert) exposed
a genuine gap: `_run_steps()`'s `navigate` handler never resolved a
relative `url`/`value` against the target origin before calling
`page.goto()` — harmless in Phase 9/10 (the smoke test always navigates to
the full target itself), but scenario portability explicitly wants
relative URLs (spec §41: `/login`, not `http://host:port/login`). Fixed
with a single `urljoin(target, value)` in the shared `_run_steps()`,
benefiting any future browser test definition, not just scenarios.

### 19.5 A real CLI safety gap found and fixed

The first `browser scenario run` subcommand draft added a `--yes` flag but
never gated execution on it — scenario runs would have silently bypassed
the confirmation requirement `browser test`/`web assess` both correctly
enforce (spec §15/§18/§46: "one-click does not mean no safety"). Fixed by
mirroring `_maybe_run_assess_browser()`'s exact confirmation-gate shape.
While fixing this, a second, older latent bug surfaced across *all four*
of the CLI's confirmation prompts (performance/browser test/web assess/
scenario run): `input()` can raise `EOFError` with a raw traceback rather
than a clean refusal when stdin is redirected in certain Windows/
subprocess configurations even though `sys.stdin.isatty()` reported
`True`. Fixed once, centrally, via a new `_confirm()` helper all four call
sites now share.

### 19.6 Assessment / Regression / Reporting integration

Mirrors Phase 9's Browser Testing integration file-for-file:
`assessment/scenario_assessment.py` ("Web Scenarios", the eleventh
category, added to `_EXECUTION_DRIVEN_CATEGORY_NAMES` alongside Browser
Testing); `regression/scenario_compare.py` (per-scenario-ID PASS/FAIL/
ERROR comparison, mirrors `browser_compare.py`, stable scenario `id` as
identity per spec §36); `reporting/*_report.py` gain a "Web Scenarios"
section. Quality Gate needed zero changes (a new category flows through
the existing data-driven `fail_on`/`warn_on` policy automatically, same as
every prior category addition).

### 19.7 CLI / GUI

`universal-test browser scenario list/validate/run` (nested under the
existing `browser` command, matching `browser install`/`browser test`'s
precedent) plus an opt-in `--scenario <id>` (repeatable) on `assess`/
`baseline save`/`baseline compare`. The GUI's "Web Scenarios" card adds
two new endpoints: `POST /api/web/scenarios` (read-only, wraps the
existing loader/validator) and `POST /api/web/scenario/run` — the latter
executes synchronously (a scenario run is one bounded, hard-timeout-capped
operation, not `/api/assess`'s multi-stage pipeline, so it deliberately
does not use `RunRegistry`/SSE) but still requires the same explicit
`confirmed: true` the GUI's other browser-launching flows require, and
calls the exact same `run_scenario()` the CLI uses.
