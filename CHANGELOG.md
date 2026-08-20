# CHANGELOG.md

All notable user-visible changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- C/C++ discovery support: language detection (`.c`/`.h` → C, `.cpp`/`.cc`/
  `.cxx`/`.hpp`/... → C++, with shared `.h` headers disambiguated as C++
  when C++-only extensions are also present), `c`/`cpp` project types,
  CMake/Meson/Bazel/Make/Conan/vcpkg build-system detection, and CTest/
  GoogleTest/Catch2/Unity test-framework detection (read from CMakeLists.txt
  / conanfile content). Extension to the existing Phase 2 Discovery engine —
  same evidence-first, manifest-anchored method as every other language.

Phase 12 — Final Web QA / Freeze. Not a feature-development phase — a
validation-and-freeze pass over Phases 9-11's Web capabilities. **Web
capability is frozen after this phase**; see
`docs/WEB_CAPABILITY_FREEZE.md`.

### Fixed

- The packaged Windows one-click `.exe` never configured logging: it
  calls `gui/launcher.py::launch()` directly, bypassing the CLI's
  `configure_logging()` call, so its logger had no secret-redacting
  formatter attached. A server-side unhandled exception could have
  logged an unredacted secret (the response the browser received was
  never affected). `launch()` now configures logging defensively.

### Added

- `docs/WEB_CAPABILITY_FREEZE.md`: the definitive Included/Explicitly-
  Not-Included statement for everything built in Phases 9-11.

Phase 11 — Web Test Scenario / Workflow Testing. Not a new test engine —
an explicit, repeatable multi-step Web workflow layer on top of the
existing Browser Adapter.

### Added

- **Scenario file** (`universal-test-web.yaml`): define a named, ordered
  sequence of browser actions (`navigate`/`click`/`fill`/`select`/`check`/
  `uncheck`/`press`/`wait_for`) and assertions (`assert_visible`,
  `assert_text`, `assert_url`, `assert_count`, etc.) once, run it
  repeatedly. Secrets via `value_env: TEST_PASSWORD`, never a literal
  password in the file.
- **`universal-test browser scenario list/validate/run`**: list without
  executing, validate offline without launching a browser, run one or all
  scenarios with `--dry-run`/`--yes` support.
- **`assess --scenario <id>`** (repeatable): folds scenario results into
  the unified assessment/report/regression/quality-gate pipeline as a new
  "Web Scenarios" category.
- **GUI "Web Scenarios" card**: list scenarios for the selected project,
  view its steps, preview the plan, and run it after explicit
  confirmation.
- Sequential execution stops at the first step that doesn't pass;
  subsequent steps are recorded `SKIPPED`, never executed.
- Scenario-level timeout (`Run > Scenario > Step`, each child capped to
  the remaining parent budget) reusing the existing Phase 9 Hardening
  per-TestCase timeout mechanism.

### Fixed

- Relative navigation URLs (e.g. `/login`) were never resolved against
  the authorized target origin before being passed to the browser,
  making them unusable — an existing gap only now exercised by scenario
  portability.
- `browser scenario run --yes` did not actually gate execution; real
  browser execution could have started without the required explicit
  confirmation.
- All four of the CLI's confirmation prompts (performance/browser test/
  web assess/scenario run) could raise a raw `EOFError` traceback instead
  of a clean refusal on certain Windows stdin-redirection setups.
- `run_scenario()` did not catch a rejected/invalid target, causing a
  crash instead of a graceful `NOT_ASSESSED` result.

Phase 10 — One-Click Web Assessment / Non-Programmer UX. Not a new testing
engine — a guided orchestration/UX layer over the existing `assess`
pipeline.

### Added

- **`universal-test web assess <path>`**: one guided command combining
  project discovery, static frontend analysis, browser smoke test, and
  report generation — no need to know `scan`/`assess`/`browser test` as
  separate concepts. `--dry-run` shows the full plan (detected type,
  planned checks, not-included list, generated browser test steps)
  without launching a browser.
- **GUI "Web Assessment" card**: pick a project, click "Analyze Project &
  Build Plan" to see what was detected and exactly what will/won't be
  tested, confirm, then run — alongside (not replacing) the existing
  "Full Assessment" form.
- **New `POST /api/web/detect`** GUI endpoint: read-only project/frontend
  detection for the pre-flight plan (wraps the existing discovery engine).
- Result summary now shows a fourth distinct line — Browser Testing —
  alongside the existing Application Health/Testability/Assessment
  Coverage lines. Still no numeric quality score.

### Fixed

- `adapters/browser/local_server.py` occasionally bound a port Chromium
  itself refuses to navigate to (`net::ERR_UNSAFE_PORT`), causing rare,
  confusing flaky test failures. Now retries until a non-restricted port
  is bound.
- Picking a different project folder in the GUI after already analyzing
  one previously left a stale Web Assessment plan visible for the old
  project.

Phase 9 Hardening — Real-Project Validation. Hardening/validation pass
only, no new capabilities.

### Added

- **TestCase wall-clock timeout**: browser TestCase execution now has a
  true hard ceiling (`browser.test_timeout_seconds`), never the sum of
  each step's own timeout — verified with a real fixture
  (`test_timeout_seconds=2s` + a step whose own timeout is `10s` still
  completes in ~2.4s).
- Cancellation regression tests (`KeyboardInterrupt` during a browser
  session) confirming existing cleanup behavior.

### Fixed

- `BrowserConfig.test_timeout_seconds` was defined but never actually
  wired to the browser executor — now threaded through end-to-end
  (CLI/GUI/`assess --browser`).
- `BrowserConfig`'s timeout fields now explicitly reject `NaN`/`+-infinity`
  (`math.isfinite()`), rather than "happening to" clamp correctly only via
  an undocumented Python NaN-comparison quirk.
- The "Application Health" summary text (report/GUI) said it reflects only
  "Functional/Performance" — Browser Testing joined that same
  execution-driven category set in the original Phase 9 pass but the
  human-facing text was never updated to say so.

Browser / Web UI Functional Testing Adapter (Phase 9) — real, bounded,
explicitly-authorized browser execution on top of Phase 8.5's frontend
discovery. See `docs/BROWSER_TESTING.md` and `docs/BROWSER_SAFETY.md`.

### Added

- **`adapters/browser/`**: Playwright-based browser adapter (optional
  `pip install universal-test[browser]` extra; base install works with
  zero of it present). Reuses the existing `TestEngine`/`AssertionEngine`/
  `Orchestrator` — no second test engine or assertion framework.
- **`universal-test browser install`**: explicit, user-initiated browser
  binary download — never automatic.
- **`universal-test browser test <project> --target <url>`**: dry-run
  plan preview, or real execution with a safety confirmation
  (`--yes` for non-interactive use).
