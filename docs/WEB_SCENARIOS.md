# Web Test Scenario / Workflow Testing

Phase 11. Lets you define an explicit, multi-step Web workflow once (e.g.
"Login Smoke Test") and execute it repeatedly, deterministically, and
safely — without Universal Test guessing, generating, or discovering the
workflow on your behalf.

This is **not** a new test engine. A scenario is translated, step by step,
into the same `TestCase`/`AssertionEngine`/Browser Adapter machinery
`docs/BROWSER_TESTING.md` already documents — see `ARCHITECTURE.md` §19
for the implementation detail.

## Scenario file format

YAML, default path `<project>/universal-test-web.yaml` (override with
`--scenario-file`):

```yaml
scenarios:
  - id: login-smoke
    name: Login Smoke Test
    description: Verify that a valid user can reach the dashboard.
    timeout_seconds: 60          # optional, scenario-level wall-clock budget

    steps:
      - id: open-login
        action: navigate
        url: /login               # relative URLs are preferred (portable across environments)

      - id: enter-user
        action: fill
        selector:
          type: label
          value: Username
        value_env: TEST_USERNAME  # secret-safe: read from an environment variable, never inline

      - id: enter-password
        action: fill
        selector:
          type: label
          value: Password
        value_env: TEST_PASSWORD

      - id: login
        action: click
        selector:
          type: role
          role: button
          name: Login              # accepted as an alias for `value` on role selectors

      - id: dashboard
        action: assert_visible
        selector:
          type: text
          value: Dashboard
```

A scenario file may define several scenarios; each needs a stable, unique
`id` (used by regression comparison and CLI/GUI selection — never rename
an existing scenario's `id` if you want its history tracked).

## Secrets

Never put a plaintext password/token in a scenario file. Use `value_env`
to name an environment variable instead:

```yaml
value_env: TEST_PASSWORD
```

The referenced variable is resolved only at the last possible moment,
during real execution — never during `list`, `validate`, or `--dry-run`.
If a required variable isn't set, the scenario reports `NOT_ASSESSED`
with a clear reason before any browser is launched. The resolved value
never appears in a report, log, or GUI response — reports show the
`value_env` reference (e.g. `source: TEST_PASSWORD`), never the value.

## Supported actions

`navigate`, `click`, `fill`, `select` (alias: `select_option`), `check`,
`uncheck`, `press`, `wait_for` (alias: `wait`) — the same conservative set
`docs/BROWSER_TESTING.md` already documents.

## Supported assertions

`assert_visible`, `assert_hidden`, `assert_text`, `assert_text_equals`,
`assert_value`, `assert_attribute`, `assert_url`, `assert_url_equals`,
`assert_title`, `assert_count`, `assert_enabled`, `assert_disabled`,
`assert_checked` — each maps 1:1 onto an existing browser assertion type
(the same `AssertionEngine`, no second assertion vocabulary).

## Selectors

Same selector types as ordinary browser testing: `role`, `label`, `text`,
`placeholder`, `test_id`, `css`. A `role` selector's accessible name may be
written as `name` (as in the example above) or `value` — both work.

## CLI usage

```bash
# List scenarios without executing anything
universal-test browser scenario list ./project

# Validate a scenario file (schema/actions/selectors/assertions/timeouts) --
# never launches a browser
universal-test browser scenario validate ./project

# Show the plan without launching a browser or resolving any secret
universal-test browser scenario run ./project --scenario login-smoke \
  --target http://localhost:3000 --dry-run

# Execute for real
universal-test browser scenario run ./project --scenario login-smoke \
  --target http://localhost:3000 --yes

# Run every scenario in the file
universal-test browser scenario run ./project --all --target http://localhost:3000 --yes
```

`--yes` (or an interactive `Proceed? [y/N]` confirmation) is required for
real execution, exactly like `browser test`/`web assess` — a scenario file
existing is never itself authorization to run it.

### Integrating into `assess`

```bash
universal-test assess ./project --target http://localhost:3000 \
  --scenario login-smoke --yes
```

Adds a "Web Scenarios" category (alongside "Browser Testing") to the
unified assessment/report/regression/quality-gate pipeline. Pass
`--scenario` multiple times to run several scenarios in one `assess` run.

## GUI usage

A "Web Scenarios" card lists scenarios found in the selected project
(`List Available Scenarios`), lets you pick one to see its steps, enter a
target, and either preview the plan or run it after the same explicit
confirmation checkbox used elsewhere in the GUI.

## Execution model

Steps run strictly in order, sharing one browser page for the whole
scenario. The first step that doesn't PASS stops the scenario — every
step after it is recorded `SKIPPED`, never executed. This is deliberate:
a scenario step usually depends on the previous one having succeeded
(you can't fill a password field on a page that never loaded).

## Timeout hierarchy

```
Run timeout
    └── Scenario timeout (timeout_seconds -- a true hard wall-clock ceiling)
          └── Step timeout (per-step, further capped by remaining scenario budget)
```

A step's own timeout is always capped to whatever remains of the
scenario's budget — the same hard-ceiling mechanism Phase 9 Hardening
built for a single browser TestCase, reused here rather than
reimplemented. If the scenario's overall budget runs out mid-scenario,
the current step is reported `ERROR` ("scenario exceeded its configured
timeout") and nothing further executes.

## Status semantics

| Status | Meaning |
|---|---|
| `PASS` | Every step ran and every assertion held. |
| `FAIL` | The scenario executed, but an assertion did not hold. |
| `ERROR` | The scenario could not be reliably executed (target unreachable, selector ambiguous, timeout, browser unavailable). |
| `NOT_ASSESSED` | The scenario was not executed (not requested, missing target, missing required `value_env`, or disallowed target). |

`ERROR` is never presented as proof the application is defective;
`NOT_ASSESSED` never silently becomes `PASS`.

## Safety

Every existing Browser Adapter safety rule applies unchanged: explicit
target only (never inferred from README/package.json/source), localhost/
127.0.0.1/::1/file:// allowed by default (`--allow-external` required
otherwise), no permission auto-grants, no arbitrary JavaScript execution,
fresh browser context, hard-capped timeouts, secrets redacted via the
existing `core/redaction.py`, guaranteed process cleanup. See
`docs/BROWSER_SAFETY.md`.

## Validation

`browser scenario validate` (and every execution path, before launching a
browser) checks: missing/duplicate scenario or step ids, missing name,
unknown action, missing required action parameters, invalid/missing
selector, missing assertion parameters, malformed `value_env` reference,
and out-of-range timeouts. A validation failure never results in browser
execution.

## What this is not

Not AI-generated tests, not an autonomous browser agent, not automatic
test generation from static analysis evidence (a detected button/form is
never turned into a scenario step automatically), not visual regression,
not accessibility/security scanning. See `skill.md`/`ROADMAP.md` for what
remains explicitly out of scope.
