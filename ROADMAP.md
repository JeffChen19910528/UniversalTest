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
| 9 | Browser Adapter | ⬜ Not started | Playwright preferred; page discovery, navigation, form interaction, failure screenshots. Builds on Phase 8.5's `FrontendInfo` (routes/forms/test-framework evidence) but is a separate, unimplemented capability. |
| 10 | .NET / Node / Python adapters | ⬜ Not started | Solution/project detection, build status, dependency + test-runner integration. |
| 11 | AI integration | ⬜ Not started | Optional, off by default, output labeled "AI-generated hypothesis", never bypasses validation/execution layer. |

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
adapter, or distributed testing without explicit go-ahead.

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