- **`assess --browser --target ... --yes`**: opt-in browser testing folded
  into the unified assessment/report/regression/quality-gate pipeline.
  Disabled by default — a detected frontend never triggers it.
- **Target safety policy**: localhost/127.0.0.1/::1/file:// allowed by
  default; any other target requires explicit `--allow-external`. No port
  scanning, no guessing, no following URLs found in scanned content.
- **Conservative default smoke test**: navigate, assert page loaded, assert
  title exists, capture console/page-error evidence — never clicks,
  submits, uploads, or requests a permission automatically.
- **Explicit test definitions**: `navigate`/`click`/`fill`/`select`/
  `check`/`uncheck`/`press`/`wait_for` actions; `role`/`label`/`text`/
  `placeholder`/`test_id`/`css` selectors; `visible`/`hidden`/
  `text_contains`/`text_equals`/`url_equals`/`url_contains`/`page_title`/
  `element_count`/`attribute_equals`/`input_value`/`checked`/`enabled`/
  `disabled`/`console_summary` assertions.
- **Assessment**: new "Browser Testing" category (`NOT_ASSESSED` by
  default; `PASS`/`WARNING`/`FAIL` once executed, execution-driven like
  Functional Health/Performance).
- **Reporting**: "Browser Testing" section in `report.json`/`.md`/`.html`.
- **Regression**: `regression/browser_compare.py`, per-test-ID PASS/FAIL/
  ERROR comparison (no numeric score), folded into `baseline save`/
  `baseline compare`.
- **GUI**: "Browser / UI Testing" checkbox with an explicit confirmation
  gate, rendered through the existing generic category grid.
- **Safety**: fresh browser context per run, no credential guessing, no
  auto-granted permissions, no arbitrary JavaScript execution, hard-capped
  timeouts independent of configuration, secrets redacted via the existing
  `core/redaction.py`, browser storage never read into evidence,
  guaranteed process cleanup on exception/timeout/Ctrl+C.

### Fixed

- `core/redaction.py`'s key=value pattern now correctly redacts the full
  value of `Authorization: Bearer <token>`/`Basic <credentials>` headers
  (previously only the scheme word itself was redacted, leaking the token).

Frontend / Web Application Analysis Adapter (Phase 8.5) — discovery +
testability assessment for frontend projects. Explicitly **not** browser/UI
execution; see `docs/FRONTEND_ANALYSIS.md`.

### Added

- **Frontend framework/build-tool/test-framework detection**: React,
  Next.js, Vue, Nuxt, Angular, Svelte, SvelteKit, Solid, Astro (dependency
  or config-file evidence); Vite, Webpack, Rollup, Turbopack, Angular CLI
  build tools; Jest, Vitest, Mocha, Karma, Jasmine, Testing Library
  (unit-level) and Playwright, Cypress, WebdriverIO, Puppeteer (browser
  automation) test frameworks — reported as distinct facts, never
  conflated with each other.
- **`ProjectModel.frontend` (`FrontendInfo`)**: bounded route/component/
  form/API-client evidence (`FrontendSignal`, always labeled with its scan
  bound), build/test npm scripts, frontend test directories, `.env.example`/
  `.env.template` public key names (values never captured).
- **`adapters/frontend/`**: discovery + testability assessment adapter,
  following the existing REST/database adapter contract shape. Browser/UI
  test generation and execution are explicit, honest stubs (`execute()`
  raises `NotImplementedError`), not silent no-ops — reserved for a future
  Browser Adapter.
- **New "Frontend / Web Application Health" assessment category**, capped
  below `FAIL` (missing test tooling is a testability gap, not a defect) —
  same rule already used for database connectivity issues. `assess`'s
  coverage/unassessed tracking gains a "Frontend Discovery" (always 100%)
  and, whenever a frontend is detected, a "Browser/UI Execution" item
  pinned at 0% and explicitly `NOT_ASSESSED`.
- `universal-test scan`/`assess` (text/Markdown/JSON/HTML) and the GUI all
  show a "Frontend / Web Application" section with an explicit
  "Browser/UI Execution: NOT_ASSESSED" line, so "frontend detected" is
  never read as "frontend tested."
- New fixtures under `tests/fixtures/` (React+Vite+Vitest, Vue, Angular,
  Next.js, SvelteKit, no-test-framework, malformed `package.json`, empty
  frontend dir, malicious `package.json` scripts, backend-mentions-react
  false-positive case) and corresponding discovery/adapter/assessment/
  reporting tests, including a dedicated safety test asserting discovery
  never spawns a subprocess or opens a socket.
- New `docs/FRONTEND_ANALYSIS.md`.

### Security

- Frontend discovery is strictly read-only and offline: `package.json`
  `scripts` are copied as inert display strings, never executed; no
  package manager, browser, or network activity occurs during discovery.

### Added (Static Web Analysis enhancement, same phase)

- **Plain static HTML/CSS/JavaScript websites are now a first-class
  frontend type** (`FrontendType.STATIC_WEB`) — no `package.json`,
  lockfile, or config file required. A single root `index.html` is
  sufficient on its own; multi-page sites, monorepo-style multiple app
  roots (`frontend/index.html` + `admin/index.html`), and framework
  precedence (a React project's own `index.html` never reclassifies it as
  Static Web) are all handled explicitly.
- Detected static sites report **HTML/CSS/JS file counts, entry point(s),
  navigation-link, form, API-client (including WebSocket), responsive-design,
  and authentication-UI structural evidence**, plus known CSS framework
  detection (Bootstrap, Tailwind CSS, Bulma, Foundation — matched by
  filename/link, never by an arbitrary class name).
- **Conservative false-positive guards**: generated documentation
  (`docs/`), code-coverage reports (`coverage/`/`htmlcov/`, now excluded
  from discovery entirely alongside `node_modules`/`dist`/`build`), and
  server-rendered backend templates (`templates/`) are not misclassified
  as a standalone static frontend when there's no supporting CSS/JS.
- New fixtures (`frontend-static-basic`, `frontend-static-form`,
  `frontend-static-api`, `frontend-single-html`, `frontend-docs-only`,
  `frontend-coverage-only`, `backend-html-template`,
  `frontend-static-malicious-inline-script`) and corresponding
  discovery/assessment/reporting tests, including a security test proving
  an inline `<script>` with dangerous-looking content is only ever
  matched as evidence text, never executed.

### Added (Static Web Capability Detection & Assessment Semantics Hardening, same phase)

- **A single rich HTML file is no longer misreported as "CSS: 0,
  JavaScript: 0"** — `inline_css_count`/`inline_js_count` now report
  inline `<style>`/`<script>` blocks additively alongside the existing
  external-file counts.
