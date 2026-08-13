# SPECIFICATION.md

## 1. Purpose

`universal-test` is a project-agnostic CLI framework that inspects an unfamiliar or
user-owned software project and produces an evidence-based *initial* quality
assessment: discovery, conservative functional tests, opt-in performance tests,
regression comparison, and JSON/Markdown/HTML reports.

This is the authoritative functional specification for the project. It is derived
from `skill.md` (the development constitution) — see that file for full rationale.
`skill.md` always wins in case of conflict.

## 2. Non-goals

The tool is explicitly **not**:

- a complete security scanner or vulnerability detector
- a replacement for QA engineers or penetration testers
- a formal verification system
- a complete business-logic validator
- a guarantee of production readiness

Positioning: *a general-purpose automated framework for initial software project
discovery, functional validation, performance measurement, regression detection,
and evidence-based quality assessment.*

## 3. Users / use cases

1. **Unfamiliar project** — user points the tool at a repo they didn't write (vendor
   handoff, legacy system, OSS project) and wants a fast orientation report.
2. **Own project** — user wants a repeatable baseline: functional smoke tests,
   performance snapshot, regression detection against a prior run, and a quality
   summary they can track over time.

## 4. Functional requirements

### 4.1 CLI surface (target, built incrementally)

```
universal-test scan <path>
universal-test assess <path>
universal-test test <path>
universal-test performance <path> --target <url>
universal-test report <path>
universal-test run <path> --all
```

Options: `--config`, `--output`, `--format`, `--verbose`, `--adapter`, `--target`,
`--dry-run`, `--safe-mode`.

Phase 1 delivered the argument-parsing skeleton and command routing;
`scan` (Phase 2), `test` (Phase 3), `performance` (Phase 4), and `assess`
(Phase 5) are now fully implemented — the remaining commands (`report`,
`run`) still raise a clear "not implemented until Phase N" signal rather
than silently doing nothing or crashing with a stack trace. (`report`'s
functionality is effectively subsumed by `assess`, which already emits
`report.json`/`.md`/`.html`.)

### 4.2 Discovery (Phase 2 — implemented)

`universal-test scan <path>` performs a read-only scan and reports, each with
confidence + evidence (never a bare assertion):

- **Repository**: git presence, root, branch, commit, dirty working tree,
  file count, test directories. Never mutates the repository (git commands
  used are limited to `rev-parse`/`status --porcelain`).
- **Languages**: Python, JavaScript, TypeScript, C#, Java, Go, Rust, PHP,
  Kotlin, Swift, Solidity, SQL — anchored on manifest/marker-file evidence,
  not bare extension counts (see `ARCHITECTURE.md` §6.2).
- **Project types**: python, node, dotnet, java, go, rust, php, frontend,
  generic (fallback when nothing else matches).
- **Frameworks**: ASP.NET Core, WinForms, WPF, React, Angular, Vue, Node.js,
  Express, FastAPI, Django, Flask, Spring Boot, Laravel, Hardhat, Foundry —
  only asserted from concrete manifest-dependency or marker-file evidence.
- **Build systems**: pip/poetry, npm/yarn/pnpm, dotnet sdk, maven/gradle, go
  modules, cargo, composer.
- **Infrastructure**: Dockerfile, Docker Compose, Kubernetes (directory or
  bounded YAML content scan), Terraform, GitHub Actions, GitLab CI, Jenkins,
  Azure Pipelines.
- **Databases**: SQL Server, PostgreSQL, MySQL, SQLite, MongoDB, Redis — from
  dependency names, `*.sqlite`/`*.db` files, connection-string *patterns*,
  and `docker-compose` service images. Never connects to anything.
- **API/service evidence**: OpenAPI/Swagger file presence+content,
  GraphQL schema files/dependencies, REST-style routing directories
  (`routes/`, `controllers/`, `api/` — weak/`INFERRED` evidence only). Real
  endpoint parsing is Phase 3.
- **Test frameworks**: pytest, unittest, Jest, Vitest, Mocha, NUnit, xUnit,
  MSTest, JUnit, go test, cargo test — plus test-directory discovery.
- **Secrets**: pattern-based scan (password/token/api_key/secret/connection-
  string/private-key patterns) reporting only `file`, `line`, `pattern_type`
  — the matched value is never captured, logged, or serialized. A pattern
  match is not a confirmed secret and not a vulnerability finding.

Output: `--format text|json|markdown` to stdout or `--output <path>` (file or
directory). `--format html`/`all` intentionally error until Phase 5.

Full detail in `skill.md` §6–§7 and `ARCHITECTURE.md` §6.

### 4.3 Functional testing — REST/OpenAPI (Phase 3 — implemented)

```
universal-test test <path> --target <url> [--openapi <path>] [--dry-run]
```

Given a project with exactly one discoverable OpenAPI 3.x document (or an
explicit `--openapi <path>`), the tool:

1. Parses the document into a normalized, technology-independent
   `ApiSpecification` (never a proprietary parser object) — internal `$ref`s
   resolved, external `$ref`s left unresolved with a warning (never fetched
   automatically).
2. If more than one candidate spec file exists and `--openapi` wasn't given,
   refuses to guess: reports the (sorted, deterministic) candidate list and
   exits non-zero.
