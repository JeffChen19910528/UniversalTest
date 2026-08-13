# Universal Test

English | [繁體中文](README.zh-TW.md)

A project-agnostic CLI for initial software-quality assessment: read-only
discovery, conservative REST/OpenAPI functional testing, bounded
performance testing, read-only database assessment, baseline/regression
comparison, and a deterministic CI Quality Gate — with evidence-based
JSON/Markdown/HTML reports.

> **Universal Test is not a security scanner, a QA replacement, a
> correctness guarantee, or an autonomous testing agent.** It produces an
> initial, evidence-based assessment — conservative, read-only/safe-by-
> default, and deterministic. See "Limitations" below.

## What It Does

Given an unfamiliar or your own project, Universal Test:

1. **Discovers** what the project is — language, framework, build system,
   infrastructure, database, and API evidence — without modifying it or
   running any of its code.
2. **Generates and runs conservative functional tests** against an OpenAPI
   spec, if you point it at a running instance of the API.
3. **Runs bounded-concurrency performance tests**, if you opt in.
4. **Assesses a database's schema** read-only, if you give it explicit
   credentials — never by executing arbitrary SQL.
5. **Compares a run against a saved baseline** to detect regressions —
   functional, performance, database schema, and discovery changes.
6. **Evaluates a deterministic Quality Gate** and returns a stable exit
   code your CI pipeline can act on directly.
7. **Reports** everything as `report.json`/`report.md`/`report.html` —
   every finding traces to evidence, and `UNKNOWN`/`NOT_ASSESSED` are
   first-class outcomes, never silently folded into pass or fail.

## Installation

Requires Python 3.11+.

```bash
pip install universal-test
```

To assess a SQL Server, PostgreSQL, or MySQL database, also install the
optional database-driver extra (not needed for SQLite, which uses the
Python standard library):

```bash
pip install "universal-test[database]"
```

## Quick Start

```bash
universal-test scan ./my-project
```

This is always safe: it's a read-only scan that never touches the network
or executes anything in your project.

If your project has a running API, point `assess` at it:

```bash
universal-test assess ./my-project --target http://localhost:8000
```

A few things to know before you do:

- **`--target` must always be explicit.** Universal Test never guesses a
  host to test against, and an OpenAPI document's own `servers:` entry is
  never used as a substitute.
- **`assess` with no `--target` sends zero network traffic** — it still
  completes discovery and reports `NOT_ASSESSED` (with a reason) for
  Functional Health and Performance, rather than skipping them silently.
- **Performance testing is opt-in** (`--performance`), on top of
  `--target`, and always shows a plan and asks for confirmation before
  sending real load (or requires `--yes` for non-interactive use).
- **Database assessment requires an explicit `--database-profile`.**
  Discovering "PostgreSQL" as a dependency in your project never implies
  permission to connect to it.
