# Post-V1 Backlog

Candidate directions beyond V1.0, recorded during V1.0 Release Engineering
so ideas surfaced while finalizing the release aren't lost — **not a
roadmap and not a commitment**. Nothing here is scheduled, prioritized
against anything else, or implicitly approved for a future "Phase 9". Each
entry needs its own explicit go-ahead and its own scoped brief before any
implementation starts, per every phase's stop condition so far.

## Browser/UI adapter

- **Purpose**: extend functional testing to browser-driven UIs (page
  discovery, navigation, form interaction, failure screenshots), not just
  REST APIs.
- **Possible value**: covers projects whose primary surface is a web UI
  rather than an API — a large class of projects V1 currently can't test.
- **Major risks**: browser automation is inherently harder to keep
  conservative/safe-by-default than REST testing (arbitrary JS execution
  on the page, file uploads, navigation to unintended URLs); a new,
  heavier dependency (Playwright, per `skill.md` §15's preference); much
  larger safety-review surface than any adapter shipped so far.
- **Dependency**: Playwright (or equivalent) — a new runtime dependency
  class, unlike every V1 adapter's minimal-dependency footprint.
- **Why deferred**: explicitly out of V1 scope per every phase brief's
  stop condition; needs its own dedicated safety design (what "read-only"
  even means for a live UI) before implementation.

## GraphQL adapter

- **Purpose**: functional testing for GraphQL APIs, mirroring the REST
  adapter's conservative test-generation approach.
- **Possible value**: a common API style V1 currently has no functional-
  testing support for (Discovery already detects GraphQL *evidence*,
  Phase 2 — but generates nothing from it).
- **Major risks**: query/mutation generation from a GraphQL schema is a
  different problem than OpenAPI's request-shape generation — schemas can
  express deeply nested, recursive types that need their own conservative-
  generation strategy to avoid either under- or over-generating requests.
- **Dependency**: a GraphQL schema-introspection/query-building library.
- **Why deferred**: no phase has scoped this yet; would need its own
  brief defining conservative generation rules analogous to Phase 3's.

## gRPC adapter

- **Purpose**: functional testing for gRPC services.
- **Possible value**: covers microservice architectures using gRPC
  instead of REST/GraphQL.
- **Major risks**: requires `.proto` discovery/parsing (Discovery has no
  gRPC evidence detection at all yet — a prerequisite, not just an
  adapter); binary protocol testing has a different safety surface than
  text-based HTTP.
- **Dependency**: `grpcio` + protobuf tooling.
- **Why deferred**: no discovery evidence exists yet to build an adapter
  on top of; would need a discovery phase first.

## AI-assisted test generation

- **Purpose**: use an LLM to propose additional test cases beyond what
  conservative, schema-driven generation produces.
- **Possible value**: could catch edge cases conservative generation
  deliberately doesn't attempt (by design — see `SPECIFICATION.md`'s
  "never fabricate a request" principle).
- **Major risks**: directly in tension with V1's core "no AI dependency,
  fully deterministic" principle (`skill.md` §13); any AI-generated test
  must be clearly labeled "AI-generated hypothesis" and must never bypass
  the existing validation/execution layer — a real design constraint, not
  a minor caveat. Non-determinism in what tests get generated would also
  break the "same input -> same report" guarantee V1 relies on throughout.
- **Dependency**: an LLM API (cost, network dependency, availability).
- **Why deferred**: explicitly out of scope for every phase so far
  (`skill.md` §13: "No mandatory LLM dependency"); would need to be
  strictly optional and clearly separated from the deterministic core.

## AI-assisted failure analysis

- **Purpose**: use an LLM to explain *why* a test failed or a regression
  occurred, beyond the structured evidence already in a report.
- **Possible value**: could lower the effort to triage a large report,
  especially for a regression with many findings.
- **Major risks**: same AI-dependency tension as above; a plausible-
  sounding but wrong explanation is arguably worse than no explanation,
  given V1's "never overclaim" principle — a fabricated root-cause guess
  presented next to genuine evidence risks being trusted as fact.
- **Dependency**: an LLM API.
- **Why deferred**: same as AI-assisted test generation — would need its
  own strict labeling/opt-in design before consideration.

## Security assessment

- **Purpose**: detect actual vulnerabilities, not just secret *patterns*
  (which V1 already does, deliberately without confirming exploitability).
- **Possible value**: an adjacent, frequently-requested capability for a
  tool that already discovers APIs and databases.