3. Generates conservative positive tests (required parameters + request body,
   built from documented `example`/`default`/`enum`/`minimum` — never
   fabricated when there isn't enough information, in which case that
   endpoint's test is marked `UNKNOWN` and not executed) and up to 3
   conservative negative tests per endpoint (missing required
   parameter/body field, invalid type, unsupported content type) — only when
   a concrete documented error status exists to assert against. No fuzzing.
4. If an endpoint requires authentication and no matching credential was
   supplied (via `--bearer-token-env`/`--api-key-env`/
   `--basic-auth-user-env`+`--basic-auth-pass-env`, reading the named
   environment variable — never the raw secret on the command line), that
   endpoint's tests are marked `SKIPPED`, never executed, never guessed.
5. `--dry-run` (or omitting `--target`) stops here: "Discovered: N endpoints
   / Generated: M test cases", each with its expected status, and **no HTTP
   requests are executed**. Omitting `--target` without `--dry-run` still
   completes discovery/generation and then reports `ERROR: No execution
   target specified` with a non-zero exit code — the repository was
   analyzed, nothing was executed.
6. With `--target`, executes each test over HTTP (`httpx`), evaluates
   assertions via the *existing* `AssertionEngine` (no new assertion types),
   optionally validates the response body against the documented JSON
   Schema (`jsonschema`, full draft support as of Phase 3 — see §4.4), and
   distinguishes `PASSED/FAILED/SKIPPED/UNKNOWN/ERROR`. A connection
   failure, timeout, or unreachable target is `ERROR` (with a distinct
   exception type recorded in evidence) — never conflated with `FAILED`
   (an assertion mismatch against a server that *did* respond).
7. `--target` always wins over any `servers` entry in the OpenAPI document —
   a spec pointing at a production/external URL is never auto-used.
8. No credential (bearer token, API key, basic-auth password) is ever
   present in a `TestCase`, `TestResult`, log line, or exception — the
   executor sends auth headers but never returns them in the context dict
   `AssertionEngine` evaluates against, so nothing results are built from
   can contain them.

Output: `--format text|json|markdown` to stdout or `--output <path>`, for
both dry-run and executed runs.

Other adapters (GraphQL, .NET/Node/Python project adapters) remain
unimplemented. REST/OpenAPI (Phase 3), the read-only database adapter
(Phase 6, §4.9), and the browser adapter (Phase 9, §4.14) are implemented.

### 4.4 Assertion engine (Phase 1, extended per-adapter later)

A registry of named, composable assertions (`status_code`, `status_code_in`,
`response_time_less_than`, `json_path_exists`, `json_path_equals`,
`json_schema_valid`, `header_exists`, `header_equals`, `body_contains`,
`body_not_contains`, `row_count`, `value_equals`, `value_not_null`). Each
evaluation produces structured `AssertionResult` evidence — never a bare
boolean. `json_schema_valid` shipped in Phase 1 as a minimal type/
required-field checker; as of Phase 3 it uses the `jsonschema` library for
full JSON Schema draft validation (falling back to the minimal checker if
`jsonschema` is ever unavailable), while a malformed *schema* (as opposed to
invalid response data) is reported as a schema error rather than silently
passed or conflated with an API failure.

### 4.5 Performance testing (Phase 4 — implemented)

```
universal-test performance <path> --target <url> [--endpoint <path> --method <verb>]
    [--profile baseline|load|stress|custom] [--concurrency 1,10,50] [--requests N | --duration S]
    [--dry-run] [--yes]
```

- **Load profiles**: `baseline` (forces concurrency=1), `load` (fixed
  concurrency levels, default `[1, 10]`), `stress` (auto-generated stepping
  sequence, stops on a configurable error-rate/P95 condition — defaulting
  to `error_rate_percent > 50` if the user gave no stop condition — or a
  `--max-concurrency` cap, whichever comes first: never increases forever),
  `custom` (explicit `--concurrency` required, never defaulted).
- **Request source**: reuses Phase 3's OpenAPI discovery and the *same*
  deterministic request-data generator functional testing uses — never a
  freshly-randomized request per call, so results across concurrency levels
  are comparable. Falls back to an explicit `--endpoint`/`--method` only
  when no OpenAPI document is discoverable; never scans for an unknown API.
- **Safety** (highest priority, per the Phase 4 brief): `--target` is
  required unconditionally, including for `--dry-run` — the tool never
  attacks a URL merely because it appeared in the repository, never uses an
  OpenAPI `servers` entry automatically, and every numeric knob
  (concurrency/requests/duration/levels) has a hard ceiling independent of
  CLI validation. Non-`--dry-run`, non-`--yes` runs print the full test
  plan and estimated request count, then require an explicit `y`/`yes`
  confirmation; a non-interactive session without `--yes` is refused rather
  than hanging. No attempt is made to detect "this looks like production"
  from the URL — the brief is explicit that the tool cannot reliably know
  this, so the safeguard is always showing the plan + requiring
  confirmation, not guessing about the environment.
- **Concurrency**: bounded `ThreadPoolExecutor` (`max_workers=concurrency`),
  never unbounded threads/tasks; supports both a fixed request count per
  level and a fixed duration per level; cooperative cancellation via a
  shared event, checked between requests (duration mode) and always between
  concurrency levels.
- **Metrics per level**: total/successful/failed request counts, error rate
  (%), timeout count, network-error count, HTTP-error count, wall-clock
  duration, total RPS and successful-RPS (both defined against wall-clock
  time, not summed per-request durations), and latency P50/P90/P95/P99 (+
  min/mean/max) via a documented nearest-rank percentile algorithm — never
  an unexplained one-liner. Zero samples never fabricates a `0ms`/`0 RPS`
  result; latency is `None`/thresholds against it are `NOT_ASSESSED`.
- **Error classification**: HTTP error (status ≥ 400, transport succeeded),
  timeout, and network/connection error are distinguished from each other
  and from a passing request — never merged into one undifferentiated
  "failure" count.
- **Threshold evaluation**: an independent, unit-tested component (not
  hardcoded in the runner), evaluating `p50_ms/p90_ms/p95_ms/p99_ms` (max),
  `error_rate_percent` (max), `min_rps` (min) — read from
  `universal-test.yaml`'s existing `performance.thresholds` section
  (`skill.md` §18, unused until this phase). Result is `PASS`/`FAIL`/
  `NOT_ASSESSED` per threshold, using the same `AssessmentStatus` enum
  category-level assessments already use elsewhere.
- **No regression engine yet** (Phase 4 does not compare against a stored
  baseline — that's explicitly deferred, see §4.6) and **no AI** (fully
  deterministic).
- Output: `--format text|json|markdown` to stdout or `--output <path>`,
  for both the dry-run plan and the executed result.
- No credential (bearer token, API key, basic-auth password) is ever
  present in a `PerformanceRequest`/`PerformanceResult`/log line — same
  guarantee as functional testing (§4.3), verified end-to-end.

### 4.6 Regression engine (deferred — explicitly out of scope for Phase 4)

Compare a run's performance/functional metrics against a stored baseline using
configurable thresholds; do not flag every fluctuation as a regression. The
Phase 4 brief explicitly excludes this ("§20 No Regression Engine Yet" —
no baseline comparison across versions, no historical trend, no automatic
regression detection, no CI quality gate) even though threshold evaluation
*within* a single run is now implemented (§4.5). Scheduled for a later
phase, not yet numbered.

### 4.7 Assessment engine (Phase 5 — implemented)

```
universal-test assess <path> [--target <url>] [--performance] [--format json|markdown|html|all]
```

Aggregates Phase 2 discovery + Phase 3 functional + Phase 4 performance
results into one `ProjectAssessment` — never re-discovers, re-executes, or
recomputes a metric those phases already produced. Seven categories
(narrowed from skill.md §12's illustrative list to what current evidence
actually supports, per the Phase 5 brief §2's "don't expand without
evidence" instruction): Project Discovery, Build / Project Health,
Testability, Functional Health, Performance, Configuration Hygiene, Test
Infrastructure. Each resolves to `PASS | WARNING | FAIL | UNKNOWN |
NOT_ASSESSED` via a documented, unit-tested, deterministic rule (no magic
numbers) — see `ARCHITECTURE.md` §9.3. `NOT_ASSESSED` categories never
count toward FAIL/WARNING/UNKNOWN nor toward a silent PASS; a category with
literally no assessable evidence resolves the *overall* project status to
`UNKNOWN`, never `PASS` by default. **No numeric quality score** — overall
status is one of the same five values, never `82/100`.

Safety (brief §19-20, non-negotiable): `assess ./project` alone — no
`--target`, no `--performance` — completes discovery and reports
`NOT_ASSESSED` for Functional Health and Performance without sending a
single byte of network traffic. Functional test *generation* (not
execution) is always attempted so the report can show what tests exist,
regardless of whether a target was given; execution requires `--target`.
Performance is opt-in via `--performance` even when `--target` is present —
`assess` never hides a load test inside its defaults — and reuses the
standalone `performance` command's full safety gate (interactive
confirmation or `--yes`, every planner safety ceiling) rather than a
lighter version.

Every category's evidence traces back to a Phase 2/3/4 result object
(`ProjectModel`/`RunResult`/`PerformanceResult`); findings carry
`severity` (`info|low|medium|high|critical`) *separately* from `status` —
the two are never conflated. Recommendations are deterministic strings
attached at finding-generation time, keyed by finding type — no AI.

The report's **Coverage** section is explicit about what was and wasn't
tested and why (five items: Discovery, API Discovery, Functional Execution,
Performance Execution, Database — the last two always show a reason when
below 100%). An **Unknown / Not Assessed** section always exists as its own
first-class part of the report — never merged into "everything passed."

### 4.8 Reporting (Phase 5 — implemented)

`universal-test assess` emits, per `--format` (default `all`):

- **`report.json`** — machine-readable, `schema_version` field present,
  containing `discovery`/`functional`/`performance` (the full Phase 2-4
  detail) alongside the `assessment` rollup, `findings`, `coverage`,
  `unassessed`, `recommendations`, `limitations`.
- **`report.md`** — human-readable, fixed section order: Executive Summary,
  Project Discovery, Technology Detection, Testability, Functional Testing,
  Performance, Findings, Recommendations, Coverage, Unknown / Not Assessed,
  Limitations, Execution Information.
- **`report.html`** — offline-openable static page (no CDN, no external
  JavaScript), every piece of scanned-project-derived text passed through
  `html.escape()`, showing overall status, critical findings, functional/
  performance summaries, coverage, and unknown areas at a glance.

Report generation is deterministic: the same discovery/functional/
performance input always produces the same `assessment`/`findings`/
`coverage` content — only the `generated_at` timestamp varies, and it never
feeds assessment logic. No random IDs, no AI-generated prose.

A trailing **Limitations** section is always present, stating plainly what
the assessment does *not* prove: security, absence of bugs, business
correctness, production readiness, complete test coverage.

### 4.9 Read-only database adapter (Phase 6 — implemented)

```
universal-test database <path> --database-profile <path.yaml> [--dry-run] [--format text|json|markdown]
universal-test assess <path> --database-profile <path.yaml> [... functional/performance flags]
```

- **Discovery never implies connection.** Phase 2's `discovery.database`
  detecting "SQL Server dependency present" in a project's manifests is
  evidence of technology use, not permission to connect. The database
  adapter connects **only** when the user supplies an explicit
  `--database-profile <path>` — never derived from anything `scan` found,
  never a credential read out of the scanned repository.
- **Profile** (`database:` YAML section): `engine` (`sqlserver
  |postgresql|mysql|sqlite`), `host/port/database` (or `path` for SQLite),
  `credentials.username_env`/`password_env` (named environment variables —
  the credential value is never written in the profile file itself), and
  `readonly: true` — **required to be the literal boolean `true`**; a
  missing key, `false`, or any other value refuses the connection outright
  rather than assuming safety.
- **No arbitrary SQL execution, structurally.** The adapter's entire
  capability surface is a fixed set of read-only metadata operations:
  connectivity check, schema/table/view discovery, column/primary-key
  /foreign-key/index metadata, and a safe (metadata-based, never a raw
  `SELECT COUNT(*)` on an unfamiliar large table) row-count estimate. There
  is no `execute_sql(...)` method anywhere in the codebase for this
  adapter — not a statement blocklist, an absent capability.
- **Supported engines**: SQL Server (`pyodbc`), PostgreSQL (`psycopg2`),
  MySQL (`mysql-connector-python`) — all optional, adapter-local
  dependencies (`pip install universal-test[database]`); SQLite via stdlib
  `sqlite3`, opened through a read-only URI so the connection itself cannot
  write. A missing driver never crashes the tool or the CLI — it resolves
  to `NOT_ASSESSED` with reason "Database driver is not installed."
- **Normalized model**: engine-independent `DatabaseInfo` →
  `DatabaseSchema` → `DatabaseTable`/`DatabaseView` →
  `DatabaseColumn`/`PrimaryKey`/`ForeignKey`/`DatabaseIndex`
  /`RowCountEstimate`. The assessment/reporting layers never see a raw
  driver cursor or row object.
- **Never a defect verdict from a schema observation.** Zero foreign keys,
  a table without a detected primary key, or metadata that couldn't be
  fully discovered are reported as informational/warning findings —
  `Database Health` never reaches `FAIL`. A connection failure, timeout, or
  missing driver is `NOT_ASSESSED`, never `FAIL` either — an
  access/environment problem is not evidence the assessed project's
  database is broken.
- **Timeouts**: connect and query timeouts are configurable in the profile
  (defaulting to 10s each) and enforced by each engine's native timeout
  mechanism; a timeout or refused connection degrades gracefully to
  `NOT_ASSESSED`, never hangs the CLI or crashes.
- **`--dry-run`** prints the assessment plan (engine, host/path, the fixed
  list of read-only operations, "Mode: READ ONLY") and opens **no**
  connection at all — no socket, no file handle.
- **Credentials never appear** in logs, console output, `report.json/.md
  /.html`, exceptions, or `AssessmentFinding`/`Evidence` — the profile's
  serialized form (`DatabaseProfile.to_dict()`) carries only
  `credentials: "configured" | "not configured"`, never the actual
  username/password, so there is no code path capable of leaking one.
- **Assessment integration**: an eighth category, "Database Health,"
  alongside Phase 5's seven; `NOT_ASSESSED` by default (no
  `--database-profile` given) — `assess ./project` alone still sends zero
  database traffic, matching the same safe-by-default guarantee functional/
  performance testing already give.