- **Credentials are never read from your repository.** They come only
  from named environment variables you specify on the command line
  (`--bearer-token-env`, a profile's `username_env`/`password_env`, etc.).

## Graphical User Interface

Prefer clicking over typing commands? `universal-test` also ships a local,
browser-based GUI — no Python, terminal, or command-line knowledge
required.

```bash
universal-test gui
```

This starts a server on `127.0.0.1` (never reachable from the network) and
opens your default browser to it. From there you can pick a project
folder, optionally enter a test target, choose which checks to run, and
click "開始專案健檢" / "Start Assessment" — the GUI calls the exact same
discovery/testing/assessment pipeline as the CLI, just with plain-language
progress and results instead of flags and JSON.

For web projects specifically, a "Web Assessment" card offers a guided
one-click path: pick a project, click "Analyze Project & Build Plan" to see
what Universal Test detected (static/framework/full-stack web, or "no web
frontend detected") and exactly what will and won't be tested, confirm,
then run — no need to understand checkboxes for performance/database/REST
testing at all. The detailed "Full Assessment" form below it remains
available for anyone who wants that level of control.

The result dashboard shows
the same Quality Gate verdict and Regression comparison `assess --baseline`
computes, performance testing lets you pick which API endpoint to target
when more than one exists, and API authentication (Bearer/API key/Basic)
is configured by naming an environment variable, never by typing a secret
into the browser. See `docs/GUI_USER_GUIDE.md` for a full walkthrough,
`docs/GUI_SAFETY.md` for its safety guarantees, and
`docs/GUI_ARCHITECTURE.md` for how it's wired to the CLI's shared Core.

## Windows One-Click Application

There is no pre-built `UniversalTest.exe` shipped in this repository or
as a download — it has to be built once, locally, from source. After
that one build, the result is a normal portable folder you (or anyone
without Python installed) can double-click forever after; you don't
rebuild it again unless the source changes.

**Build it once** (needs Python 3.11+ and this repo checked out):

```powershell
pip install ".[packaging]"
powershell -File release/windows/build.ps1
```

**Then find and run it:**

```
dist\windows\UniversalTest\UniversalTest.exe
```

Double-click `UniversalTest.exe` in File Explorer (or run it from a
terminal). It runs windowed — no console window — and your default
browser opens to the GUI. If the browser doesn't open automatically, a
small dialog box shows the local address to open manually. The whole
`dist\windows\UniversalTest\` folder is portable — copy it anywhere, or
onto a USB drive / another Windows machine, and `UniversalTest.exe` still
works with no Python install there.

Optional database drivers (PostgreSQL/MySQL/SQL Server) are not bundled;
the GUI reports that a database check needs an extra driver rather than
crashing if one is missing.

## Commands

### `scan`

Read-only project discovery: language, project type, framework, build
system, infrastructure/CI evidence, database evidence, API evidence, test
framework, and secret *patterns* (never values).

```bash
universal-test scan ./my-project
universal-test scan ./my-project --format json --output ./out
```

### `test`

Parses an OpenAPI 3.x document, generates conservative positive/negative
functional tests, and — only with `--target` — executes them over HTTP.

```bash
universal-test test ./my-project --dry-run
universal-test test ./my-project --target http://localhost:8000
universal-test test ./my-project --target http://localhost:8000 \
    --bearer-token-env API_TOKEN   # reads the env var; the token itself never appears on the command line
```

`--dry-run` shows what would run without sending any HTTP requests:

```text
Discovered: 2 endpoints
Generated: 4 test cases

API-001
GET /users
Expected: 200
...
No HTTP requests executed.
```

### `performance`

Bounded-concurrency load testing against one endpoint. `--target` is
required even for `--dry-run` — a performance plan without a known target
isn't a plan.

```bash
universal-test performance ./my-project --target http://localhost:8000 \
    --endpoint /api/users --method GET --dry-run
universal-test performance ./my-project --target http://localhost:8000 \
    --endpoint /api/users --method GET \
    --profile load --concurrency 1,10,50 --requests 100 --yes
```

Without `--dry-run`/`--yes`, it prints the plan and asks `Proceed? [y/N]`
before sending any request. Every numeric knob (concurrency, requests,
duration, levels) has a hard safety ceiling regardless of what you
configure.

### `database`

Read-only schema/table/view/column/key/index assessment. Connects **only**
to an explicitly configured database — never one merely detected in your
project's manifests — and has no arbitrary-SQL-execution capability at
all.

```yaml
# database.yaml — never commit real credentials; put them in env vars
database:
  engine: postgresql       # sqlserver | postgresql | mysql | sqlite
  host: localhost
  port: 5432
  database: my_app_dev
  credentials:
    username_env: DB_USER      # read from $DB_USER at run time
    password_env: DB_PASSWORD  # read from $DB_PASSWORD at run time
  readonly: true            # required -- omitting this (or setting it to
                             # false) refuses the connection outright
```

```bash
export DB_USER=readonly_user
export DB_PASSWORD=...
universal-test database ./my-project --database-profile ./database.yaml --dry-run
universal-test database ./my-project --database-profile ./database.yaml
```

`--dry-run` opens no connection at all — it only prints the plan (engine,
host, the fixed list of read-only operations, "Mode: READ ONLY"). A
missing database driver (e.g. `pyodbc` for SQL Server) degrades to
`NOT_ASSESSED` with an install hint, never a crash.

### `browser`

Real, bounded, explicitly-authorized browser/UI testing (optional
`pip install universal-test[browser]` extra). Disabled unless you
explicitly ask for it — a detected frontend never triggers it.

```bash
universal-test browser install                                   # explicit, one-time browser binary download
universal-test browser test ./my-site --target http://localhost:8080 --dry-run
universal-test browser test ./my-site --target http://localhost:8080 --yes
```

No port scanning, no guessed targets. `localhost`/`127.0.0.1`/`::1`/
`file://` are allowed by default; anything else needs `--allow-external`.
No credential guessing, no auto-granted browser permissions (microphone/
camera/geolocation), no arbitrary JavaScript execution. See
`docs/BROWSER_TESTING.md` and `docs/BROWSER_SAFETY.md`.

### `web assess`

A guided, non-programmer-friendly one-command Web Assessment: project
discovery + static frontend analysis + browser smoke test + report, without
needing to know `scan`/`assess`/`browser test` as separate concepts. It is
a thin, safe preset over the *same* `assess` pipeline above — not a second
engine — scoped to static analysis and browser testing only (no
performance/database testing).

```bash
universal-test web assess ./my-site --target http://localhost:8080 --dry-run
universal-test web assess ./my-site --target http://localhost:8080 --yes
universal-test web assess ./my-site   # no target: static analysis only, Browser Testing shows NOT ASSESSED
```

The GUI exposes the same guided flow as a "Web Assessment" card: pick a
project, click "Analyze Project & Build Plan" to see what was detected
(static/framework/full-stack web, or "no web frontend detected") and
exactly what will and won't be tested, then confirm before anything
executes. See `docs/BROWSER_TESTING.md`.

### `browser scenario`

An explicit, user-authored, repeatable multi-step Web workflow — "log in,
then verify the dashboard" — rather than a single smoke test. Defined once
in a YAML file (default `universal-test-web.yaml`), not a new test engine:
each step reuses the same Browser Adapter actions/assertions/selectors
`browser test` already uses.

```bash
universal-test browser scenario list ./my-site
universal-test browser scenario validate ./my-site
universal-test browser scenario run ./my-site --scenario login-smoke --target http://localhost:3000 --dry-run
universal-test browser scenario run ./my-site --scenario login-smoke --target http://localhost:3000 --yes
```

Secrets use `value_env: TEST_PASSWORD` (an environment-variable
*reference*), never a literal password in the file — resolved only at
execution time, never during `list`/`validate`/`--dry-run`, and never
shown in a report/log. Steps run in order and stop at the first one that
doesn't PASS; `assess --scenario <id> --target ... --yes` folds the result
into the unified report as a "Web Scenarios" category. See
`docs/WEB_SCENARIOS.md`.

### `assess`

Ties discovery, functional, performance, database, and regression results
into one evidence-based report: an overall `PASS/WARNING/FAIL/UNKNOWN`
status, per-category findings, coverage, and an explicit Unknown/Not-
Assessed section.

```bash
universal-test assess ./my-project
universal-test assess ./my-project --target http://localhost:8000
universal-test assess ./my-project --target http://localhost:8000 --performance --yes
universal-test assess ./my-project --target http://localhost:8000 --browser --yes
universal-test assess ./my-project --database-profile ./database.yaml
universal-test assess ./my-project --format json --output ./reports
```

```text
Overall Status: WARNING
```

```json
{
  "assessment": {
    "overall_status": "warning",
    "categories": [
      {"name": "Functional Health", "status": "not_assessed",
       "reason": "no execution target was provided"},
      {"name": "Performance", "status": "not_assessed",
       "reason": "performance execution was not enabled (pass --performance)"}
    ]
  }
}
```

### `baseline`

A baseline is a point-in-time snapshot of discovery/functional/
performance/database/assessment results. Save one, keep it (e.g. commit
it alongside a release tag), then compare later runs against it.

```bash
universal-test baseline save ./my-project --target http://localhost:8000 --output baseline.json

# ...later, after changes...
universal-test baseline compare ./my-project --target http://localhost:8000 --baseline baseline.json
```

`baseline compare` is **read-only** — it never writes to `baseline.json`,
and it never executes anything `assess` wouldn't (functional tests only
run with `--target`, performance only with `--target --performance`,
database comparison only with `--database-profile`). It reports:

- **Functional regressions by test ID** (e.g. `API-002: PASS -> FAIL`),
  not just aggregate pass/fail counts.
- **Performance regressions**, direction-aware (latency/error-rate/
  timeouts are "lower is better", RPS is "higher is better") and
  tolerance-based, so ordinary measurement noise isn't flagged.
- **Database and discovery changes**, always informational — a table or
  detected technology appearing/disappearing is reported, never scored as
  a defect.
- **Assessment-category status transitions** (e.g. `Performance: PASS ->
  FAIL`).

```yaml
# universal-test.yaml -- performance regression tolerances (safe defaults shown)
regression:
  performance:
    p95_percent: 10          # P95 latency may increase up to 10% before flagging
    p99_percent: 10
    rps_percent: 10           # throughput may drop up to 10% before flagging
    error_rate_absolute: 1    # error rate may rise up to 1 percentage point before flagging
```

### CI/CD

`universal-test assess` is the CI/CD entry point. It evaluates a
deterministic **Quality Gate** against the assessment + regression results
and returns a stable exit code your pipeline can act on directly.

> **CI mode does not automatically authorize network traffic.** `--ci`
> only changes *how* the tool behaves (non-interactive, stable output); it
> never substitutes for `--yes`. Detecting a CI environment
> (`CI`/`GITHUB_ACTIONS`/`GITLAB_CI`/`JENKINS_URL`/etc.) is purely
> informational and never relaxes safety either.

```bash
universal-test assess . --ci --yes --target http://localhost:8080 --baseline baseline.json --output reports/
echo "exit code: $?"
```

See "Regression" and "Safety Model" below for the Quality Gate policy,
exit-code contract, and CI provider templates.

## Configuration

`universal-test.yaml` at the project root is entirely optional — every
command runs with safe defaults if it's absent. All sections:

```yaml
performance:
  thresholds:
    p95_ms: 500
    error_rate_percent: 1
    min_rps: 50

regression:
  performance:
    p50_percent: 10
    p90_percent: 10
    p95_percent: 10
    p99_percent: 10
    rps_percent: 10
    error_rate_absolute: 1

quality_gate:
  fail_on:
    regression: [critical, high]
    functional: [failure]
    performance: [threshold]
  warn_on:
    regression: [medium]
    database: [schema_change]
    discovery: [change]

ci:
  retry:
    count: 1   # hard-capped at 2 regardless of what you configure

database:
  enabled: false   # informational; actual database access always requires --database-profile
```

Every value shown above is the **default** — you only need to write a key
if you want to change it. Overriding one sub-key (e.g. `quality_gate
.fail_on.regression`) leaves every other default untouched; partial
overrides never silently disable the rest of a section.

## Reports

`assess` emits `report.json` (machine-readable, schema-versioned,
deterministic), `report.md`, and `report.html` (offline-openable, no CDN
or external JavaScript) — by default all three, to `./reports/`.

Every report includes: overall status, per-category findings with
evidence, coverage, an explicit Unknown/Not-Assessed section, a
Regression section (when `--baseline` was given), a Quality Gate section,
and a Limitations section stating plainly what the assessment does *not*
prove. No password, token, API key, cookie, Authorization header, or
connection-string credential ever appears in any report, log, or
exception — enforced by dedicated redaction and verified against real
HTTP responses in the test suite.

### Understanding report status

`PASS`/`WARNING`/`FAIL`/`UNKNOWN`/`NOT_ASSESSED` answer different
questions, and are never collapsed into one meaning:

- **`WARNING` does not mean "broken."** It may indicate a testability
  limitation (no automated test framework detected) or an incomplete
  assessment, not necessarily an application defect. Every finding is
  additionally labeled with a `classification`
  (`defect`/`testability_gap`/`not_assessed`/`informational`/
  `execution_failure`) so you can tell which one applies.
  `Application Health` (shown separately from the overall status in every
  report and the GUI) reflects only categories driven by something that
  actually *executed* against your project (functional/performance
  testing) — a `PASS` there means no confirmed defect was found, even if
  other categories show `WARNING` for missing test tooling.
- **`NOT_ASSESSED` is not `PASS` and not `FAIL`.** It means that capability
  wasn't run this time (no target provided, performance not enabled, no
  database profile configured) — not that it succeeded or failed.
