# V1.0 Freeze

Frozen after the V1 Hardening / Architecture / Safety Audit (`docs
/V1_HARDENING_AUDIT.md`), covering everything built across Phases 1-8. This
document is the definitive statement of what V1 promises — treat any
future change that contradicts it as a breaking change requiring an
explicit version bump and migration note, not a silent behavior shift.

## V1 supported capabilities

- **Discovery** (`universal-test scan`): read-only detection of language,
  project type, build system, framework, infrastructure/CI evidence,
  database evidence, API evidence (OpenAPI/Swagger/GraphQL/REST-routing),
  test framework, and secret *patterns* (never values) — every finding
  carries `confidence` + `evidence`, never a bare assertion.
- **REST/OpenAPI functional testing** (`universal-test test`): OpenAPI 3.x
  parsing, conservative positive/negative test generation, HTTP execution,
  env-var-only auth, full JSON Schema validation, dry-run, multi-spec
  safety.
- **Performance testing** (`universal-test performance`): bounded-
  concurrency load generation, documented percentiles, error
  classification, independent threshold evaluation, hard safety ceilings,
  interactive confirmation (or `--yes`).
- **Read-only database assessment** (`universal-test database`): SQL
  Server, PostgreSQL, MySQL, SQLite — schema/table/view/column/key/index
  metadata and safe row-count estimates only. No arbitrary SQL execution
  capability exists in the codebase.
- **Unified assessment** (`universal-test assess`): aggregates the above
  into one evidence-based `PASS/WARNING/FAIL/UNKNOWN` result per category
  plus an overall status, with coverage and an explicit Unknown/Not-
  Assessed section.
- **Baseline / regression** (`universal-test baseline save|compare`,
  `assess --baseline`): versioned, immutable baseline snapshots; per-
  test-ID functional regression; direction-aware, tolerance-based
  performance regression; informational (never failing) database/
  discovery schema-change detection; assessment-category-transition
  severity rules.
- **CI Quality Gate** (`assess --ci --yes`): deterministic, configurable
  `fail_on`/`warn_on` policy; stable `0/1/2/3` exit-code contract; CI
  environment detection (informational only); bounded, narrow retry;
  GitHub Actions/GitLab CI/Jenkins starting-point templates.
- **Reporting**: `report.json`/`report.md`/`report.html`, offline-safe,
  schema-versioned, deterministic, secret-redacted.

## V1 non-goals

Explicitly **not** V1 capabilities — do not describe them as such in any
documentation, and treat a request to add them as a new, separately-scoped
phase, not a bug fix:

- Not a security scanner or vulnerability detector.
- Not a replacement for QA engineers or penetration testers.
- Not a browser/UI automation framework.
- Not an autonomous or AI-driven testing agent.
- Not a fuzzing framework.
- Not a CI/CD pipeline runner, deployment tool, or branch-protection
  manager — it produces an exit code and a report; wiring that into a
  provider's branch protection is the adopting project's own
  responsibility.
- Not a load-testing tool for arbitrary production traffic generation
  beyond its own conservative, safety-ceilinged performance profiles.

## CLI contract