- Output: `--format text|json|markdown` for the standalone `database`
  command; `assess`'s unified `report.json/.md/.html` gains a `database`
  section (`null` when not assessed).
- **Explicitly not built this phase**: baseline/schema-diff regression,
  migration validation, arbitrary SQL execution, CI/CD integration, AI/LLM
  analysis, SQL-injection or other security testing, database load testing
  — all out of scope per the Phase 6 brief §25-26, deferred to a later,
  separately-approved phase.

### 4.10 Regression / baseline comparison engine (Phase 7 — implemented)

```
universal-test baseline save <path> --output baseline.json [--target ...] [--performance ...] [--database-profile ...]
universal-test baseline compare <path> --baseline baseline.json [same flags]
universal-test assess <path> --baseline baseline.json [...]
```

- **Answers a different question than `assess` alone.** `assess` answers
  "what does this project look like now"; `baseline save`/`compare` answer
  "did it get worse since a saved point in time" — a new capability, not a
  reinterpretation of Phase 5's output.
- **A baseline stores structured evidence, not a status string.** Every
  `baseline.json` carries `schema_version`, `tool_version`, `generated_at`,
  project identity, git commit/branch/dirty (when available — never the
  *sole* identity a comparison keys off of), and compact discovery/
  functional/performance/database/assessment summaries — never just
  `"Overall Status: WARNING"`.
