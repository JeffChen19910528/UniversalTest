# ROADMAP.md

Phase order is fixed by `skill.md` §23. Do not skip ahead or parallelize phases —
each one builds on domain models/interfaces the previous phase established.

| Phase | Name | Status | Summary |
|---|---|---|---|
| 0 | Repository initialization | ✅ Done | Planning docs created (this pass). |
| 1 | Core | ✅ Done (skeleton) | Domain models, config, assertion engine, test engine, orchestrator, CLI skeleton, logging, redaction, error hierarchy, unit tests. |
| 2 | Discovery | ✅ Done | Filesystem/language/project-type/framework/build-system/infrastructure/database/API-evidence/test-framework/secret detection, all read-only with confidence+evidence. `universal-test scan` implemented (text/json/markdown). |
| 3 | REST Adapter | ✅ Done | OpenAPI 3.x parser (internal `$ref` resolution), normalized endpoint model, conservative positive/negative test generation, `httpx`-based execution, auth (env-var credentials), full `jsonschema` validation, dry-run, multi-spec safety. `universal-test test` implemented (text/json/markdown). Report *output* is still the adapter's own lightweight serializers, not the unified Phase 5 report — see SPECIFICATION.md §7. |
| 4 | Performance | ✅ Done | Technology-independent engine (`testing/performance/`): bounded `ThreadPoolExecutor` concurrency, documented nearest-rank percentiles (P50/P90/P95/P99), error classification (HTTP/timeout/network), independent threshold evaluation, baseline/load/stress/custom profiles with hard safety ceilings, dry-run + interactive confirmation. Reuses Phase 3's REST executor pattern and deterministic request generation — no baseline-comparison regression engine yet (explicitly deferred). `universal-test performance` implemented (text/json/markdown). |
| 5 | Unified Assessment & Reporting | ✅ Done | `assessment/` (7 categories, deterministic overall-status rule, evidence-linked findings, coverage, unknown/not-assessed tracking) aggregates Phase 2-4 results without recomputing them. `reporting/` emits `report.json`/`.md`/`.html` (offline, no CDN/JS, HTML-escaped). `universal-test assess` implemented — safe by default (no traffic without `--target`; performance additionally opt-in via `--performance`, same safety gate as the standalone command). No regression engine, no numeric score, no AI — all explicitly deferred per the phase's own brief. |
| 6 | Database Adapter (read-only) | ✅ Done | `adapters/database/` — SQL Server (`pyodbc`), PostgreSQL (`psycopg2`), MySQL (`mysql-connector-python`), SQLite (stdlib, read-only URI) drivers behind one `DatabaseDriver` contract with **no arbitrary-SQL-execution method at all** — metadata-only (`list_tables/list_views/list_columns/list_primary_keys/list_foreign_keys/list_indexes/get_safe_row_count`). Connects only with an explicit `--database-profile <path>` (`readonly: true` mandatory, refused otherwise); credentials read from named env vars, never the profile file or the repo. Discovering "SQL Server detected" (Phase 2) never implies a connection. `universal-test database <path> --database-profile <path>` implemented (text/json/markdown + `--dry-run`); `assess` gains an eighth "Database Health" category, `NOT_ASSESSED` (never `FAIL`) on missing driver/timeout/no profile. Driver dependencies are optional extras (`pip install universal-test[database]`) — Core/Discovery/REST/Performance/Assessment all still work with zero of them installed. |
| 7 | Regression / Baseline Comparison Engine | ✅ Done | `regression/` — versioned `BaselineSnapshot` (tool/schema version, project identity, git revision, discovery/functional/performance/database/assessment summaries), immutable `baseline save`/read-only `baseline compare`, per-test-ID functional regression, direction-aware tolerance-based performance regression (configurable via `regression.performance` in `universal-test.yaml`, safe non-zero defaults), INFO-only database/discovery schema-change detection, assessment-category-transition severity rules (deterministic, no scoring), one shared overall-status rule reused from Phase 5. `universal-test baseline save`/`baseline compare` implemented (text/json/markdown); `assess --baseline` folds a "Regression" section into the unified report. No numeric quality score, no CI/CD integration — explicitly deferred per the phase's own brief. |
| 8 | CI/CD Integration + Quality Gate | ✅ Done | `quality_gate/` — CI-provider-independent (`QualityGatePolicy`/`QualityGateRule`/`QualityGateFinding`/`QualityGateResult`/`ExitCode`), deterministic `category -> [values]` policy (`quality_gate.fail_on`/`warn_on` in `universal-test.yaml`, safe default matching the brief exactly), no scattered `if` policy logic. Stable `assess` exit-code contract (0 pass / 1 fail / 2 config error / 3 infrastructure error) — a completely unreachable target is correctly `3`, not `1`, per Phase 5's existing transport-wipeout-vs-check-failure distinction. `--ci` forces non-interactive behavior without ever implying `--yes`; CI environment detection (`CI`/`GITHUB_ACTIONS`/`GITLAB_CI`/`JENKINS_URL`/etc.) is informational only and never relaxes safety. `report.json`/`.md`/`.html` gain a "Quality Gate" section. Bounded, narrow CI retry (`ci.retry.count`, hard-capped) for total-transport-wipeout only — never masks a real regression. GitHub Actions/GitLab CI/Jenkins templates under `examples/ci/`, each a plain-CLI-invoking, provider-SDK-free starting point with documented immutable-baseline and artifact-upload guidance. |
| 8.5 | Frontend / Web Application Analysis Adapter | ✅ Done | `discovery/frontend.py` + `FrontendInfo`/`FrontendSignal` models, extended framework/build-system/test-framework detection (Next.js/Nuxt/Svelte/SvelteKit/Solid/Astro; Vite/Webpack/Rollup/Turbopack/Angular CLI; Playwright/Cypress/Testing Library/WebdriverIO/Puppeteer/Karma/Jasmine), `adapters/frontend/` (discovery + testability assessment only), `assessment/frontend_assessment.py` ("Frontend / Web Application Health" category, capped below `FAIL`), CLI/report/GUI integration. Discovery + testability assessment only — explicitly **not** the Browser Adapter (Phase 9): no browser is launched, no UI test executes; every surface reports "Browser/UI Execution: NOT_ASSESSED". See `docs/FRONTEND_ANALYSIS.md`. |
| 9 | Browser / Web UI Functional Testing Adapter | ✅ Done | `adapters/browser/` — Playwright-based, optional `[browser]` extra (base install works with zero of it present), explicit `universal-test browser install` (never automatic). Explicit-target-only safety policy (localhost/127.0.0.1/::1/file:// by default, `--allow-external` opt-in), fresh browser context per run, no credential guessing, no auto-granted permissions, no arbitrary JS execution, hard-capped timeouts, existing `core/redaction.py` reused. Reuses the existing `TestEngine`/`AssertionEngine`/`Orchestrator` — no second test engine. Conservative built-in smoke test (navigate/assert loaded/assert title/capture console+page errors) plus explicit hand-written test definitions (navigate/click/fill/select/check/uncheck/press/wait_for actions; role/label/text/placeholder/test_id/css selectors; visible/hidden/text/url/title/element_count/attribute/input_value/checked/enabled/disabled assertions). `universal-test browser test`/`browser install` implemented; `assess --browser --target ... --yes` opt-in (disabled by default); GUI exposes it as one more opt-in checkbox with an explicit confirmation gate; Assessment gains a tenth "Browser Testing" category (execution-driven, like Functional/Performance); Reporting gains a "Browser Testing" section (json/markdown/html); Regression gains `browser_compare.py` (per-test-ID PASS/FAIL/ERROR, mirrors Functional). See `docs/BROWSER_TESTING.md` and `docs/BROWSER_SAFETY.md`. |
| 10 | One-Click Web Assessment / Non-Programmer UX | ✅ Done | Not a new testing engine — `universal-test web assess` (CLI) and a "Web Assessment" GUI card, both thin guided presets over the existing `assess` pipeline (discovery + static analysis + browser smoke test + report). Reuses `FrontendType` web detection, the existing `/api/assess` run/report/results machinery, and the Phase 8.5/9 Application Health/Testability/Assessment Coverage summary card (now also showing Browser Testing) unmodified — one new read-only `POST /api/web/detect` endpoint (wraps `discover()`) is the only new backend surface. Safety unchanged: explicit target still required, `--yes`/GUI confirmation checkbox/`--allow-external` all unchanged from Phase 9. No numeric score. See `ARCHITECTURE.md` §18 and `SPECIFICATION.md` §4.15. |
| 11 | Web Test Scenario / Workflow Testing | ✅ Done | Not a new test engine — an explicit, user-authored, repeatable multi-step Web workflow layer sitting entirely on the existing Browser Adapter. `adapters/browser/scenario_models.py`/`scenario_loader.py`/`scenario_runner.py`/`scenario_serializers.py`: framework-independent serializable `WebScenario`/`ScenarioStep` model, YAML file (`universal-test-web.yaml`), offline validation, sequential stop-on-failure execution where each step is one synthesized `TestCase` run through the unmodified `TestEngine.run()`. Secrets via `value_env` only, resolved only at execution time, never logged/reported. Scenario timeout cascades into each step via a one-line additive `test_timeout_seconds_override` on Phase 9 Hardening's existing per-TestCase timeout — no second timeout system. `universal-test browser scenario list/validate/run` implemented; opt-in `--scenario <id>` on `assess`/`baseline save`/`baseline compare`; GUI "Web Scenarios" card (`/api/web/scenarios`, `/api/web/scenario/run`). Eleventh assessment category "Web Scenarios" (execution-driven), `regression/scenario_compare.py` (stable scenario-ID identity comparison), JSON/Markdown/HTML report sections — Quality Gate needed zero engine changes. Found and fixed two real defects along the way: relative-URL navigation was never resolved against the target origin (`executor.py`), and all four CLI confirmation prompts shared a latent Windows `EOFError` robustness gap. See `ARCHITECTURE.md` §19 and `docs/WEB_SCENARIOS.md`. |
| 12 | Final Web QA / Freeze | ✅ Done | Not a feature-development phase — validated Phases 9-11 together (architecture boundaries, status semantics, report consistency, dead code, real-project + scenario matrices, a real-browser Playwright-driven GUI walkthrough, regression/quality-gate cycles) and fixed the genuine defects found: the packaged one-click `.exe` (`release/windows/launch_gui.py`) called `gui/launcher.py::launch()` directly and never configured logging, so a server-side unhandled exception could log an unredacted secret (fixed by making `launch()` configure logging defensively, with a regression test); one unused import and one cosmetic f-string-without-placeholder removed from the browser/scenario layer. Produced `docs/WEB_CAPABILITY_FREEZE.md`. See that document for the full Included/Not-Included capability statement. |
| 13 | .NET / Node / Python adapters | ⬜ Not started | Solution/project detection, build status, dependency + test-runner integration. |
| 14 | AI integration | ⬜ Not started | Optional, off by default, output labeled "AI-generated hypothesis", never bypasses validation/execution layer. |

## Stop points

Per `skill.md` §32, work stops after Phase 1 for a checkpoint: architecture +
Phase 1 spec review before Phase 2 begins. Do not implement Phase 2+ without
explicit go-ahead. (Done — Phase 2 approved and completed 2026-08-09.)

Work now stops again after Phase 2. Do not start Phase 3 (REST test
execution, OpenAPI test generation), performance testing, browser automation,
SQL execution, or AI integration without explicit go-ahead. (Done — Phase 3
approved and completed 2026-08-09.)

Work now stops again after Phase 3. Do not start performance testing, SQL
execution, browser automation, the regression engine, AI integration, or
security exploitation without explicit go-ahead. (Done — Phase 4 approved
and completed 2026-08-09.)

Work now stops again after Phase 4. Do not start the regression engine,
historical baseline comparison, CI/CD integration, the SQL adapter, the
browser adapter, AI integration, security scanning, the blockchain adapter,
or distributed load testing without explicit go-ahead. (Done — Phase 5
approved and completed 2026-08-09.)

Work now stops again after Phase 5. Do not start the regression engine,
historical baseline comparison, CI/CD integration, the SQL adapter, the
browser adapter, AI integration, a security scanner, the blockchain
adapter, or distributed testing without explicit go-ahead. (Done — Phase 6
approved and completed 2026-08-09.)

Work now stops again after Phase 6. Do not start the regression engine,
historical baseline comparison, CI/CD integration, the browser adapter, AI
integration, a security scanner, the blockchain adapter, or distributed
testing without explicit go-ahead. (Done — Phase 7 approved and completed
2026-08-09.)

Work now stops again after Phase 7. Do not start CI/CD integration, the
browser adapter, AI integration, a security scanner, the blockchain
adapter, or distributed testing without explicit go-ahead. (Done — Phase 8
approved and completed 2026-08-09.)

Work now stops again after Phase 8. Do not start the browser/UI adapter,
AI integration, a security scanner, the blockchain adapter, or distributed
testing without explicit go-ahead. (Done — Phase 8.5, Frontend Analysis
Adapter, approved and completed 2026-08-11; explicitly scoped to
discovery + testability assessment only.)

Work now stops again after Phase 8.5. Do not start actual browser/UI test
execution (Playwright/Selenium), visual regression, AI-generated test
generation, a security/CVE scanner, GraphQL/gRPC support, the blockchain
adapter, or distributed testing without explicit go-ahead. (Done — Phase 9
approved and completed 2026-08-12.)

Work now stops again after Phase 9. Do not start AI-generated browser
tests, visual regression, an accessibility scanner, a security scanner,
performance profiling of the browser itself, mobile/cloud browser farms,
automatic project server startup, arbitrary JavaScript execution, or
automatic credential discovery without explicit go-ahead. (Done — Phase 10
approved and completed 2026-08-12.)

Work now stops again after Phase 10. Do not start Web Test Scenario/
Workflow authoring, AI-generated tests, an AI browser agent, visual
regression, accessibility scanning, security scanning, performance
profiling, mobile/cloud/distributed browser testing, automatic login
discovery, or credential guessing without explicit go-ahead. Do not invent
a "Phase 10.1"/"10.2" to keep adding features under this phase. (Done —
Phase 11 approved and completed 2026-08-13.)

Web feature freeze after Phase 11. Do not automatically start AI-generated
tests, an AI browser agent, visual regression, accessibility scanning,
security scanning, browser performance profiling, mobile/cloud/distributed
browser testing, or automatic workflow discovery/generation without
explicit go-ahead. Do not invent a "Phase 11.1"/"11.2". The only
permitted next step without further instruction is Phase 12 — Final Web
QA / Freeze, a validation-and-freeze pass, not a new feature-development
phase.

**Web capability is frozen after Phase 12** (see
`docs/WEB_CAPABILITY_FREEZE.md`). No "Phase 12.1"/"Phase 13 Web follow-up"
— any further Web work (AI-assisted testing, visual regression,
accessibility/security scanning, mobile/cloud/distributed browsers,
autonomous browser agents) is new, separately-scoped future product work,
not a continuation of Phases 9-12.

## Definition of done (applies to every phase, `skill.md` §24)

- [ ] implementation exists
- [ ] unit tests exist
- [ ] integration tests exist where applicable
- [ ] error handling exists
- [ ] CLI behavior documented
- [ ] configuration documented
- [ ] report output implemented (once reporting exists)
- [ ] fixture project exists (once there's something to discover)
- [ ] regression test exists
- [ ] README updated
- [ ] PROGRESS.md updated