- **Major risks**: this is the single most explicitly-excluded capability
  in the entire project's constitution (`skill.md` §29, restated in every
  phase brief and in `README.md`'s own disclaimer) — "not a security
  scanner, not a penetration tester." Adding it would fundamentally change
  what this tool claims to be and would need a completely different
  safety model (active probing vs. read-only discovery).
- **Dependency**: a vulnerability-scanning engine or ruleset.
- **Why deferred**: explicit, repeated non-goal — would need a top-level
  scope decision, not just a new phase brief, before any design work.

## Blockchain adapter

- **Purpose**: assess Solidity/smart-contract projects (Discovery already
  detects `.sol` files and Hardhat/Foundry evidence, Phase 2).
- **Possible value**: covers a project category Discovery already
  recognizes but Testing/Assessment currently can't act on.
- **Major risks**: an entirely different execution model (on-chain state,
  gas costs, network selection — mainnet vs. testnet safety is a real
  concern) from every adapter shipped so far.
- **Dependency**: a blockchain client library (e.g. `web3.py`) and access
  to a test network.
- **Why deferred**: no phase has scoped the safety model for this yet
  (what does "read-only" or "safe-by-default" mean against a blockchain?).

## Distributed load testing

- **Purpose**: scale performance testing beyond one machine's concurrency
  ceiling.
- **Possible value**: relevant for load profiles beyond what Phase 4's
  single-process `ThreadPoolExecutor` model supports.
- **Major risks**: a distributed load generator is a fundamentally
  different (and more dangerous) safety surface — coordinating multiple
  machines to hit one target is closer to what an attacker's tooling looks
  like than what a conservative assessment tool should default to; the
  existing hard safety ceilings (`testing/performance/planner.py`) would
  need a completely new design for a multi-node context.
- **Dependency**: a distributed task-queue/coordination system.
- **Why deferred**: explicitly out of scope for every performance-related
  phase so far; V1's single-machine ceilings are a deliberate safety
  choice, not just a current limitation.

## Historical multi-baseline analysis

- **Purpose**: trend analysis across more than one baseline (e.g. "P95 has
  been rising for the last 5 releases"), not just one baseline vs. one
  current run.
- **Possible value**: catches slow-drift regressions a single pairwise
  comparison can't (Phase 7's own explicitly-deferred scope item).
- **Major risks**: needs a storage/retention design for multiple
  baselines over time (where do they live, how many are kept, how are
  they indexed) that doesn't exist yet; trend-detection logic (what counts
  as a meaningful drift vs. noise across N points) is a materially
  different problem than Phase 7's pairwise tolerance comparison.
- **Dependency**: none new, but a real design effort.
- **Why deferred**: explicitly deferred by Phase 7's own brief; no
  shape has been specified for it.

## Additional database engines

- **Purpose**: read-only assessment for databases beyond SQL Server/
  PostgreSQL/MySQL/SQLite (e.g. Oracle, MongoDB, Redis — the latter two
  already have Discovery *evidence* detection, Phase 2, but no adapter).
- **Possible value**: extends Phase 6's adapter to cover databases already
  detected but not assessable.
- **Major risks**: each new engine needs its own driver, its own
  metadata-query mapping to the normalized model
  (`adapters/database/models.py`), and its own safety review (does the
  engine even have a clean read-only connection mode the way SQLite's URI
  trick and the three existing engines' `SET SESSION READ ONLY`-style
  guards do?) — not a mechanical copy-paste of an existing driver.
- **Dependency**: a driver per new engine (e.g. `cx_Oracle`, `pymongo`).
- **Why deferred**: no explicit request yet for a specific additional
  engine; Phase 6's four engines were the brief's own explicit scope.

## Live CI provider validation

- **Purpose**: actually run the three CI templates
  (`examples/ci/{github-actions,gitlab,jenkins}/`) against real GitHub
  Actions/GitLab CI/Jenkins instances, not just structural/YAML validation.
- **Possible value**: catches provider-specific quirks (runner
  environment differences, artifact-upload action version drift, YAML
  edge cases) no amount of local `yaml.safe_load()` checking can find.
- **Major risks**: low risk technically, but requires actual accounts/
  access on each provider and ongoing maintenance as each provider's
  action/plugin ecosystem changes — an operational commitment, not a code
  change.
- **Dependency**: real accounts on each CI provider.
- **Why deferred**: explicitly out of scope for Phase 8 and this V1
  release per both briefs' own instructions not to connect to any
  provider; natural first step for whichever project first adopts a
  template in anger.