- **Baseline is immutable.** `baseline save` only ever creates the file at
  the caller-supplied `--output` path; `baseline compare` and `assess
  --baseline` only ever read it. No code path in the tool modifies a
  baseline file once written.
- **Compare is read-only and never executes anything a plain `assess`
  wouldn't.** `baseline save`/`baseline compare` share the exact same
  `--target`/`--performance`/`--database-profile` opt-in flags and safety
  gates (interactive confirmation, planner ceilings) `assess` already has —
  omitting `--target` means zero functional execution and zero network
  traffic, exactly like `assess` today.
- **Functional regression compares by test ID**, not just aggregate pass/
  fail counts: `API-002: PASS -> FAIL` is reported specifically, not
  buried in "3 failures -> 4 failures". A test present in only one of the
  two runs is `ADDED`/`REMOVED`, never itself a regression verdict.
- **Performance regression respects metric direction and a configurable
  tolerance**: latency/error-rate/timeouts are "lower is better", RPS is
  "higher is better"; a percentage/absolute tolerance
  (`regression.performance` in `universal-test.yaml`, safe non-zero
  defaults if unconfigured) prevents ordinary measurement noise from being
  reported as a regression. Matched by concurrency level.
- **Database and discovery changes are always informational (`INFO`
  severity)**, never a defect verdict — a table/column/detected-technology
  appearing or disappearing is reported, not failed, unless a project later
  configures an explicit stricter policy (not built this phase).
- **Assessment-category regression** compares each Phase 5 category's
  status by name (not just the overall status), with deterministic
  severities for the worsening transitions the brief specifies:
  `PASS -> WARNING` = medium, `PASS -> FAIL` / `WARNING -> FAIL` = high.
- **No numeric quality score** — regression status is one of the same
  `PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED` values used everywhere else,
  never a computed delta score.
- **Schema-version compatibility is strict**: an unrecognized
  `schema_version` in a baseline file is refused outright with a clear
  error, never partially parsed. A differing *tool* version is not an
  error — both versions are recorded in the comparison output.
- Output: `--format text|json|markdown` for the standalone `baseline
  compare`; `assess`'s unified `report.json/.md/.html` gains a
  `regression` section (`null`/absent-content when no `--baseline` was
  given).
