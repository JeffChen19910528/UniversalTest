# Browser Testing Safety Model

Phase 9's browser adapter follows the same "safe by default" rule as
every other capability in Universal Test (skill.md §4.2): nothing here
runs unless explicitly requested, and every boundary below is enforced in
code, not just documentation.

## Disabled by default

- `assess ./project` never launches a browser. A detected frontend never
  implies browser execution.
- `assess --browser` still requires an explicit `--target` and `--yes`
  (or an interactive confirmation).
- The GUI requires both the "Browser / UI Testing" checkbox **and** a
  separate confirmation checkbox - the same two-step gate Performance
  Testing already uses.

## Target policy

Enforced by `adapters/browser/target_policy.py::validate_target()`, called
before any browser is launched:

- Allowed by default: `http(s)://localhost`, `http(s)://127.0.0.1`,
  `http(s)://[::1]`, and any `file://` URL.
- Anything else requires the explicit `--allow-external` flag
  (`allow_external=True` at the API level).
- No port scanning, no guessing, no following URLs found in a README or
  in scanned HTML - the target must be supplied by the user.
- Universal Test never attempts to infer whether a target "looks like
  production." The only safety boundary is explicit target + explicit
  authorization.

## Browser isolation

Each run launches exactly one fresh browser + browser context
(`adapters/browser/executor.py::browser_session()`). Cookies,
localStorage, sessionStorage, cache, and service workers are never reused
across runs.

## No credential guessing

This version has no login/authentication flow. It never scrapes
credentials from the repository, inspects `.env` values, guesses
passwords, or performs credential spraying/brute force.

## No automatic permission grants

Microphone, camera, geolocation, notifications, and clipboard permissions
are never granted automatically - there is no code path in this adapter
that calls a permission-granting API. A page that uses `getUserMedia`/
`MediaRecorder` is reported by static analysis as having that capability;
browser testing never exercises it.

## No arbitrary JavaScript execution

The only actions exposed are `navigate`, `click`, `fill`, `select`,
`check`, `uncheck`, `press`, `wait_for`. There is no `evaluate(...)`-style
action available to a test definition.

## External navigation control

A `navigate` step to a URL outside the authorized target's origin raises
an error unless `--allow-external` was set - this is checked before the
navigation happens, not after.

## Secret redaction

All console messages, network-failure details, and resolved element
attribute/value evidence pass through `core/redaction.py`'s existing
`redact()`/`redact_mapping()` (`adapters/browser/redaction.py`) before
becoming part of any `TestResult`/`Evidence`/report. This is the same
redaction infrastructure the REST adapter uses - there is no second
redaction system to keep in sync.

Browser storage (`localStorage`, `sessionStorage`, cookies, IndexedDB) is
never read into the execution context in the first place - there is
nothing to redact because it is never collected.

## Bounded timeouts

Every navigation/action has a timeout, and every timeout is hard-capped
independent of what a project's `universal-test.yaml` configures
(`core/configuration/config.py::BrowserConfig.__post_init__`,
`MAX_BROWSER_TIMEOUT_SECONDS = 120`, `MAX_BROWSER_TEST_TIMEOUT_SECONDS = 600`).
No browser operation can be configured to wait indefinitely. `0`, negative
values, `NaN`, and `+-infinity` are all rejected (fall back to the
documented safe default rather than producing an unbounded or nonsensical
wait) — this is enforced once, in `BrowserConfig.__post_init__`, which is
the only place these fields are ever set, so no CLI flag, config file, or
environment variable has a path around it.

**TestCase wall-clock timeout** (`test_timeout_seconds`) is a true hard
ceiling on an entire TestCase, not merely on each individual step. Before
every blocking Playwright call, `adapters/browser/executor.py::_remaining_ms()`
computes `min(that call's own timeout, time left in the TestCase budget)`
and passes it as that call's explicit `timeout=` argument; once the budget
is exhausted, no further browser operation is attempted at all — the
TestCase fails immediately with a classified `BrowserTimeoutError` (surfaces
as `ResultStatus.ERROR`, never `PASS`, never treated as an application
defect). This is deliberately *not* implemented with a watchdog thread or
signal: Playwright's synchronous Python API is explicitly single-threaded
(calling it from a second thread is unsupported and unsafe), so per-call
timeout arguments are the only safe mechanism. See
`docs/BROWSER_TESTING.md`'s "Timeout hierarchy" section for the exact
parent/child budget relationship and a worked example.

## Process cleanup

`browser_session()` guarantees cleanup via `finally` at every layer -
page, context, browser, and the Playwright driver itself - so an
assertion exception, timeout, raised error, or `Ctrl+C` (`KeyboardInterrupt`)
propagating through the `with` block still closes everything. No orphaned
browser processes are left behind.

## No automatic browser binary download

`pip install universal-test[browser]` only installs the `playwright`
Python package. The browser binary itself is downloaded only by the
explicit `universal-test browser install` command - never during `scan`,
`assess`, or GUI startup.