- **Static analysis detects capabilities and evidence; it cannot prove
  runtime behavior.** A detected browser API, form, or interactive element
  is evidence the code exists, not proof it works when actually run — that
  distinction is why "Browser/UI Execution" is reported separately from
  static frontend analysis. It stays `NOT_ASSESSED` unless you explicitly
  opt in with `assess --browser --target ... --yes` (or
  `universal-test browser test`) — see `docs/BROWSER_TESTING.md`.
- **Quality Gate `PASS` means no configured gate rule failed** — it does
  not mean the entire application was verified correct; **`FAIL`** means a
  configured condition failed, detailed in the findings below it.

## Regression

See the `baseline` command above for usage. The Quality Gate policy that
turns a regression comparison into a pass/warn/fail decision:

```yaml
quality_gate:
  fail_on:
    regression: [critical, high]
    functional: [failure]
    performance: [threshold]
  warn_on:
    regression: [medium]
    database: [schema_change]
    discovery: [change]
```

This is the default — `UNKNOWN`/`NOT_ASSESSED` results (e.g. no
`--database-profile` was given) never fail a build unless you explicitly
opt a rule in, e.g. `fail_on: {database: [not_assessed]}`.

**A completely unreachable target is never treated as a quality
regression by default** — see the exit-code table below. Opt a project
into treating it as one with `fail_on: {functional: [unreachable]}`
/`{performance: [unreachable]}`.

