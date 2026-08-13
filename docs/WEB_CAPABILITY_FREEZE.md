# Web Capability Freeze

Frozen after Phase 12 (Final Web QA / Freeze), covering everything built
across Phases 9-11: Browser/Web UI Functional Testing (Phase 9), real-
project validation hardening (Phase 9 Hardening), One-Click Web Assessment
/ Non-Programmer UX (Phase 10), and Web Test Scenario / Workflow Testing
(Phase 11). This document is the definitive statement of what Universal
Test's Web capability promises — treat any future change that contradicts
it as a breaking change requiring an explicit version bump and migration
note, not a silent behavior shift.

**Web capability is frozen after Phase 12.** No Phase 12.1, no Phase 13,
no further Web feature development follows this document. A future
request for AI-assisted Web testing, visual regression, accessibility
scanning, security scanning, mobile/device emulation, cloud/distributed
browser execution, or autonomous/agentic browser testing is new,
separately-scoped product work — it does not reopen Phase 12 and must not
be treated as a bug fix or a natural extension of what already exists.

## Included

- **Static Web detection & analysis** (`discovery/frontend.py`, reused by
  every layer below): routes, forms, interactive elements, browser APIs
  referenced in source (`MediaRecorder`/`getUserMedia`/etc.), auth-UI
  signals, external resources, CSP — all read-only, file-based, zero
  execution.
- **Browser/UI functional testing** (`universal-test browser test`,
  `assess --browser --target <url> --yes`): an isolated, fresh Playwright
  Chromium/Firefox/WebKit context per run navigates to an explicit
  `--target`, executes a bounded auto-generated smoke test (or explicit
  test cases), and asserts observable page state (visibility, text, URL,
  title, element count/attribute/value/checked/enabled) through the same
  `TestEngine`/`AssertionEngine` every other adapter uses.
- **Explicit Web Scenarios** (`universal-test browser scenario
  list|validate|run`, `assess --scenario <id>`): user-authored, multi-step,
  reproducible YAML workflows (`universal-test-web.yaml`) — navigate, fill,
  click, select, check/uncheck, press, wait, and assertion steps — executed
  sequentially with stop-on-first-failure semantics. Secrets are resolved
  only via `value_env` (an environment variable name), never accepted as
  plaintext in the YAML file itself.
- **One-click / non-programmer workflow** (`universal-test web assess`,
  GUI "Web Assessment" card): guided detection → plan preview → explicit
  safety confirmation → run, built entirely on top of the above — no
  parallel test-execution path, no numeric score.
- **GUI Web panels** (`gui/static/`): project selection, Web detection,
  Web Assessment plan/confirm/run/results, Web Scenarios list/detail/dry-
  run/run/results — all rendered from the same backend JSON the CLI and
  reports produce; the GUI never computes an authoritative verdict itself.
- **Assessment integration**: two additional categories, "Browser Testing"
  and "Web Scenarios", each independently `NOT_ASSESSED` (not requested,
  the common default) / `PASS` / `WARNING` (a genuine assertion/step
  failure) / `FAIL` (a total execution wipeout — target unreachable or
  every attempted check errored), following the same "WARNING never
  overclaims to FAIL" convention as Functional Health.
- **Regression**: stable `scenario_id` identity across baseline/compare
  runs; per-scenario PASS→FAIL detected as a regression finding, FAIL→PASS
  counted as an improvement (no spurious regression finding raised for an
  improvement) — verified end-to-end with real baseline/compare cycles in
  Phase 12.
- **Quality Gate**: Browser Testing/Web Scenarios participate in the same
  policy-driven `fail_on`/`warn_on` mechanism as every other category via
  the assessment-level signal; by default neither category can fail a
  build (a missing browser, an unrequested scenario, or even a genuine
  scenario failure requires an explicit policy opt-in to gate on) —
  verified in Phase 12 with both the default policy (safe pass) and an
  explicit opt-in policy (correctly gates).
- **Reporting**: `report.json`/`report.md`/`report.html` each carry a
  "Browser Testing" and "Web Scenarios" section, always present (marked
  `NOT_ASSESSED` with a reason when not run, never silently omitted or
  fabricated as `PASS`); the three output formats and the GUI were cross-
  checked against the same run in Phase 12 and never disagree.
- **Safety boundaries** (`docs/BROWSER_SAFETY.md`): browser testing/
  scenarios are opt-in everywhere (CLI flag + explicit target + `--yes`/
  confirmation; GUI checkbox); `localhost`/`127.0.0.1`/`::1`/`file://`
  allowed by default, anything else requires `--allow-external`; no
  credential guessing (only `value_env`); no automatic permission grants
  (microphone/camera/geolocation/notifications/clipboard/filesystem); a
  fresh browser context per run with guaranteed cleanup on pass, fail,
  error, timeout, and interruption; hard wall-clock timeouts at the Run >
  Scenario > Step level; all secrets redacted through the single existing
  `core/redaction.py`, never a second redaction system.
- **Optional dependency**: the base install never requires Playwright;
  `browser`/`scenario` support is an opt-in `[browser]` extra, and its
  absence degrades every Web-execution capability to `NOT_ASSESSED`, never
  a crash.

