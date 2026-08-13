# Browser / Web UI Functional Testing

Phase 9. Given an explicit, user-authorized target, Universal Test can
launch an isolated browser, perform a small set of bounded UI actions, and
evaluate assertions against the live page - reusing the same Core test
engine, assertion engine, assessment, and reporting used by REST testing.

This document covers installation, CLI/GUI usage, and the supported
actions/assertions/limitations. For the safety model itself (target
policy, permissions, redaction, process cleanup), see
[`BROWSER_SAFETY.md`](BROWSER_SAFETY.md).

## Installation

Browser testing is an **optional** capability. The base install works with
zero of it present.

```bash
pip install universal-test[browser]
```

This installs the `playwright` Python package only - it does **not**
download a browser binary. Browser binaries are large (100-300MB) and must
be installed explicitly:

```bash
universal-test browser install
# or a specific engine:
universal-test browser install --engine firefox
```

If Playwright or a browser binary is missing, browser testing reports
`NOT_ASSESSED` with a clear reason - it never crashes and never silently
falls back to a different behavior.

## CLI usage

```bash
# Show the test plan without launching a browser
universal-test browser test ./my-static-site --target http://localhost:8080 --dry-run

# Run the default smoke test against an explicit target
universal-test browser test ./my-static-site --target http://localhost:8080 --yes

# Static HTML file, opened directly
universal-test browser test ./my-static-site --target file:///C:/path/to/index.html --yes

# Capture screenshots and allow external navigation
universal-test browser test ./my-app --target https://staging.example.com \
  --allow-external --screenshots --yes
```

`--target` is always required for real execution (never guessed, never
scanned for). `--yes` is required outside an interactive terminal, or you
will be shown the plan and asked to confirm.

### As part of `assess`

Browser testing is **disabled by default** in `assess` - a frontend being
detected never triggers it.

```bash
universal-test assess ./my-project --target http://localhost:3000 --browser --yes
```

Without `--browser`, the report shows:

```text
Browser Testing
NOT ASSESSED
Browser testing was not requested. ...
```

## GUI usage

The GUI exposes a "Browser / UI Testing" checkbox next to Performance and
Database Assessment. Checking it reveals a confirmation box explaining
that a real browser will be launched and that no credentials will be
guessed - an explicit confirmation checkbox must also be checked before
the run proceeds (the same pattern as Performance Testing's confirmation).
Results render in the same category grid as every other assessment
category.

## The default smoke test

When no explicit test definition is supplied, Universal Test generates one
conservative smoke test:

1. Navigate to the target.
2. Assert the page body is visible.
3. Assert the page has a non-empty title.
4. Record console/page-error/network-failure counts as evidence (never
   auto-failing on them).

It never clicks, submits a form, uploads a file, or requests a browser
permission - even if static analysis detected buttons, forms, or
`getUserMedia`/`MediaRecorder` usage on the page.

## Supported actions

`navigate`, `click`, `fill`, `select`, `check`, `uncheck`, `press`,
`wait_for`. No arbitrary JavaScript execution is exposed as a user action.

## Supported selectors

`role`, `label`, `text`, `placeholder`, `test_id`, `css`. An ambiguous
selector (matches zero or more than one element for an action) is an
execution error, never an arbitrary-match guess.

## Supported assertions

`visible`, `hidden`, `text_contains`, `text_equals`, `url_equals`,
`url_contains`, `page_title`, `element_count`, `attribute_equals`,
`input_value`, `checked`, `enabled`, `disabled`, `console_summary`
(diagnostic - records error counts as evidence, never fails unless a
`max_console_errors` threshold is explicitly configured).

## Static websites

A static site (plain HTML/CSS/JS, no build step) is a first-class target.
Use `file://` for a single page, or point `--target` at a local HTTP
server you already run. Universal Test does not start your project's own
dev server for you (`npm run dev`, etc. are explicitly out of scope for
this phase).

## Failure classification

| Situation | Status |
|---|---|
| All assertions passed | `PASS` |
| An assertion failed (e.g. element not visible) | `FAIL` |
| Target unreachable / selector ambiguous or missing / a single step timed out | `ERROR` |
| The whole TestCase exceeded its `test_timeout_seconds` wall-clock budget | `ERROR` |
| Playwright / browser binary not installed | `NOT_ASSESSED` |
| Browser testing not requested | `NOT_ASSESSED` |

`ERROR` is infrastructure/execution evidence, not proof the application is
defective — this applies equally to a TestCase timeout: exceeding the
configured budget is never reported as `PASS`, and never reclassified as an
application defect.

## Timeout hierarchy

```
Run timeout
    +-- TestCase timeout (test_timeout_seconds -- a true hard wall-clock ceiling)
          +-- navigation timeout (navigation_timeout_seconds)
          +-- action timeout (action_timeout_seconds)
          +-- assertion/element-resolution timeout (action_timeout_seconds)
```

`test_timeout_seconds` bounds the *entire* TestCase — every step combined —
not just each step individually. Before every navigation/action/wait
Playwright call, the executor computes `min(that call's own configured
timeout, time actually left in the TestCase budget)` and passes it as that
call's timeout. A step whose own timeout would otherwise run long is cut
short once the TestCase budget runs out; once the budget is already spent,
no further browser operation is attempted at all — the TestCase fails
immediately with `ERROR` instead of running each remaining step's timeout
in full. Concretely: with `test_timeout_seconds=2` and a step's own
`action_timeout_seconds=10`, the whole TestCase still completes in
approximately 2 seconds, not 10.

This bound applies to every blocking browser operation in a TestCase
(navigation, click/fill/etc., `wait_for`, and the element-state resolution
used to build assertion evidence) — the only unbounded-by-design work is
the small amount of non-blocking Python in between calls (redaction,
context assembly), which is the "small scheduling/cleanup overhead" this
hard ceiling explicitly allows for.

Configure it under `browser.test_timeout_seconds` in `universal-test.yaml`
(default 60s, hard-capped at 600s regardless of what a project configures —
see `BROWSER_SAFETY.md`).

## Multi-step workflows

For a single one-off smoke test, everything above is enough. For an
explicit, repeatable, multi-step workflow (e.g. "log in, then verify the
dashboard"), see [`WEB_SCENARIOS.md`](WEB_SCENARIOS.md) — it reuses every
action/assertion/selector documented here, just sequenced and named.

## Known limitations

- One browser context per run; no concurrency (spec Phase 9 scope).
- No visual regression, accessibility auditing, or security scanning.
- No AI-generated test plans - only the deterministic smoke test and
  explicit hand-written test definitions.
- A TestCase timeout does not forcibly tear down the shared browser
  context mid-run (a run may execute several TestCases sequentially against
  one context, per the "no concurrency, one context per run" design) — the
  guarantee is that no browser process is left running once the whole run
  (`browser_session()`) completes, not that the very next TestCase in the
  same run is guaranteed a perfectly pristine page state after a prior one
  timed out. In practice this rarely matters: the built-in smoke test is
  always exactly one TestCase per run.
- File upload/download is detected by static analysis but not exercised by
  browser testing in this version (reported `NOT_ASSESSED` for that
  specific capability, per the safety model).