- **Explicitly not built this phase**: CI/CD integration, historical
  trend/multi-baseline tracking, an explicit "baseline policy" concept for
  escalating schema/discovery changes past `INFO`, and any AI-assisted
  regression explanation — all out of scope per the Phase 7 brief §20 and
  its own stop condition.

### 4.11 CI/CD integration + Quality Gate (Phase 8 — implemented)

```
universal-test assess <path> --ci --yes --target <url> --baseline baseline.json --output reports/
```

- **CI-provider-independent by construction.** No GitHub Actions/GitLab
  /Jenkins/Azure-specific logic exists in Core or in the `quality_gate/`
  package — only in documented, replaceable templates under `examples/ci/`.
- **Deterministic, configurable Quality Gate**, never scattered `if`
  statements: a `category -> [values]` policy (`quality_gate.fail_on`
  /`quality_gate.warn_on` in `universal-test.yaml`) that the evaluator
  takes as data. Safe default policy (brief §3, implemented exactly):
  `critical`/`high` regression, a real functional failure, and a
  performance threshold breach fail the build; `medium` regression, a
  database schema change, and a discovery change warn without blocking.
  `UNKNOWN`/`NOT_ASSESSED` never fail a build unless a project explicitly
  opts a specific rule (e.g. `database: [not_assessed]`) into its policy.
- **Stable exit-code contract** for `assess`: `0` = Quality Gate passed
  (a `WARNING`-level result still exits `0` — a warning doesn't block a
  build), `1` = Quality Gate failed, `2` = configuration error (bad
  `--format`, unreadable project path, an unloadable/incompatible
  `--baseline`), `3` = infrastructure/execution error. **A completely
  unreachable target is `3`, not `1`** — brief §18's explicit "target
  unavailable is an infrastructure error, not a quality regression" rule,
  distinguishable because Phase 5's `execution_health_status()` already
  separates "every request failed at the transport layer" (`FAIL`) from
  "some checks didn't pass against a target that *did* respond"
  (`WARNING`). A project can opt out of this distinction explicitly (e.g.
  `functional: [unreachable]` in `fail_on`) if it wants unreachability
  treated as an ordinary quality failure instead.
- **`--ci`** (assess-only): forces non-interactive behavior even if stdin
  happens to report a TTY (some CI runners attach a pseudo-tty), and
  prints a structured, machine-scannable console summary instead of the
  terse default two lines. **`--ci` never authorizes network traffic by
  itself** — a `--performance` run still requires `--yes` alongside it;
  omitting `--yes` in a non-interactive/`--ci` session produces a clear
  refusal and returns promptly, never hangs on a prompt nobody can answer.
- **CI environment detection** (`CI`/`GITHUB_ACTIONS`/`GITLAB_CI`
  /`JENKINS_URL`/`TF_BUILD`/etc.) is informational only — it improves a
  log message ("Detected CI environment: GitHub Actions") and nothing
  else. **Detecting a CI environment never relaxes safety** — it does not
  set `--yes`, does not skip confirmation, does not widen what a run is
  allowed to do.
- **Machine-readable + human-readable output together**: `report.json`
  gains a `quality_gate` key (status, exit code, findings, summary) —
  never console-text-only; `report.md`/`report.html` gain a "Quality Gate"
  section; the standalone structured `--ci` console summary never includes
  a secret (verified: a wrong bearer token producing a real gate failure
  still never leaks the token value anywhere in the output).
- **Baseline strategy**: CI never overwrites `baseline.json` as a side
  effect of running the gate — `assess`/`baseline compare` only ever read
  it (unchanged, immutable guarantee from Phase 7). Updating a baseline is
  always its own explicit, separately-triggered step (documented in each
  CI template) — a maintainer-triggered job or one restricted to the
  default branch, never something a pull-request's own quality-gate run
  does automatically.
- **Bounded, narrow retry** (`ci.retry.count` in `universal-test.yaml`,
  hard-capped at 2 regardless of configuration): retries `assess`'s
  functional-execution step only, and only when *every* executed request
  failed at the transport layer (a total wipeout indicating likely network
  instability) — never a partial failure, never a genuine assertion or
  threshold failure, so retry can never be used to mask a real regression.
- **CI provider templates** (`examples/ci/{github-actions,gitlab,jenkins}/`):
  each installs `universal-test` as a plain `pip install` (no provider
  SDK), shells out to `universal-test assess --ci --yes ...`, relies on
  the CLI's own exit code to pass/fail the job, and uploads `reports/` as
  a build artifact unconditionally (pass or fail) so a failing run's
  evidence is always retrievable. None assumes a project already has a
  running `localhost` service — the build/deploy/start-the-app step is
  always left as an explicit placeholder.
- **Explicitly not built this phase**: the `0/1/2/3` exit-code contract
  applies to `assess` only, not to `scan`/`test`/`performance`/`database`
  /`baseline save`/`baseline compare` (their pre-existing Phase 1-6
  conventions are unchanged); no numeric quality score (unchanged from
  Phase 5/7); no automatic branch-protection management (documented as a
  recommended workflow, not something this tool configures); no
  unbounded/automatic retry.

### 4.12 Frontend / Web Application Analysis (Phase 8.5 — implemented)

```
universal-test scan <path>
universal-test assess <path>
```

Discovery + testability assessment only — **not** browser/UI execution
(see §4.13, the Phase 9 Browser Adapter, for that). See
`docs/FRONTEND_ANALYSIS.md` for the full detail; summary:

- **Detection.** React, Next.js, Vue, Nuxt, Angular, Svelte, SvelteKit,
  Solid, Astro — via `package.json` dependency or framework config file
  only, never a prose/comment mention (verified by a dedicated
  false-positive test: a backend project whose README mentions "React"
  must not be detected as a React frontend). Build tools (Vite, Webpack,
  Rollup, Turbopack, Angular CLI) and package managers (npm/yarn/pnpm/bun)
  are reported as distinct facts from frameworks/meta-frameworks.
