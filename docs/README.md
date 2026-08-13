# docs/

Additional documentation beyond the top-level planning docs
(`SPECIFICATION.md`, `ARCHITECTURE.md`, `ROADMAP.md`) goes here as it becomes
necessary — e.g. per-adapter guides once adapters exist (Phase 3+).

- `V1_HARDENING_AUDIT.md` — the pre-V1.0-freeze architecture/safety/secret-
  leakage/CLI-contract/dependency/dead-code audit across all of Phase 1-8,
  including the two Critical/High findings it found and fixed.
- `V1_FREEZE.md` — the definitive, frozen statement of what V1.0 promises:
  supported capabilities, non-goals, CLI contract, exit-code contract,
  configuration contract, report schema, safety guarantees, and known
  limitations. Treat any future change contradicting it as a breaking
  change, not a silent behavior shift.
- `V1_RELEASE_CHECKLIST.md` — every V1.0 release-engineering item
  (version freeze, build, clean-install, E2E smoke test, package-content
  audit, documentation) with its actual verified result.
- `V1_RELEASE.md` — the V1.0 release manifest: version, test count,
  artifacts, supported/optional capabilities, safety guarantees.
- `POST_V1_BACKLOG.md` — candidate post-V1 directions (AI integration,
  security scanning, etc.) recorded for future reference — not a roadmap,
  not a commitment, nothing here is scheduled. The browser adapter
  originally listed here was implemented in Phase 9.
- `FRONTEND_ANALYSIS.md` — static frontend/web-application discovery and
  testability assessment (Phase 8.5): framework/build-tool/test-framework
  detection, static-site support, bounded route/component/form evidence.
  Discovery only — see `BROWSER_TESTING.md` for actual execution.
- `BROWSER_TESTING.md` — browser/UI functional testing (Phase 9):
  installation, CLI/GUI usage, supported actions/assertions/selectors,
  failure classification, limitations.
- `BROWSER_SAFETY.md` — the browser adapter's safety model: target policy,
  isolation, no credential guessing, no auto-granted permissions, no
  arbitrary JS execution, redaction, timeouts, process cleanup.
- `WEB_SCENARIOS.md` — explicit, repeatable multi-step Web workflows
  (Phase 11): scenario file format, secret-safe `value_env`, supported
  actions/assertions, validation, timeout hierarchy, CLI/GUI usage. Not a
  new test engine — every step reuses the Browser Adapter above.