## Explicitly Not Included

Do not describe any of the following as a Universal Test Web capability in
any documentation, and treat a request to add one as new, separately-
scoped future product work, not a bug fix or a Phase 12 follow-up:

- Not AI-assisted test generation, failure explanation, or any AI/LLM
  dependency anywhere in the Web pipeline.
- Not an autonomous or agentic browser-testing framework — every action a
  browser takes is an explicit, user-authored step or a narrowly-defined
  smoke-test action; nothing decides what to click next on its own.
- Not visual regression testing (no screenshot-diffing/pixel comparison).
- Not an accessibility compliance scanner.
- Not a security scanner for Web applications (no XSS/CSRF/injection
  probing, no auth bypass testing).
- Not a mobile/device emulation or responsive-design verification tool.
- Not a distributed or cloud browser grid — one local browser process per
  run.
- Not a load/performance testing tool for browser traffic (`performance`
  testing remains HTTP-level only).
- Not a guarantee that microphone/camera/geolocation/notification-gated
  functionality works — those permissions are never auto-granted, so any
  UI path behind them is left `NOT_ASSESSED` unless a scenario is written
  to exercise it explicitly (and even then, only what the scenario
  actually asserts is evidenced).
- Not a replacement for exploratory/manual QA, and not a production-
  readiness or business-logic-correctness guarantee.

## CLI contract

Web-related subcommands, all following the same `--config`/`--output`
/`--format`/`--verbose`/`--dry-run` conventions as every other subcommand:

```
universal-test browser install [--engine chromium|firefox|webkit]
universal-test browser test <path> --target <url> [--allow-external] [--screenshots] [--dry-run] [--yes]
universal-test browser scenario list <path> [--scenario-file <file>]
universal-test browser scenario validate <path> [--scenario-file <file>]
universal-test browser scenario run <path> --scenario <id>|--all --target <url> [--allow-external] [--screenshots] [--dry-run] [--yes]
universal-test web assess <path> [--target <url>] [--yes]
universal-test assess <path> [--browser --target <url>] [--scenario <id> ...] [--allow-external] [--screenshots] [--yes]
```

`--dry-run` never launches a browser, never resolves `value_env`, and
never opens a network connection for any of the above — verified by
instrumentation in Phase 9 Hardening and re-verified in Phase 12.
`--yes` is required for real execution outside an interactive terminal;
all four CLI confirmation prompts (performance/browser-test/web-assess/
scenario-run) share one `_confirm()` helper.

## Configuration contract additions

`universal-test.yaml` gains a `browser` section: `enabled`, `browser`
(`chromium`/`firefox`/`webkit`), `headless`, `navigation_timeout_seconds`,
`action_timeout_seconds`, `test_timeout_seconds`, `allow_external`,
`screenshots` — every timeout is hard-capped independent of what a config
file requests (`MAX_BROWSER_TIMEOUT_SECONDS`/
`MAX_BROWSER_TEST_TIMEOUT_SECONDS`). A Web Scenario file
(`universal-test-web.yaml`) may set a per-scenario `timeout_seconds`,
hard-capped at `MAX_SCENARIO_TIMEOUT_SECONDS` (1800s).

## Report schema additions

`report.json` gains `browser` (a `BrowserRunResult` — `executed`,
`target`, `browser`, `run_result` summary/results, `not_assessed_reason`)
and `scenarios` (a list of `ScenarioResult` — `scenario_id`, `status`,
`step_count`, `passed_steps`, per-step results). `baseline.json` gains the
same two fields for regression comparison. Neither field, nor
`report.md`/`report.html`, nor any GUI response, can contain a raw
password, token, connection string, or `value_env`-resolved secret —
enforced by `core/redaction.py` and re-verified end-to-end in Phase 12
across five distinct scenario outcomes (pass/fail/error/timeout/a scenario
carrying a live secret value).

## Known limitations

- No historical/multi-run Web trend tracking — one baseline compared
  against one current scenario/browser run at a time (same limitation as
  every other regression domain).
- Screenshot evidence, when enabled, is stored as local files referenced
  by path in the report — not embedded, not uploaded anywhere.
- A Web Scenario's step vocabulary (navigate/fill/click/select/check/
  uncheck/press/wait/assert_*) is intentionally fixed and narrow; it is
  not a general browser-scripting or record/replay system.
- Only Chromium is exercised in the automated test suite's real-browser
  integration tests; Firefox/WebKit are supported by the same code path
  but not continuously verified against a live browser in CI.
- `file://` targets and the built-in static file server
  (`adapters/browser/local_server.py`) never execute a project's own
  build/dev scripts (`npm run dev`, etc.) — only pre-built static output
  is served.

## Deferred features (post-freeze)

Explicitly not started, per every Phase 9-12 brief's own stop condition
and this freeze's scope: AI-assisted Web test generation or failure
explanation, visual regression, accessibility scanning, Web security
scanning, mobile/device emulation, distributed/cloud browser execution,
autonomous/agentic browser agents, a general-purpose browser scripting
language, and any numeric quality score for Web results.