- **Test framework detection.** Jest, Vitest, Mocha, Karma, Jasmine,
  Testing Library (unit/component); Playwright, Cypress, WebdriverIO,
  Puppeteer (browser automation) — reported as separate categories so "has
  unit tests" and "has browser automation" are never conflated.
- **Bounded heuristic evidence** for routes/UI components/forms/
  frontend-API-client usage: a capped substring scan (up to 300 files
  under recognized frontend source roots), always labeled with its scan
  bound, never presented as exhaustive.
- **Read-only, offline, no script execution.** `package.json` `scripts`
  are copied as display-only strings, never executed; no `npm`/`node`/
  browser/network activity occurs during discovery (enforced by a test
  that fails if `subprocess`/`socket` is touched).
- **No secret leakage.** `.env.example`/`.env.template` contribute key
  names only — values are never captured.
- **Assessment**: a "Frontend / Web Application Health" category, capped
  below `FAIL` (missing test tooling is a testability gap, not proof of a
  defect) — same rule already used for database connectivity problems.
- **Explicit Discovery-vs-Execution boundary everywhere**: CLI, JSON/
  Markdown/HTML reports, and the GUI all show "Browser/UI Execution:
  NOT_ASSESSED" whenever a frontend is detected, so "frontend detected"
  is never read as "frontend tested."
- **Explicitly not built this phase**: no Playwright/Selenium execution,
  no visual regression, no AI test generation, no security/CVE scanning,
  no GraphQL/gRPC support.

### 4.13 Static Web Capability Detection & Assessment Semantics Hardening (same phase, follow-up)

**Capability detection extension.** A single rich HTML file (substantial
inline CSS/JS, browser API usage) is never misreported as "CSS: 0,
JavaScript: 0" — `inline_css_count`/`inline_js_count` are additive to the
existing external-file counts. New bounded, offline, read-only evidence:
interactive UI elements, browser APIs (microphone/MediaRecorder/speech
synthesis/storage/WebSocket/notifications/geolocation/clipboard/file
reading/IndexedDB — kept structurally separate from backend API-client
evidence), application pattern (static multi-page / single-page
application / static document, never asserted without real supporting
evidence), external resource evidence (a few well-known CDN/font hosts
normalized to a friendly label, never fetched), and
Content-Security-Policy evidence. Authentication-UI detection was
hardened: a real password field is strong evidence on its own; generic
storage/header markers only count as weak evidence, and only when
co-occurring with an actual `<form>` — a README/comment mentioning
"login"/"password"/"authentication" was never sufficient and still isn't.

**Assessment semantics — additive only, nothing removed or renamed.**
`overall_status`, `compute_overall_status`, Quality Gate, regression,
baseline, and CLI exit codes are completely unchanged — this project
deliberately does not introduce a false `PASS` or a numeric quality score
to make results "look better." Instead:

- Every `AssessmentFinding` gained a `classification`
  (`defect`/`testability_gap`/`not_assessed`/`informational`/
  `execution_failure`) so a report/GUI can say, explicitly, whether a
  `WARNING` means a confirmed problem or a testability limitation.
- `ProjectAssessment` gained two new, independent fields:
  `application_health` ("no confirmed defects" unless something that
  actually *executed* against the live project — Functional Health or
  Performance — reported a real problem) and `assessment_completeness`
  ("full"/"partial", derived from existing coverage/unassessed data).
- A static website with no build system, or a project with no automated
  test framework, is never presented as a build or application defect —
  `Build / Project Health` reads `PASS` for a genuine static site (a
  package manager/build tool is architecturally not required), and
  missing-test-framework findings are labeled `testability_gap` with
  wording that explicitly states this does not indicate the application
  has a defect. `Project Discovery` no longer reads `UNKNOWN`/"0
  languages" for a valid static HTML/CSS/JS site.

See `docs/FRONTEND_ANALYSIS.md` and `ARCHITECTURE.md` §16.8 for the full
detail, including the precise rule `compute_application_health` uses and
why it's a category whitelist rather than a classification-based
aggregation.

### 4.14 Browser / Web UI Functional Testing (Phase 9 — implemented)

```
universal-test browser install [--engine chromium|firefox|webkit]
universal-test browser test <path> --target <url> [--allow-external] [--screenshots] [--dry-run] [--yes]
universal-test assess <path> --target <url> --browser [--allow-external] [--screenshots] --yes
```

Real, bounded, explicitly-authorized browser execution on top of §4.12's
`FrontendInfo` discovery evidence. See `docs/BROWSER_TESTING.md`/
`docs/BROWSER_SAFETY.md` for full detail; summary:

- **Optional dependency, explicit binary install.** `playwright` is an
  optional `[browser]` extra; the base install and every other capability
  work with zero of it present. The browser binary itself is downloaded
  only by the explicit `browser install` subcommand — never during `scan`,
  `assess`, or GUI startup.
- **Disabled by default everywhere.** A detected frontend never triggers
  browser execution; `assess` requires `--browser` AND `--target` AND
  (`--yes` or an interactive confirmation); the GUI requires an explicit
  confirmation checkbox in addition to the feature checkbox.
- **Explicit target, target safety policy.** `localhost`/`127.0.0.1`/
  `::1`/`file://` allowed by default; any other target requires
  `--allow-external`. No port scanning, no guessed targets, no following
  URLs found in scanned content.
- **No second test engine.** Reuses the existing `TestEngine`/
  `AssertionEngine`/`Orchestrator` unmodified — browser-specific assertion
  evaluators are registered on a dedicated `AssertionEngine` instance,
  never the shared REST/DB default.
- **Conservative default smoke test**: navigate, assert page loaded,
  assert title exists, capture console/page-error/network-failure
  evidence — never clicks, submits a form, uploads a file, or requests a
  browser permission automatically, even when static analysis detected
  those capabilities on the page.