Eight implemented subcommands: `scan`, `test`, `performance`, `database`,
`assess`, `baseline save`, `baseline compare`. `report`/`run` are honest
routing stubs (each names the phase that implements it; `assess` already
covers `report`'s intended output).

Every subcommand shares `--config`/`--output`/`--format`/`--verbose`
/`--adapter`/`--target`/`--dry-run`/`--safe-mode`. `test`/`performance`
/`assess`/`baseline save`/`baseline compare` share the same auth flags
(`--bearer-token-env` etc.) and, where applicable, the same performance/
database flags — one shared flag-adding function per group, never a
redefinition per subcommand. `assess` alone gets `--ci` and `--baseline`
(optional); `baseline compare` gets `--baseline` (required).

**Windows console compatibility**: no `§` or em dash in any string that
can reach printed CLI output (`--help` text, log/error messages, or
finding/report text rendered without `--output`) — a plain ASCII hyphen is
used instead everywhere. Enforced going forward by
`tests/test_windows_console_compatibility.py`.

## Exit code contract (assess only)

```
0 = Quality Gate passed (including a WARNING-level result — a warning never blocks a build)
1 = Quality Gate failed (a configured fail_on rule matched)
2 = Configuration/CLI error (bad --format, unreadable path, invalid/incompatible --baseline)
3 = Infrastructure/execution error (target completely unreachable, including a total-wipeout timeout)
```

A completely unreachable target is `3`, not `1`, unless a project
explicitly opts that signal into its own `fail_on`/`warn_on` policy. Every
other subcommand (`scan`/`test`/`performance`/`database`/`baseline
save`/`baseline compare`) keeps its pre-existing `0`(success)/`2`(error)
convention — the full four-value contract is `assess`-specific by design
(see `ARCHITECTURE.md` §15 assumption 31).

## Configuration contract

`universal-test.yaml` sections: `project`, `assessment`, `functional`,
`performance` (incl. `thresholds`), `database`, `security`, `ai`,
`regression` (incl. `performance` tolerances), `quality_gate` (`fail_on`
/`warn_on`), `ci` (`retry.count`, hard-capped at 2). Missing file, empty
file, empty mapping, and a section present-but-`null` all fall back to
safe defaults. Dict-valued fields (`performance.thresholds`,
`regression.performance`, `quality_gate.fail_on`/`warn_on`) merge partial
overrides over their defaults rather than replacing the whole field —
overriding one key never silently drops the others. Unknown top-level
sections and unknown keys within a known section are ignored, not fatal.
A malformed `quality_gate` policy shape raises `ConfigurationError`
immediately, not a later crash.

## Report schema

`report.json`: `schema_version: "1.0"`, deterministic (`generated_at`/
`discovery.scanned_at` timestamps aside), contains `discovery`/
`functional`/`performance`/`database`/`regression`/`quality_gate`/
`assessment`/`findings`/`coverage`/`unassessed`/`recommendations`
/`limitations`/`warnings`. `baseline.json`: its own independent
`schema_version: "1.0"` (`regression/models.py`) — an unrecognized version
is refused outright by `load_baseline()`, never partially parsed. Neither
file, nor `report.md`/`report.html`, can contain a raw password, token,
API key, cookie, Authorization header, or connection-string credential —
enforced by `core/redaction.py` and verified end-to-end against real HTTP
responses.

## Safety guarantees

- No network request is ever sent without an explicit `--target`.
- No database connection is ever attempted without an explicit
  `--database-profile`, and that profile must set `readonly: true`
  verbatim.
- No arbitrary SQL execution capability exists anywhere in the codebase.
- No repository script (`setup.py`, `package.json` scripts, `Makefile`,
  `Dockerfile`, CI config commands) is ever executed by discovery or any
  other command — the only subprocess call in the entire codebase is a
  read-only `git rev-parse`/`git status --porcelain`.
- `--ci` and CI-environment detection never authorize network traffic or
  relax any safety gate by themselves — `--yes` is always required
  separately for real traffic.
- A saved baseline (`baseline.json`) is immutable — `baseline compare` and
  `assess --baseline` only ever read it; nothing in the codebase writes to
  a baseline file except `baseline save`, and only to the caller's
  explicit `--output` path.
- Bounded, narrow CI retry never retries a genuine assertion/threshold
  failure — only a total transport wipeout.

## Known limitations

- Database regression/discovery-change detection is always informational
  (`INFO` severity) with no "baseline policy" concept yet to escalate it —
  intentionally deferred, shape not yet specified by any brief.
- No historical/multi-baseline trend tracking — one baseline compared
  against one current run at a time.
- No numeric quality score anywhere — every status is one of
  `PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED` (or the Quality Gate's
  `PASS/WARNING/FAIL/ERROR`), by design.
- No AI-assisted analysis or explanation anywhere — fully deterministic.
- Only SQLite has live-database integration tests in the automated suite;
  SQL Server/PostgreSQL/MySQL are covered by missing-driver-handling tests
  and code review against the same driver contract, not a live server (no
  Docker dependency for the general test suite, per design).
- CI provider templates are structurally validated only, never run
  against a live GitHub Actions/GitLab CI/Jenkins instance.
- No load/stress testing of the tool's own pipeline against a very large
  (tens-of-thousands-of-files) repository.

## Deferred features (post-V1)

Explicitly not started, per every phase brief's stop condition and this
audit's own scope: browser/UI adapter, AI integration, security scanner,
blockchain adapter, GraphQL/gRPC adapters, distributed testing, further
project/technology adapters (.NET/Node/Python-specific), CI/CD pipeline
execution (as opposed to gate evaluation), automatic branch-protection
management, historical baseline trend tracking, a "baseline policy"
concept for database/discovery schema-change severity, and a numeric
quality score.