- **New capability detection**: interactive UI evidence (buttons, inputs,
  event handlers); browser API evidence (microphone/MediaRecorder, speech
  synthesis, storage, WebSocket, notifications, geolocation, clipboard,
  file reading, IndexedDB — kept structurally separate from backend
  API-client evidence); likely application pattern (static multi-page /
  single-page application / static document, evidence-based, never
  overclaimed); external resource evidence (e.g. "Google Fonts",
  never fetched); Content-Security-Policy evidence.
- **Authentication-UI detection hardened**: a real password field is
  strong evidence; generic storage/header markers now only count as weak
  evidence and only when co-occurring with an actual `<form>` — a
  README/comment mention of "login"/"password"/"authentication" was
  never sufficient and still isn't.
- **`AssessmentFinding.classification`** (new field: `defect` /
  `testability_gap` / `not_assessed` / `informational` /
  `execution_failure`) — every existing finding across all assessment
  modules now states explicitly whether it represents a confirmed
  problem or a testability/coverage limitation.
- **`ProjectAssessment.application_health`** (new field, independent of
  the unchanged `overall_status`) — "no confirmed defects" unless a
  category driven by something that actually executed (Functional
  Health/Performance) shows a real problem. A project with only
  testability-gap `WARNING`s (e.g. no test framework) now correctly shows
  `application_health: PASS`.
- **`ProjectAssessment.assessment_completeness`** (new field: "full"/
  "partial") — derived from existing coverage/unassessed data.
- **`Build / Project Health` no longer WARNs for a genuine static
  website** with no package manager/build system — it reads `PASS` with
  an explicit "not required for a static site" reason.
- **`Project Discovery` no longer reads `UNKNOWN`/"0 languages" for a
  valid static HTML/CSS/JS site** — static sites now get proper project-
  type evidence even without a `package.json`.
- CLI, GUI, and Markdown/HTML reports gained an "Assessment Summary"
  (Application Health / Testability / Assessment Coverage, each with a
  plain-language explanation), a classification label on every finding,
  and an explicit clarifying sentence next to Quality Gate `PASS`/`FAIL`.
- **No changes** to `overall_status`, `compute_overall_status`, Quality
  Gate policy evaluation, regression/baseline comparison, or CLI exit
  codes — all additive, no false `PASS`, no numeric quality score.
- New `frontend-static-rich-spa` fixture (modeled on a real single-file
  microphone/speech-synthesis web app) plus corresponding discovery/
  assessment/reporting tests.

## [1.1.1] — 2026-08-10

Final QA / stabilization pass on the V1.1 GUI, based on an external audit.
No new features; all changes fix confirmed defects in the existing GUI.

### Fixed

- **GUI result dashboard now shows Regression and Quality Gate.** Both were
  already computed by the backend and present in the API response, but the
  dashboard never rendered them. `gui/server.py::_outcome_to_dict()` also
  now returns the Quality Gate's full shape (`reason`, `findings`,
  `summary`), not just `status`/`exit_code`.
- **Progress checklist shows a Regression step only when a baseline was
  actually provided**, matching `application/service.py`'s own
  `if request.baseline_path:` gate — it no longer omits the step
  unconditionally nor shows it when regression can't possibly run.
- **GUI errors never leak a raw traceback, secret, or connection string
  to the browser.** Every internal-error HTTP response and failed-run
  result now returns only a human-readable message plus an opaque
  `error_id`; the full detail is logged server-side through the existing
  redacting logger.
- **API authentication (Bearer/API key/Basic) is now configurable from
  the GUI**, under Advanced Settings — by environment variable name only,
  never a plaintext secret field. The backend already supported this; the
  GUI had no control for it.
- **Performance testing now offers an endpoint-selection UI** when a
  project's OpenAPI spec has more than one candidate operation, via a new
  `POST /api/perf/endpoints` backend route (parsing stays server-side).
  Previously, enabling performance testing on a multi-endpoint project was
  a dead end in the GUI.
- **`RunRegistry` is now bounded** — only the most recent N completed runs
  are retained (default 20); a long-lived GUI process no longer
  accumulates unbounded memory. Active runs are never evicted.
- **Starting a second assessment while one is already running is now
  rejected** (HTTP 409, plus the Start button disabling itself in the UI)
  instead of silently starting a second concurrent run.
- **`core/logging_setup.py`'s `propagate = False` is now set at import
  time**, not lazily inside `configure_logging()`. Previously, whichever
  pytest test happened to be the *first* in the process to trigger
  `configure_logging()` could get an empty `caplog.records` even though
  the message was genuinely logged — pytest's caplog only auto-attaches to
  a non-propagating logger that already exists when it enters, once per
  test.
- **Traditional Chinese category labels** (專案分析、建置與專案健康度、可測
  試性、功能健康度、效能、設定檔健全度、測試基礎設施、資料庫健康度) added to
  the GUI's i18n table — previously the eight assessment categories always
  rendered in English regardless of the selected language.
- **Windows one-click `.exe` now builds windowed (`console=False`)**
  instead of showing a console window on every launch. The browser
  auto-open fallback no longer depends on a console: it shows a native Tk
  message box with the local URL, and guards against `sys.stdout` being
  `None` (as it is in a windowed PyInstaller build) so the fallback path
  itself can't crash the launch.
- `README.zh-TW.md` gained the GUI / one-click-app / performance-endpoint-
  selection / authentication sections that only existed in the English
  README.

## [1.1.0] — 2026-08-09

Post-V1 Phase 1: a local, browser-based GUI for non-technical users, on
top of the unchanged V1.0 CLI and Core. See `docs/GUI_ARCHITECTURE.md`,
`docs/GUI_USER_GUIDE.md`, and `docs/GUI_SAFETY.md`.

### Added

- **GUI** (`universal-test gui`): a `127.0.0.1`-only local web server
  (stdlib `http.server`, no new runtime dependency) serving a plain
  HTML/CSS/JS single-page app (Traditional Chinese / English) — project
  folder picker (native dialog), optional test target, simple
  check-selection (Project Analysis + Functional on by default;
  Performance/Database opt-in), human-readable progress, a status-badge
  result dashboard (no numeric score), findings with a technical-details
  toggle, and report open/export actions.
- **Application Service Layer** (`universal_test.application`): a thin
  facade (`AssessmentRequest`/`run_assessment()`/`ProgressEvent`) the GUI
  calls instead of reimplementing pipeline logic — it delegates to the
  same `discover()`/`rest_run()`/`PerformanceRunner`/`db_discover()`/
  `build_assessment()`/`regression_compare()`/`qg_evaluate()`/report
  renderers the CLI's `_run_pipeline`/`_run_assess` already use.
- **Windows one-click packaging** (`release/windows/`): a PyInstaller
  spec + build script producing a portable `UniversalTest.exe` that
  bundles its own Python runtime; no Python/pip/Node.js install required
  to run it.