### Exit codes (`assess` only)

| Code | Meaning |
|---|---|
| `0` | Quality Gate passed (a `WARNING`-level result still exits `0` — a warning never blocks a build) |
| `1` | Quality Gate failed (a configured `fail_on` rule matched) |
| `2` | Configuration error (bad `--format`, unreadable project path, an unloadable/incompatible `--baseline`) |
| `3` | Infrastructure/execution error (the target was completely unreachable) |

Every other command (`scan`/`test`/`performance`/`database`/`baseline
save`/`baseline compare`) uses `0` for success and `2` for a CLI/
configuration error only.

### Pull request workflow

Branch protection itself is configured in your CI provider, not by this
tool:

```text
main branch  ---------->  universal-test baseline save . --target <url> --output baseline.json
                           (commit baseline.json; its own separate, deliberate step)

feature branch  ---->  universal-test assess . --ci --yes --target <url> --baseline baseline.json
                           |
                           +-- exit 0/warning  -> PR allowed
                           +-- exit 1          -> PR blocked (regression / quality-gate failure)
                           +-- exit 3          -> infrastructure problem, not a regression verdict
```

**CI never overwrites `baseline.json` as a side effect of running the
gate** — `assess --baseline`/`baseline compare` only ever read it. Update
it deliberately, as its own separate step (a maintainer-triggered job, or
one restricted to your default branch).

