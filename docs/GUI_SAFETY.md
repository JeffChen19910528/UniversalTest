# GUI Safety Model (Post-V1 Phase 1)

The GUI inherits every V1 Core safety rule (skill.md §4.2) and adds GUI-
specific guarantees on top.

## Network exposure

- The GUI server only ever binds to a loopback address (`127.0.0.1`).
  `gui/server.py::make_server()` raises `ValueError` if asked to bind
  anywhere else — this is enforced in code, not just documentation.
- Startup never requires administrator privileges, never modifies the
  Windows firewall, never scans the LAN, and never connects to any
  external server on its own.
- No inbound network exposure is created. A user on another machine on
  the same network cannot reach this GUI.

## No guessed test target

- If the user leaves "測試目標" (Test Target) empty, functional testing
  still *generates* test cases (discovery/generation only) but never
  executes an HTTP request — this is the same `RestRunResult.executed`
  gate the CLI's `test`/`assess` commands already use, not new GUI logic.
- The GUI never falls back to an OpenAPI `servers:` URL, a config file
  default, or any other inferred target. `AssessmentRequest.target`
  is `None` unless the user typed something into the Target field.

## Performance testing requires two explicit signals

Checking "效能測試" (Performance Testing) alone does **not** run a
performance test. `application/service.py::_run_performance()` requires
**both**:

1. `request.run_performance` (the checkbox), **and**
2. `request.performance_confirmed` (the separate confirmation checkbox
   shown only after the first is checked, with the explicit warning
   "效能測試會對指定服務產生額外流量").

This mirrors the CLI's interactive `Proceed? [y/N]` prompt, except the
GUI can't rely on a TTY prompt — the confirmation checkbox is the GUI's
equivalent of `--yes`, and the GUI never sets it implicitly.

## Database assessment stays read-only and opt-in

- Database assessment only runs when the user explicitly supplies a
  database profile file (the same `--database-profile` YAML shape the
  CLI uses, with credentials referenced via environment variables, never
  embedded).
- Discovering database evidence in a project (e.g. a `docker-compose.yml`
  service or a connection string reference) never implies permission to
  connect — same rule as the CLI (`skill.md` §4.2, Phase 6 brief §4).
- The database adapter itself remains read-only; the GUI does not add any
  write path.

## Secrets

- Credentials are never entered into the GUI as plaintext and never
  stored in GUI state, browser localStorage, or any report. The
  environment-variable credential model from V1 is unchanged — the GUI's
  "使用環境變數" fields ask for an *environment variable name*, never a
  password value.
- `gui/server.py`'s JSON responses are built by hand from each domain
  model's existing `to_dict()` (the same one the CLI's JSON report uses)
  — nothing generically serializes an object that might carry a secret
  field.

## Never overclaiming

- The result dashboard has no numeric score. Every category and finding
  uses the same five-value `AssessmentStatus` vocabulary as the CLI
  (`pass`/`warning`/`fail`/`unknown`/`not_assessed`), and a category that
  was never run is shown as "尚未評估" / "尚未檢查" with its reason, never
  silently omitted or shown as passing.

## Process safety

- The GUI never executes project code itself. It only orchestrates the
  same Core calls the CLI makes against the target the user provided.
- An unhandled exception inside one assessment run is caught, surfaced to
  that run's GUI screen as a friendly message plus an opaque `error_id`,
  and does not crash the server process — other runs, and future runs,
  are unaffected.

## Error responses never leak raw exception detail

An unhandled exception's message, type, or traceback can legitimately
contain a secret it never should have (a driver surfacing a raw connection
string, a header value from an HTTP client error, etc.) — this is not
hypothetical, it's the normal shape of Python tracebacks. So:

- Every GUI HTTP error response (`do_GET`/`do_POST`'s catch-all, and a
  failed assessment run) returns only `{"error": "...", "error_id": "..."}`
  — never `traceback.format_exc()`, an exception's `str()`, or its type
  name. The browser (and anything inspecting the network tab) never sees
  more than that.
- The full traceback is logged server-side only, through the shared
  `universal_test` logger, whose `RedactingFormatter`
  (`core/logging_setup.py`) scrubs known secret patterns before the text
  ever reaches a log line — the same redaction the CLI's own logs go
  through.
- `tests/gui/test_gui_server.py::test_internal_error_never_leaks_traceback_or_secrets`
  and `::test_assess_run_failure_reports_only_an_error_id` assert this
  against real HTTP responses, with a deliberately secret-laden exception
  message, not just by code inspection.

## Bounded run history, one run at a time

- `gui/runs.py::RunRegistry` only ever retains a bounded number of
  *completed* runs (oldest evicted first) — a long-lived GUI process
  cannot accumulate unbounded memory (events/queue/request/outcome) just
  by being left open and re-run many times. An active run is never a
  candidate for eviction.
- Starting a second assessment while one is still running is rejected
  (`RunAlreadyActiveError`, HTTP 409) — both as a frontend affordance (the
  Start button disables itself) and as a server-side backstop, since this
  is a single-user local tool, not a multi-tenant service.
