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
- `POST_V1_BACKLOG.md` — candidate post-V1 directions (browser adapter,
  AI integration, security scanning, etc.) recorded for future reference —
  not a roadmap, not a commitment, nothing here is scheduled.