- GUI safety behavior matching V1's model: loopback-only binding (enforced
  in code), no target -> no network traffic, performance testing gated
  behind an explicit two-step confirmation (checkbox + separate
  authorization checkbox, mirroring the CLI's `--yes` prompt), database
  assessment opt-in and read-only, no secrets ever rendered in the UI.
- 22 new tests (`tests/application/`, `tests/gui/`,
  `tests/cli/test_cli_gui_command.py`) covering safe defaults, the
  no-target/no-network guarantee, the performance confirmation gate,
  database opt-in, progress-event ordering, and the packaged launcher's
  loopback binding.

### Unchanged

- The V1.0 CLI (`scan`/`test`/`performance`/`database`/`assess`/
  `baseline`) is untouched — the GUI is an additional interface, not a
  replacement. All 563 V1.0 tests still pass unmodified.

## [1.0.0] — 2026-08-09

First stable release. Summary of V1.0 capabilities — see `docs/V1_FREEZE.md`
for the definitive, frozen contract (CLI, exit codes, configuration, report
schema, safety guarantees) and the "Full development history" section below
for the phase-by-phase detail this summary is drawn from.

### Added

- **Discovery** (`scan`): read-only detection of language, project type,
  framework, build system, infrastructure/CI evidence, database evidence,
  API evidence, test framework, and secret patterns (never values).
- **REST/OpenAPI functional testing** (`test`): OpenAPI 3.x parsing,
  conservative test generation, HTTP execution, env-var-only auth, full
  JSON Schema validation.
- **Performance testing** (`performance`): bounded-concurrency load
  generation, documented percentiles, independent threshold evaluation,
  hard safety ceilings.
- **Read-only database assessment** (`database`): SQL Server, PostgreSQL,
  MySQL, SQLite — schema/table/view/column/key/index metadata only, no
  arbitrary SQL execution capability anywhere in the codebase.
- **Unified assessment** (`assess`): aggregates the above into one
  evidence-based report with an overall `PASS/WARNING/FAIL/UNKNOWN` status.
- **Baseline / regression** (`baseline save`/`compare`, `assess
  --baseline`): immutable baseline snapshots, per-test-ID functional
  regression, tolerance-based performance regression, informational
  database/discovery schema-change detection.
- **CI Quality Gate** (`assess --ci --yes`): deterministic, configurable
  pass/warn/fail policy; stable `0/1/2/3` exit-code contract; GitHub
  Actions/GitLab CI/Jenkins starting-point templates.
- **Reporting**: `report.json`/`report.md`/`report.html` — offline-safe,
  schema-versioned, deterministic, secret-redacted.
- **Safety controls throughout**: no network traffic without an explicit
  `--target`; no database connection without an explicit
  `--database-profile` (`readonly: true` mandatory); no credential ever
  read from a scanned repository or written into a report/log; CI
  detection never bypasses `--yes`; every performance knob has a hard
  ceiling.

### Fixed (pre-1.0.0 hardening)

- Secret redaction now covers `Cookie`/`Set-Cookie` header values (found
  during the pre-release hardening audit — see `docs/V1_HARDENING_AUDIT.md`).
- Windows-console-safe output throughout (no `section sign`/em dash in any
  string that can reach printed CLI output).

### Known limitations

See `docs/V1_FREEZE.md`'s "Known limitations" and "V1 non-goals" sections.

---

## Full development history (Phase 0-8, pre-1.0.0)

The detailed, phase-by-phase log every 1.0.0 capability above was built
from. Kept for historical/audit purposes — new changes going forward
should get their own dated release section above, not be appended here.

### Added — Phase 0 (Repository initialization)

- `SPECIFICATION.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `PROGRESS.md`,
  `CHANGELOG.md`, `README.md` planning documents.

### Added — Phase 1 (Core)

- Python package skeleton at `src/universal_test/` with `core`, `discovery`,
  `adapters`, `testing`, `assessment`, `reporting`, `cli` module boundaries.
- Core domain models: `ResultStatus`, `AssessmentStatus`,
  `DetectionConfidence`, `Severity` enums; `Evidence`, `TestCase`,
  `AssertionSpec`, `AssertionResult`, `TestResult`, `Finding` dataclasses.
- Assertion engine with builtin assertions (`status_code`, `status_code_in`,
  `response_time_less_than`, `json_path_exists`, `json_path_equals`,
  `json_schema_valid` [minimal], `header_exists`, `header_equals`,
  `body_contains`, `body_not_contains`, `row_count`, `value_equals`,
  `value_not_null`).
- `TestEngine` (single test execution against an adapter-supplied executor)
  and `Orchestrator` (batch run + summary).
- `Config` dataclass tree + `load_config()` reading `universal-test.yaml`
  with safe, near-zero-config defaults.
- Secret redaction (`core/redaction.py`) and structured logging setup
  (`core/logging_setup.py`).
- Exception hierarchy (`core/errors.py`).
- CLI skeleton (`universal_test.cli.main`) routing `scan/assess/test
  /performance/report/run` subcommands with the documented flags; each
  currently reports which future phase implements it.
- Unit tests for all of the above under `tests/`.

### Known limitations

- No discovery, no adapters, no report generation yet — CLI subcommands are
  routing stubs only.
- `json_schema_valid` assertion is a minimal type/required-field checker, not
  full JSON Schema draft validation.

### Added — Phase 2 (Discovery)

- `universal-test scan <path>` is now fully implemented: read-only project
  discovery producing a normalized `ProjectModel` with confidence + evidence
  on every finding, output as `--format text|json|markdown` to stdout or
  `--output <path>`.
- New `discovery/` package: `filesystem` (vendor-dir-excluding walker),
  `manifests` (bounded manifest reader for `package.json`, `pyproject.toml`,
  `*.csproj`/`*.sln`, `pom.xml`/`build.gradle`, `go.mod`, `Cargo.toml`,
  `composer.json`), `repository` (read-only git inspection), `language`,
  `project_type`, `framework`, `infrastructure`, `database`, `api`,
  `test_framework`, `secrets`, `models` (normalized data model), `engine`
  (orchestrates all of the above), `serializers` (text/JSON/Markdown).
- Detects: 12 languages, 9 project types, 14 frameworks, 7 infrastructure/CI
  systems, 6 databases, OpenAPI/Swagger/GraphQL/REST-routing evidence, 11
  test frameworks/tools, and potential-secret patterns (value never
  captured — file/line/pattern-type only).
- 6 fixture projects (`tests/fixtures/{python-fastapi,dotnet-api,node-react,
  docker-project,database-project,mixed-project}`) plus edge-case coverage
  (empty repo, unknown/generic project, malformed manifests, excluded
  directories, nonexistent path, live throwaway git repo).

### Known limitations (Phase 2)

- No OpenAPI endpoint parsing yet (file/content evidence only) — Phase 3.
- No `jsonschema`/full-YAML-parsing dependency added; Kubernetes and secret
  detection use bounded heuristic content scans, not exhaustive parsing.
- Framework/database detection relies on manifest/dependency evidence only —
  no source-code import scanning (deliberate, to avoid weak-evidence claims).

### Added — Phase 3 (REST/OpenAPI Functional Testing)

- `universal-test test <path> --target <url>` is now fully implemented:
  parses an OpenAPI 3.x document, generates conservative functional tests,
  executes them over HTTP, and reports PASS/FAIL/SKIPPED/UNKNOWN/ERROR with
  evidence, as `--format text|json|markdown` to stdout or `--output <path>`.
  `--dry-run` lists discovered endpoints and generated tests without sending
  any HTTP requests; omitting `--target` (without `--dry-run`) still runs
  discovery/generation and then reports the required "no execution target
  specified" error rather than guessing a target.
- New dependencies: `httpx` (HTTP client) and `jsonschema` (full JSON Schema
  validation, replacing Phase 1's minimal `json_schema_valid` checker — see
  ARCHITECTURE.md §2 for why no dedicated OpenAPI-parsing library was added).
- New `adapters/rest/` package: `openapi_loader` (internal `$ref` resolution,
  no external-ref network fetches), `normalizer` (OpenAPI 3.x → normalized
  `ApiSpecification`/`ApiEndpoint`/`SchemaModel`/`SecurityScheme`),
  `discovery_bridge` (spec-file discovery, deterministic multi-spec
  handling — never silently picks one), `request_data` (deterministic
  example/default/enum/minimum-based value generation, `UNKNOWN` rather than
  guessed when underspecified), `test_generation` (conservative positive +
  up to 3 negative tests per endpoint, reusing the unmodified Phase 1
  `AssertionEngine` — no new assertion types), `auth` (env-var-only
  credential resolution for bearer/API-key/basic schemes; never reads a
  credential from the repository or attempts a login), `executor`
  (`httpx`-based, error categorization into `NetworkError`/
  `RequestTimeoutError`/`TargetError`, response redaction), `adapter`
  (orchestration + the generic adapter contract), `serializers`
  (text/JSON/Markdown for dry-run and executed runs).
- `core/errors.py`: added `OpenApiError`, `TargetError`, `NetworkError`,
  `RequestTimeoutError` (all additive; no existing exception changed).
- `core/assertions/builtin.py`: `json_schema_valid` now uses the
  `jsonschema` library for full JSON Schema validation (falls back to the
  Phase 1 minimal checker if `jsonschema` is ever unavailable); a malformed
  schema is reported distinctly, never silently passed.
- CLI: new `test`-only flags `--openapi`, `--timeout`,
  `--bearer-token-env`, `--api-key-env`, `--api-key-header`,
  `--basic-auth-user-env`, `--basic-auth-pass-env`.
- 5 new OpenAPI fixture projects (`tests/fixtures/openapi-{basic,auth,
  invalid,multiple,schema}`) plus a fully offline, stdlib-only local HTTP
  server fixture (`tests/adapters/rest/fixture_server.py`) exercising real
  GET/POST success, validation failures, schema-validation pass/fail,
  connection refusal, timeout, and bearer-token auth pass/fail/skip — no
  external network access anywhere in the test suite.

### Known limitations (Phase 3)

- Only OpenAPI 3.x is supported; Swagger 2.0 documents are rejected with a
  clear error, not partially parsed.
- External `$ref`s in an OpenAPI document are left unresolved with a warning
  (never fetched over the network) — deliberate, see ARCHITECTURE.md §2/§10.
- `security` requirement semantics are flattened to "any one named scheme"
  (OR-only); the rarer AND-within-one-requirement-object case isn't modeled.
- No unified `report.json/.md/.html` yet — `scan` and `test` each have their
  own lightweight serializers; the general Phase 5 report generator (with
  executive summary, cross-command findings, recommendations) is still
  pending.
- One global per-run HTTP timeout (no per-request override).

### Added — Phase 4 (Performance Testing)

- `universal-test performance <path> --target <url>` is now fully
  implemented: baseline/load/stress/custom load profiles, bounded
  concurrency execution, per-level metrics (RPS, error rate, P50/P90/P95
  /P99 latency, timeout/network/HTTP-error counts), independent threshold
  evaluation, `--dry-run`, and an interactive confirmation prompt (or
  `--yes` for CI) before sending any real traffic.
- New `--profile`, `--concurrency`, `--max-concurrency`, `--requests`,
  `--duration`, `--endpoint`, `--method`, `--stop-error-rate`,
  `--stop-p95-ms`, `--yes` flags; `--openapi` and the 5 auth flags
  (`--bearer-token-env` etc., now shared with `test` via `_add_auth_args`)
  are reused as-is.
- New `testing/performance/` package (technology-independent — no `httpx`
  import): `models.py` (`LoadProfile`, `PerformanceRequest`,
  `PerformanceSample`, `PerformanceMetrics`, `PerformanceThresholdResult`,
  `PerformanceResult`), `percentiles.py` (documented nearest-rank
  percentile algorithm), `metrics.py` (sample aggregation), `thresholds.py`
  (independent, testable threshold evaluation reusing
  `core.models.enums.AssessmentStatus`), `planner.py` (`LoadProfile`
  construction with hard safety ceilings — max concurrency 200, max 2000
  requests/level, max 300s/level, max 10 levels), `runner.py`
  (`ThreadPoolExecutor`-based bounded-concurrency execution with
  cooperative cancellation and stress-mode stopping conditions),
  `serializers.py` (plan/result text/JSON/Markdown).
- New `adapters/rest/performance_executor.py` (httpx-based
  `PerformanceExecutor`, error-classifying, never raises) and
  `adapters/rest/performance.py` (endpoint selection reusing Phase 3's
  OpenAPI discovery, and `build_positive_request`/
  `test_generation.build_positive_request` — now public — for deterministic
  request bodies, so performance testing never regenerates a different
  request per call).
- `universal-test.yaml`'s existing `performance.thresholds` section
  (defined since Phase 1, unused until now) is applied automatically.
- Extended the Phase 3 offline fixture server with `/fast`, `/error`, and
  `/unstable` (deterministic "every Nth request fails") routes for
  performance-specific integration tests — still no external network access
  anywhere in the suite.

### Fixed

- Interval timing across the performance engine now uses
  `time.perf_counter()` instead of `time.monotonic()` — this Windows Python
  build's `monotonic()` has ~15ms resolution, which was silently producing
  `duration_seconds=0.0` (and therefore `rps=0.0`) for fast concurrency
  levels. Found by manually running a two-level plan and noticing the
  second level's numbers were exactly zero; see ARCHITECTURE.md §8.4/§11.12.

### Known limitations (Phase 4)

- No regression/baseline-comparison engine — explicitly out of scope for
  this phase (per its own brief §20); threshold evaluation is per-run only.
- CLI `Ctrl+C` does not yet cancel a running performance test gracefully —
  the `PerformanceRunner` cancellation API exists and is tested, but isn't
  wired to `SIGINT` yet.
- One global per-request timeout per run (same limitation as Phase 3's
  functional testing).
- OpenAPI `security` OR-only flattening (inherited from Phase 3) applies
  here too.

### Added — Phase 5 (Unified Assessment & Reporting)

- `universal-test assess <path>` is now fully implemented: aggregates
  Phase 2 discovery, Phase 3 functional testing, and Phase 4 performance
  testing into one evidence-based `ProjectAssessment` and emits
  `report.json`/`report.md`/`report.html` (default `--format all`, written
  to `./reports/` when `--output` isn't given). Safe by default: `assess
  ./project` alone sends zero network traffic; `--target` enables
  functional execution; `--performance` (in addition to `--target`) opts
  into a small load test, reusing the exact same confirmation/`--yes`
  safety gate as the standalone `performance` command.
- New `assessment/` package: `models.py` (`ProjectAssessment`,
  `AssessmentCategory`, `AssessmentFinding`, `CoverageItem`,
  `UnassessedArea` — reusing the existing `AssessmentStatus`/`Severity`
  enums rather than inventing new ones), `rules.py` (deterministic,
  documented, unit-tested overall-status rule — `FAIL > WARNING > UNKNOWN
  > PASS`, no magic numbers — plus a shared `execution_health_status()`
  ladder used by both Functional Health and Performance),
  `discovery_assessment.py`/`functional_assessment.py`
  /`performance_assessment.py`/`testability_assessment.py`
  /`configuration_assessment.py` (the seven category assessors),
  `engine.py` (`build_assessment()` orchestration, coverage computation,
  unassessed-area tracking, fixed limitations text).
- New `reporting/` package: `report_bundle.py` (`AssessReportBundle` —
  assessment + the raw Phase 2-4 results it was built from),
  `json_report.py` (schema-versioned, deterministic), `markdown_report.py`
  (fixed 12-section structure), `html_report.py` (offline static page, no
  CDN/external JS, every scanned-project-derived string passed through
  `html.escape()` — no templating-engine dependency added).
- CLI: new `assess`-only `--performance` opt-in flag; `assess` reuses the
  entire `performance` flag set (`--profile/--concurrency/--requests`
  /etc.) and the shared auth flags.
- 5 new fixture projects (`tests/fixtures/{healthy-project,
  failed-functional-project,slow-project,unknown-project,partial-project}`)
  exercising PASS/WARNING/FAIL functional and performance outcomes against
  the existing offline fixture server.
- Fixed a latent test-collection bug (unrelated to Phase 5 code, surfaced
  by adding a second fixture with a `tests/test_main.py`): `pyproject.toml`
  now excludes `tests/fixtures/**` from pytest's own collection via
  `norecursedirs`, since those files are fixture *content* for discovery/
  assessment to scan, not part of this project's test suite.

### Known limitations (Phase 5)

- No regression/baseline-comparison engine, no historical trend, no CI
  quality gate — explicitly out of scope for this phase per its own brief.
- No numeric quality score — overall status is one of
  `PASS/WARNING/FAIL/UNKNOWN`, deliberately, per the brief §5.
- Coverage is five fixed, mostly-binary items, not a fine-grained
  per-detector percentage (avoids implying false precision).
- No AI-assisted findings or recommendations — fully deterministic.
- `report`/`run` remain routing stubs; `assess` already covers `report`'s
  intended functionality.

### Added — Phase 6 (Read-Only SQL Database Adapter)

- `universal-test database <path> --database-profile <path.yaml>` is now
  implemented: connects to an explicitly configured SQL Server, PostgreSQL,
  MySQL, or SQLite database and produces a read-only discovery report
  (server version, schemas, tables/views, columns, primary keys, foreign
  keys, indexes, safe row-count estimates) as `--format text|json|markdown`
  to stdout or `--output <path>`, plus `--dry-run` (prints the plan,
  connects to nothing). `assess` gains an opt-in `--database-profile` flag
  and an eighth report category, "Database Health" — omitted, zero database
  connections are attempted, matching `assess`'s existing safe-by-default
  behavior for functional/performance testing.
- **Discovering database evidence never implies connecting to it.** The
  database adapter connects only when the user supplies an explicit
  `--database-profile` YAML file; nothing is ever derived from what `scan`
  (Phase 2) found in the project's manifests/config files.
- **No arbitrary SQL execution capability exists anywhere in the adapter**
  — the entire driver contract (`DatabaseDriver` in
  `adapters/database/base.py`) is a fixed set of read-only metadata
  operations (list tables/views/columns/keys/indexes, safe row-count
  estimate); there is no `execute(sql)` method to guard, block, or bypass.
- **`database.readonly: true` is mandatory** in the profile — any other
  value (including an absent key) refuses the connection at load time
  rather than assuming safety. Credentials are read only from named
  environment variables (`credentials.username_env`/`password_env`), never
  written in the profile file itself, and never appear in any log, report,
  exception, or `AssessmentFinding`/`Evidence`.
- New `adapters/database/` package: `models.py` (normalized,
  engine-independent `DatabaseInfo`/`DatabaseSchema`/`DatabaseTable`
  /`DatabaseView`/`DatabaseColumn`/`PrimaryKey`/`ForeignKey`
  /`DatabaseIndex`/`RowCountEstimate`), `base.py` (`DatabaseDriver`
  contract + generic metadata-walking orchestration), `profile.py`
  (profile YAML parsing + the mandatory-readonly refusal), `sqlite.py`
  (stdlib `sqlite3`, opened via a read-only URI so the connection itself
  cannot write), `postgresql.py`/`mysql.py`/`sqlserver.py` (each engine's
  optional driver imported lazily, so a missing driver never breaks
  anything outside its own module), `adapter.py` (orchestration — every
  connection/timeout/driver/metadata failure becomes a
  `not_assessed_reason`, never an uncaught exception), `serializers.py`
  (dry-run plan + result text/JSON/Markdown).
- New dependency group: `pip install universal-test[database]`
  (`psycopg2-binary`, `mysql-connector-python`, `pyodbc` — SQL Server's
  driver also needs an OS-level ODBC driver installed). None is a hard
  dependency; Core/Discovery/REST/Performance/Assessment/Reporting all work
  correctly with zero of these installed. A missing driver resolves to
  `NOT_ASSESSED` with reason "Database driver is not installed," never a
  crash.
- New `assessment/database_assessment.py`: an eighth assessment category,
  "Database Health," structurally capped below `FAIL` — a connection
  failure/timeout/missing driver, a missing primary key, or zero detected
  foreign keys are all reported as `NOT_ASSESSED`/`INFO`/`WARNING`
  evidence, never a defect verdict (a schema observation is not the same
  thing as a confirmed problem).
- Safe row-count estimation prefers each engine's own catalog/metadata
  statistics (SQL Server `sys.dm_db_partition_stats`, PostgreSQL
  `pg_stat_user_tables`, MySQL `information_schema.tables.table_rows`,
  SQLite `sqlite_stat1`) over `SELECT COUNT(*)`, which can be expensive on
  a large, unfamiliar table; an unavailable estimate is reported as `None`,
  never fabricated.
- `reporting/{json,markdown,html}_report.py` gain a `database`
  section/key (`null`/"NOT_ASSESSED" when no profile was configured or the
  connection failed).
- 2 new SQLite fixture databases (`tests/fixtures/database/{sqlite-basic,
  sqlite-relations}/app.db`) — `sqlite-relations` specifically includes a
  foreign key, a unique index, a view, and a table with no primary key, to
  exercise the "informational, not a defect" assessment rules end-to-end
  against a real (if tiny) database.

### Known limitations (Phase 6)

- Only SQLite has live-database integration tests in the automated suite —
  SQL Server/PostgreSQL/MySQL are covered by missing-driver-handling tests
  and code review against the same driver contract, not a live server, per
  the brief's explicit instruction not to make the general test suite
  depend on Docker or an external database service.
- No schema diff, migration validation, or baseline comparison — out of
  scope for this phase, deferred alongside the regression engine already
  deferred from Phase 4.
- No arbitrary SQL execution capability exists at all, by design — a
  permanent property of this adapter, not a temporary gap.
- Driver dependencies are grouped into one `[database]` extra covering all
  three server engines together, rather than a separate extra per engine.

### Added — Phase 7 (Regression / Baseline Comparison Engine)

- `universal-test baseline save <path> --output baseline.json` is now
  implemented: captures a versioned snapshot (`schema_version`,
  `tool_version`, timestamp, project path, git commit/branch/dirty,
  discovery/functional/performance/database/assessment summaries) of the
  current discovery + (optional) functional/performance/database pipeline
  results — never just an overall status string. `universal-test baseline
  compare <path> --baseline baseline.json` compares a later run against a
  saved baseline and reports what changed. `universal-test assess <path>
  --baseline baseline.json` folds the same comparison into the unified
  report as a new "Regression" section.
- **Baseline is immutable; comparison is read-only.** `baseline save` only
  ever creates the file at the explicit `--output` path (never a hidden
  default); `baseline compare` and `assess --baseline` only ever read a
  baseline — no code path modifies one once written.
- **Functional regression compares by test ID**, not just aggregate
  pass/fail counts — `API-002: PASS -> FAIL` is reported specifically. A
  test present in only one of the two runs is `added`/`removed`, never
  itself treated as a regression.
- **Performance regression is direction-aware and tolerance-based**:
  latency/error-rate/timeouts are "lower is better", RPS/throughput is
  "higher is better"; a configurable tolerance
  (`regression.performance` in `universal-test.yaml` — `p50/p90/p95
  /p99_percent`, `rps_percent`, `error_rate_absolute`, with safe non-zero
  defaults) prevents ordinary measurement noise from being reported as a
  regression. Compared per matching concurrency level.
- **Database and discovery schema changes are always informational**
  (`INFO` severity, capped at `PASS`) — a table, column, or detected
  technology appearing or disappearing is reported for visibility, never
  scored as a defect.
- **Assessment-category regression** compares each Phase 5 category's
  status by name with deterministic severities: `PASS -> WARNING` =
  medium, `PASS -> FAIL` / `WARNING -> FAIL` = high; missing/undecided
  data on either side is never treated as a regression.
- **No numeric quality score** — regression status reuses the existing
  `PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED` vocabulary and the exact same
  overall-status rule Phase 5 already established.
- **Schema-version compatibility is strict**: an unrecognized baseline
  `schema_version` is refused outright with a clear error, never partially
  parsed; a differing *tool* version is recorded (not an error) so both
  versions are visible in the comparison output.
- **Safety matches `assess` exactly**: `baseline save`/`baseline compare`
  share the identical `--target`/`--performance`/`--database-profile`
  opt-in flags and safety gates `assess` already has via one shared
  pipeline implementation — no separate, looser safety story for baseline
  commands. `baseline compare` without `--target` sends zero network
  traffic.
- New `regression/` package: `models.py` (`BaselineSnapshot` and its
  sub-snapshots, `ChangeType`, `MetricDelta`, `RegressionFinding`,
  `RegressionCategory`, `RegressionSummary`), `snapshot.py`
  (`build_snapshot()`), `baseline_store.py` (`save_baseline()`
  /`load_baseline()`), `rules.py` (`status_from_findings()`),
  `functional_compare.py`/`performance_compare.py`/`database_compare.py`
  /`discovery_compare.py`/`assessment_compare.py` (the five category
  comparators), `engine.py` (`compare()` orchestration), `serializers.py`
  (standalone `baseline compare` text/json/markdown).
- `core/errors.py`: added `RegressionError` (additive only).
- `core/configuration/config.py`: new `RegressionConfig` section with
  safe non-zero default performance-regression thresholds.
- `reporting/{json,markdown,html}_report.py` gain a `regression`
  section/key (`null`/absent when no `--baseline` was given).
- New fixture: `tests/fixtures/regression-project/` — a single `GET
  /unstable` endpoint used to produce a real, deterministic PASS-then-FAIL
  transition against the existing offline fixture server for end-to-end
  functional-regression testing.

### Fixed

- `core/configuration/config.py::_build_section()` previously replaced a
  dict-valued config field (e.g. `regression.performance`) wholesale on
  any override rather than merging over its defaults — overriding just
  one regression threshold in `universal-test.yaml` would have silently
  dropped every other default threshold, disabling regression detection
  for every metric except the one explicitly configured. Found while
  writing Phase 7's own config tests; fixed by merging dict-valued fields
  over their dataclass defaults. `performance.thresholds` (whose default
  is an empty dict) is unaffected by the fix.

### Known limitations (Phase 7)

- No "baseline policy" configuration to escalate database/discovery
  schema changes past `INFO` severity — the brief names this as a future
  concept without specifying its shape; nothing was speculatively built.
- No historical/multi-baseline trend tracking — one baseline compared
  against one current run at a time, matching the brief's own scope.
- No CI/CD integration (exit-code gate wiring, PR annotations) — deferred
  to Phase 8.
- No AI-assisted regression explanation — fully deterministic.
- Performance regression only compares concurrency levels present in
  both runs — no interpolation between non-matching levels.

### Added — Phase 8 (CI/CD Integration + Quality Gate)

- `universal-test assess` now has a stable, documented exit-code contract:
  `0` = Quality Gate passed, `1` = Quality Gate failed, `2` = configuration
  error, `3` = infrastructure/execution error. **A completely unreachable
  target is `3`, not `1`** — it's an infrastructure problem, not a quality
  regression, unless a project explicitly configures otherwise.
- New deterministic, configurable **Quality Gate**: a `category ->
  [values]` policy (`quality_gate.fail_on`/`warn_on` in
  `universal-test.yaml`) evaluated by one function, no hard-coded/scattered
  policy logic. Safe default policy: `critical`/`high` regression, a real
  functional test failure, and a performance threshold breach fail the
  build; `medium` regression, a database schema change, and a discovery
  change warn without blocking; `UNKNOWN`/`NOT_ASSESSED` never
  automatically fail a build.
- New `--ci` flag (assess-only): forces non-interactive behavior (no
  confirmation prompt, even if stdin happens to look like a TTY) and
  prints a machine-scannable console summary. **`--ci` never authorizes
  network traffic by itself** — `--yes` is still required separately for
  any real traffic.
- CI environment detection (`CI`/`GITHUB_ACTIONS`/`GITLAB_CI`
  /`JENKINS_URL`/`TF_BUILD`/etc.) — informational only (improves a log
  message); never relaxes safety, never substitutes for `--yes`.
- `report.json` gains a `quality_gate` key; `report.md`/`report.html` gain
  a "Quality Gate" section — no finding here can carry a secret.
- Bounded, narrow CI retry (`ci.retry.count` in `universal-test.yaml`,
  hard-capped at 2): retries `assess`'s functional-execution step only,
  and only on a total transport wipeout (likely network instability) —
  never a partial failure, never a real assertion/threshold failure, so it
  can never mask a genuine regression.
- New `quality_gate/` package: `models.py` (`QualityGateStatus`,
  `ExitCode`, `QualityGatePolicy`, `QualityGateRule`, `QualityGateFinding`,
  `QualityGateResult`), `signals.py` (collects rule signals from an
  already-built assessment/regression — never re-discovers/re-executes/
  re-compares anything), `engine.py` (`evaluate()` — the single
  policy-application function, including the infra-error short-circuit),
  `serializers.py` (`--ci` console summary), `ci_detection.py`.
- `core/configuration/config.py`: new `QualityGateConfig` (with policy
  validation raising a clear config error on a malformed shape) and
  `CiConfig`/`RetryConfig` sections.
- Three CI provider templates under `examples/ci/`: `github-actions
  /universal-test.yml`, `gitlab/universal-test.yml`, `jenkins/Jenkinsfile`
  — each a documented starting point, not a working pipeline: installs
  `universal-test` as a plain `pip install` (no provider SDK), runs
  `assess --ci --yes --target ... --baseline ... --output reports/`,
  relies on the CLI's own exit code, and uploads `reports/`
  unconditionally (pass or fail). Each documents that CI never overwrites
  `baseline.json` — updating a baseline is always its own separate,
  deliberately-triggered step.

### Changed

- `assess --baseline <path>` pointed at a file that can't be loaded now
  exits `2` (configuration error) instead of silently continuing with
  `regression=None` at exit `0` — a deliberate Phase 8 tightening (the
  report is still written in full; only the exit code changed) so a broken
  `--baseline` reference can't silently look like a passing CI run.
- `core/configuration/config.py::_build_section()` now validates
  `quality_gate.fail_on`/`warn_on` shape at load time (a mapping of
  category -> list of strings), raising `ConfigurationError` immediately
  on a malformed policy rather than failing later inside gate evaluation.

### Known limitations (Phase 8)

- The `0/1/2/3` exit-code contract and `--ci` apply to `assess` only —
  other subcommands keep their pre-existing Phase 1-6 exit-code
  conventions, not retrofitted this phase.
- No performance-execution retry — only the functional-execution step is
  retried, and only on a total transport wipeout.
- No numeric quality score — unchanged from Phase 5/7.
- No automatic branch-protection/PR-blocking configuration — this tool
  produces the exit code and report; wiring it to a provider's branch
  protection is the project's own responsibility.
- CI provider templates are validated for YAML well-formedness and
  expected CLI flags only, never against a live GitHub/GitLab/Jenkins
  instance, per the brief's own instruction not to connect to any of them.

### V1 Hardening / Architecture / Safety Audit (pre-1.0.0 freeze)

Full-repository audit across Phases 1-8 before the V1.0 freeze. See
`docs/V1_HARDENING_AUDIT.md` for the complete findings and
`docs/V1_FREEZE.md` for the frozen V1 capability/contract surface.

### Fixed

- **Security: `Set-Cookie`/`Cookie` header values were never redacted.**
  `core/redaction.py` covered `password`/`token`/`api_key`/`authorization`
  /etc. but not cookies at all — a real target setting a session cookie in
  its response would have had that value written verbatim into
  `report.json`/`.md`/`.html` and any saved `baseline.json`. Fixed by
  adding cookie coverage to both the key=value and structured-mapping
  redaction patterns.
- **Windows console compatibility**: several `AssessmentFinding`
  /`RegressionFinding` description strings and two report-renderer
  templates still contained a raw em dash, which garbles when printed to
  this project's default Windows console codepage (the same bug class
  fixed in Phases 6-7, reintroduced via new finding text added in Phases
  7-8). Replaced with a plain ASCII hyphen everywhere; added a durable
  regression test (`tests/test_windows_console_compatibility.py`) that
  exercises the actual code paths rather than relying on a static grep.
- Minor dead code: 2 unused imports and 1 placeholder-less f-string in
  `src/`, plus the same class of issue in 5 test files (found via a
  one-time `pyflakes` pass).

### Added

- `tests/fixtures/e2e-project/` — a canonical end-to-end fixture (OpenAPI
  spec, real SQLite database, Docker/CI/pytest evidence, a fixture secret
  pattern) and `tests/e2e/test_e2e_pipeline.py` — runs every implemented
  subcommand against it end-to-end, including a full-pipeline determinism
  check, entirely against local fixtures (no public internet).
- `tests/cli/test_exit_code_matrix.py` — an explicit, independently-
  diagnosable test for every scenario in the `0/1/2/3` exit-code contract,
  including the subtle "timeout is an infrastructure error, not a quality
  regression" case.
- `docs/V1_HARDENING_AUDIT.md`, `docs/V1_FREEZE.md`.

### Audit result

No architecture boundary violations found (Core imports no adapter/
`httpx`/database driver/CI SDK; `assessment`/`regression`/`quality_gate`
never re-execute discovery/tests/assessment; `reporting` contains no
business logic; CLI has no duplicated orchestration). No unsafe network/
database/repository-execution behavior found. No overclaiming
documentation language found. **563 tests passing** (526 before this
audit, 37 new) — no existing test weakened or deleted.