### CI provider templates

Starting points, not working pipelines — each leaves your project's own
build/deploy/start-the-application step as an explicit placeholder, since
Universal Test never starts, builds, or deploys the project it's
assessing. Each installs `universal-test` as a plain `pip install` (no
provider SDK), relies on the CLI's own exit code, and uploads `reports/`
as a build artifact unconditionally (pass or fail):

- [`examples/ci/github-actions/universal-test.yml`](examples/ci/github-actions/universal-test.yml)
- [`examples/ci/gitlab/universal-test.yml`](examples/ci/gitlab/universal-test.yml)
- [`examples/ci/jenkins/Jenkinsfile`](examples/ci/jenkins/Jenkinsfile)

## Safety Model

- **Repository**: discovery is entirely read-only. It never modifies your
  project, installs dependencies, starts containers, or executes any
  script in it (`setup.py`, `package.json` scripts, a `Makefile`, a
  `Dockerfile`, or a CI config's own commands) — the only external process
  this tool ever runs is a read-only `git rev-parse`/`git status
  --porcelain`.
- **Network**: no request is ever sent without an explicit `--target`. An
  OpenAPI document's own `servers:` entry is never used as a substitute.
  `scan` and `assess` without `--target` send zero network traffic.
- **Database**: no connection is ever attempted without an explicit
  `--database-profile`, and that profile must set `readonly: true`
  verbatim — omitting it (or setting it to `false`) refuses the
  connection. There is no arbitrary-SQL-execution API anywhere in the
  codebase; every database operation is one of a fixed set of read-only
  metadata queries.
- **Secrets**: credentials are read only from named environment variables
  you specify — never from your repository, never written into a report,
  log, or exception. Passwords, tokens, API keys, cookies, Authorization
  headers, and connection-string credentials are all redacted.
- **CI**: `--ci` and CI-environment detection never authorize network
  traffic or relax any safety gate by themselves — `--yes` is always
  required separately for real traffic. A saved baseline is immutable;
  nothing but `baseline save` (to its own explicit `--output` path) ever
  writes one. CI retry is bounded and narrow — it never retries a genuine
  assertion/threshold failure, only a total transport wipeout.
- **Performance**: every numeric knob (concurrency, requests, duration,
  levels) has a hard ceiling independent of what you configure.

## Supported Technologies

- **Discovery**: 12+ languages, common frameworks (FastAPI, Django,
  Flask, Express, ASP.NET Core, Spring Boot, Laravel, React, Angular,
  Vue, and more), Docker/Compose/Kubernetes/GitHub Actions/GitLab CI/
  Jenkins/Azure Pipelines evidence, 6 databases, OpenAPI/Swagger/GraphQL/
  REST-routing evidence, common test frameworks.
- **Frontend / web application analysis**: React, Next.js, Vue, Nuxt,
  Angular, Svelte, SvelteKit, Solid, Astro; Vite/Webpack/Rollup/Turbopack/
  Angular CLI build tools; Jest/Vitest/Mocha/Karma/Jasmine/Testing Library
  unit-test frameworks and Playwright/Cypress/WebdriverIO/Puppeteer
  browser-automation frameworks; bounded route/component/form/API-client
  evidence. **Plain static HTML/CSS/JavaScript websites are supported too**
  — no `package.json` or build tooling required — with HTML/CSS/JS counts,
  entry-point detection, navigation/form/API-client/responsive/
  authentication-UI structural evidence, and known CSS framework
  detection (Bootstrap/Tailwind/Bulma/Foundation) — plus inline vs.
  external CSS/JS counts, interactive UI evidence, browser API detection
  (microphone, speech synthesis, storage, WebSocket, and more), likely
  application pattern (static multi-page / single-page app / static
  document), external resource evidence, and CSP evidence, so a
  single-file rich web app is never misreported as having no CSS/JS.
  Static discovery + testability assessment
  (see [`docs/FRONTEND_ANALYSIS.md`](docs/FRONTEND_ANALYSIS.md)) is always
  on; actual browser/UI *execution* is a separate, explicit opt-in (see
  next item and [`docs/BROWSER_TESTING.md`](docs/BROWSER_TESTING.md)).
- **Browser / UI functional testing**: Chromium/Firefox/WebKit via
  Playwright (optional `[browser]` extra). Explicit target only, bounded
  navigate/click/fill/select/check/uncheck/press/wait_for actions, role/
  label/text/placeholder/test_id/css selectors, visibility/text/URL/
  title/element-count/attribute/input-value/checked/enabled/disabled
  assertions. Disabled by default everywhere.
- **Functional/performance testing**: OpenAPI 3.x REST APIs.
- **Database assessment**: SQL Server, PostgreSQL, MySQL, SQLite.
- **CI**: any provider that can run a shell command and check an exit
  code — GitHub Actions, GitLab CI, and Jenkins have ready-made templates.

## Limitations

This is an **initial, automated assessment** — not a security audit, not
a correctness proof, not a substitute for QA or code review:

- It does not prove the software is secure.
- It does not prove the absence of bugs.
- It does not prove business-logic correctness.
- It does not prove production readiness.
- It does not prove complete test coverage.
- It is not a security scanner or vulnerability detector.
- It is not a general-purpose browser/UI automation framework — browser
  testing supports one conservative smoke test plus a small, explicit
  action/assertion vocabulary, not arbitrary workflow automation, visual
  regression, or accessibility auditing.
- It is not an AI-driven or autonomous testing agent — every result is
  fully deterministic; there is no AI/LLM anywhere in this tool.
- It is not a fuzzing framework — functional tests are conservative,
  generated only from documented examples/defaults/schemas.
- Swagger 2.0 documents are rejected (OpenAPI 3.x only).
- Only SQLite has live-database integration tests in the automated test
  suite; SQL Server/PostgreSQL/MySQL support is verified against the same
  driver contract and via missing-driver-handling tests, not a live
  server, so the general test suite has no Docker dependency.

## Development

Contributing to Universal Test itself (not just using it):

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate.bat on cmd.exe
python -m pip install -e ".[dev]"
python -m pytest -q
```

| Doc | Purpose |
|---|---|
| `skill.md` | Development constitution — the source of truth for every rule in this project. |
| `SPECIFICATION.md` | Functional requirements derived from `skill.md`. |
| `ARCHITECTURE.md` | Module boundaries, technology choices, Core interfaces. |
| `ROADMAP.md` | Phase-by-phase plan and current status. |
| `PROGRESS.md` | Log of what's been completed, phase by phase. |
| `CHANGELOG.md` | User-visible changes. |
| `docs/V1_FREEZE.md` | The frozen V1.0 capability/contract surface. |
| `docs/V1_HARDENING_AUDIT.md` | The pre-freeze architecture/safety audit. |
| `docs/V1_RELEASE.md` | The V1.0 release manifest. |
| `docs/POST_V1_BACKLOG.md` | Candidate post-V1 directions (not committed to). |
| `docs/WEB_CAPABILITY_FREEZE.md` | The frozen Web capability (Phases 9-11) contract surface — Included/Explicitly-Not-Included. |

### Architecture at a glance

```text
Universal Core (technology-independent)
   models | engine | assertions | orchestration | configuration
        |
        v
Adapters (technology-specific)              Testing (technology-independent)
   rest | database                             performance | reliability (later)
   graphql | browser | docker |
   dotnet | node | python (not implemented)
        |                                             |
        +---------------------+------------------------+
                               v
     Discovery -> Testing -> Assessment -> Reporting -> Regression -> Quality Gate
                                                                          |
                                                                          v
                                                               CI Adapter / Template
                                                          (GitHub Actions / GitLab / Jenkins)
```

Core never imports adapter-specific code; adapters implement a shared
`detect/describe/discover/generate_tests/execute/collect_metrics`
contract. `assessment/`/`reporting/` only aggregate what Discovery/Testing
already produced — they never re-discover or re-execute anything.
`regression/` only compares two already-built snapshots. `quality_gate/`
only evaluates an already-built assessment + regression against a
configurable policy — no GitHub/GitLab/Jenkins/Azure logic exists in Core
or in this package; every provider-specific piece lives in a replaceable
`examples/ci/*` template. Full detail in `ARCHITECTURE.md`.