- **Explicit test definitions** support a fixed action set (`navigate`/
  `click`/`fill`/`select`/`check`/`uncheck`/`press`/`wait_for`), robust
  selectors (`role`/`label`/`text`/`placeholder`/`test_id`/`css`), and a
  fixed assertion set (`visible`/`hidden`/`text_contains`/`text_equals`/
  `url_equals`/`url_contains`/`page_title`/`element_count`/
  `attribute_equals`/`input_value`/`checked`/`enabled`/`disabled`/
  `console_summary`). No arbitrary JavaScript execution is exposed.
- **Fresh isolation, no auto-granted permissions.** One fresh browser
  context per run (no cookie/storage/cache reuse across runs); microphone/
  camera/geolocation/notifications/clipboard permissions are never
  auto-granted; browser storage (localStorage/sessionStorage/cookies/
  IndexedDB) is never read into evidence.
- **Failure classification**: `PASS` (assertions passed), `FAIL` (an
  assertion failed), `ERROR` (target unreachable/selector ambiguous or
  missing/timeout — infrastructure evidence, not proof of a defect),
  `NOT_ASSESSED` (browser missing, or testing not requested).
- **Redaction reuse.** Console/network/element evidence passes through the
  existing `core/redaction.py` before becoming part of any result/report —
  no second redaction system.
- **Bounded timeouts, guaranteed cleanup.** Every timeout is hard-capped
  independent of configuration; browser/context/driver cleanup is
  guaranteed via `finally` even on exception/timeout/Ctrl+C.
- **Assessment/Reporting/Quality Gate/Regression integration**: a tenth
  "Browser Testing" assessment category (execution-driven, like Functional
  Health/Performance); a "Browser Testing" report section (json/markdown/
  html); Quality Gate needs no engine changes (data-driven policy already
  handles a new category); `regression/browser_compare.py` mirrors
  `functional_compare.py` (per-test-ID PASS/FAIL/ERROR, no numeric score).
- **Explicitly not built this phase**: AI-generated test plans, visual
  regression, accessibility auditing, security scanning, distributed/cloud
  browser providers, automatic project server startup, arbitrary
  JavaScript execution as a user action, automatic credential discovery.

**Static Web Analysis extension (same phase, follow-up enhancement).** A
project needs no `package.json`, lockfile, or config file at all to be
recognized as a frontend — a plain static HTML/CSS/JavaScript website is a
first-class `FrontendType.STATIC_WEB`, not a degraded fallback of the
framework case. Classification (`STATIC_WEB`/`FRAMEWORK_WEB`/
`FULL_STACK_WEB`/`UNKNOWN_WEB`) always gives framework/config evidence
precedence over a static-HTML guess — a React project's own `index.html`
never reclassifies it as Static Web. Conservative false-positive guards
(brief §20) keep generated documentation (`docs/`), code-coverage reports
(`coverage/`/`htmlcov/`, excluded from discovery entirely), and
server-rendered backend templates (`templates/`) from being misclassified
as a standalone static frontend — a lone HTML file in one of those
locations with no supporting CSS/JS is not detected as a frontend at all.
Detected static sites additionally report HTML/CSS/JS file counts, entry
point(s) (or an explicit "multiple web roots" note for monorepos),
navigation-link evidence, form/API-client/responsive-design/
authentication-UI structural evidence, and known CSS framework evidence
(Bootstrap/Tailwind/Bulma/Foundation, matched by filename/link, never by
an arbitrary class name) — all bounded, offline, and never executing any
HTML/CSS/JavaScript. See `docs/FRONTEND_ANALYSIS.md`.

### 4.15 One-Click Web Assessment / Non-Programmer UX (Phase 10 — implemented)

```
universal-test web assess <path> [--target <url>] [--allow-external] [--screenshots] [--dry-run] [--yes] [--baseline <path>]
```

Not a new testing engine — a guided preset over the existing `assess`
pipeline (discovery + static analysis + browser smoke test + report),
scoped to non-programmer usability. See `ARCHITECTURE.md` §18 for
implementation detail; summary:

- **CLI**: `web assess` forces `--browser` on and defaults out performance/
  database flags, then delegates to the same `_run_assess()` the plain
  `assess` command uses — no duplicate discovery/execution/assessment/
  report code. `--dry-run` prints a human-readable plan (detected type,
  planned checks, not-included list, generated browser test plan) without
  launching a browser.
- **GUI**: a "Web Assessment" card (pick project → "Analyze Project &
  Build Plan" → plan + confirmation → run) alongside the pre-existing
  "Full Assessment" form, not replacing it. Calls a new read-only
  `POST /api/web/detect` (wraps the existing `discover()`, returns
  `FrontendInfo` — no HTML re-parsing in the GUI) for the pre-flight plan,
  then the *same* `/api/assess` endpoint the Full Assessment form already
  used for actual execution — one run-tracking system, one results
  renderer.
- **Web detection**: reuses `FrontendType`
  (`STATIC_WEB`/`FRAMEWORK_WEB`/`FULL_STACK_WEB`/`UNKNOWN_WEB`) and
  `FrontendInfo.detected` unmodified. A non-web project is never treated
  as a failure — "no web frontend detected, Full Assessment still
  available."
- **Safety unchanged**: explicit target still required for real browser
  execution (never guessed); `--yes`/interactive confirmation and the
  GUI's separate confirmation checkbox are unchanged from Phase 9;
  `--allow-external`/external-target policy unchanged; the GUI's
  external-target warning is a presentation-only heuristic, never the
  actual security boundary.
- **Result summary**: Application Health / Testability / Assessment
  Coverage / Browser Testing render as four distinct, independently
  explained lines (no numeric score, ever) at the top of the results
  screen, reusing the Phase 8.5/9 summary card with one added line.
- **Explicitly not built this phase**: no Web Test Scenario/Workflow
  authoring, no AI-generated tests, no visual regression, no accessibility
  scanning, no security scanning, no browser performance profiling, no
  mobile/cloud/distributed browser testing, no automatic login discovery,
  no automatic project-server startup.

### 4.16 Web Test Scenario / Workflow Testing (Phase 11 — implemented)

```
universal-test browser scenario list <path> [--scenario-file <path>]
universal-test browser scenario validate <path> [--scenario-file <path>]
universal-test browser scenario run <path> --scenario <id> [--all] --target <url> [--dry-run] [--yes] [--allow-external] [--screenshots]
universal-test assess <path> --target <url> --scenario <id> [--scenario <id> ...] --yes
```

An explicit, user-authored, repeatable multi-step Web workflow layer — not
a new test engine. See `ARCHITECTURE.md` §19 and `docs/WEB_SCENARIOS.md`
for implementation detail; summary:

- **Scenario model**: framework-independent, serializable
  (`WebScenario`/`ScenarioStep`, plain dataclasses, no Playwright objects)
  loaded from a dedicated YAML file (default `universal-test-web.yaml`,
  not forced into `universal-test.yaml`). Each step is either one real
  browser action or one `assert_*` action, never both.
- **Full reuse**: every action maps onto the existing `ALLOWED_ACTIONS`;
  every `assert_*` action maps onto an existing browser `AssertionEngine`
  evaluator; selectors reuse `BrowserSelector` unmodified. One step = one
  synthesized `TestCase` run through the unmodified `TestEngine.run()`.
- **Secret-safe by construction**: `value_env` (an environment-variable
  *reference*) is the normal mechanism for any credential-shaped value;
  resolved only at the last possible moment during real execution, never
  during `list`/`validate`/`--dry-run`; never appears in any report/log/
  GUI response (`value_env` name shown, resolved value never captured).
- **Validation** (`browser scenario validate`, and automatically before
  every real run) is pure/offline — missing/duplicate ids, unknown
  actions, missing required parameters, invalid selectors, malformed
  `value_env` references, out-of-range timeouts — and never itself
  triggers browser execution.
- **Sequential execution, stop-on-failure**: steps run in order sharing
  one browser context; the first non-PASS step stops the scenario, every
  subsequent step is recorded `SKIPPED`.
- **Timeout hierarchy**: `Run > Scenario > Step`, each child capped to the
  remaining parent budget, implemented via a one-line additive parameter
  (`test_timeout_seconds_override`) on the existing Phase 9 Hardening
  per-TestCase timeout mechanism — no second timeout system.
- **Status semantics**: `PASS`/`FAIL`/`ERROR`/`NOT_ASSESSED`, same meanings
  as Browser Testing (§4.14) — `ERROR` never implies an application
  defect, `NOT_ASSESSED` never silently becomes `PASS`.
- **Safety unchanged**: explicit target only, localhost/`--allow-external`
  policy unchanged, no permission auto-grants, no arbitrary JavaScript
  execution, fresh browser context, hard-capped timeouts, existing
  `core/redaction.py` reused, guaranteed process cleanup, and the same
  explicit `--yes`/GUI-confirmation-checkbox gate every other
  browser-launching command requires.
- **Assessment/Regression/Reporting**: an eleventh "Web Scenarios"
  assessment category (execution-driven, mirrors Browser Testing);
  `regression/scenario_compare.py` (per-scenario-ID identity comparison,
  stable IDs, no numeric score); JSON/Markdown/HTML report sections.
  Quality Gate needed zero engine changes (policy-driven, automatic).
- **No automatic test generation**: static analysis evidence (forms,
  buttons, links) is never automatically turned into a scenario step —
  a scenario is only ever what the user explicitly wrote.
- **Explicitly not built this phase**: AI-generated tests, an autonomous
  browser agent, visual regression, accessibility/security scanning,
  browser performance profiling, mobile/cloud/distributed browser testing.

## 5. Cross-cutting requirements (apply to every phase)

| Requirement | Rule |
|---|---|
| Overclaiming | Never turn "no test found" into "broken", or "no vuln found" into "secure". Every status is one of `detected / tested / passed / failed / skipped / unknown / inferred / not_applicable`. |
| Safety | No destructive filesystem/DB/cloud/credential actions, ever, by default. Performance tests require an explicit `--target`. |
| Evidence | Every `TestResult`/`Finding` carries an `evidence` list — never a bare verdict. |
| Secrets | Redact `password`, `secret`, `token`, `api_key`, `authorization`, connection-string credentials, private keys from all logs/reports/exceptions/generated tests. |
| AI | Optional, off by default, never required for core function; output always labeled "AI-generated hypothesis". Not implemented until Phase 9. |
| Unknown-is-a-result | `UNKNOWN` / `NOT_ASSESSED` are first-class outcomes, distinct from pass/fail. |

## 6. Out of scope for now (tracked, not built)

GraphQL, gRPC, message queues, mobile apps, Kubernetes/cloud resource
provisioning, blockchain/EVM, distributed load testing, mutation testing, code
coverage analysis, SBOM/dependency-vulnerability scanning, chaos testing,
self-healing tests. See `skill.md` §28.

## 7. Acceptance criteria for "First Implementation Goal" (skill.md §30)

Given an unfamiliar REST/OpenAPI project the tool can: scan the repo, detect the
API, discover endpoints, connect to an explicitly configured target, generate
conservative functional tests, execute them, collect latency/error data, identify
failures, and produce JSON+MD+HTML reports that clearly separate known results
from unknown/unassessed areas.

**As of Phase 5, this milestone is closed**: `universal-test assess
<path> --target <url>` scans the repo, detects the API, discovers
endpoints, connects to the explicit target, generates conservative
functional tests, executes them, collects latency/error data, identifies
failures, and produces `report.json`/`report.md`/`report.html` that
clearly separate known results (categories with a real `PASS/WARNING/FAIL`
status) from unknown/unassessed areas (a dedicated Unknown/Not-Assessed
section, never silently merged into a passing result). `scan`/`test`
/`performance` still additionally offer their own lightweight per-command
serializers for users who only want one phase's output without a full
assessment.
