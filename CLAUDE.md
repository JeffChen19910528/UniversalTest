# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository currently contains only `skill.md` — a specification document ("Universal Project Assessment Framework — Development Skill"). No implementation exists yet: no source code, no build files, no `package.json`/`.csproj`/`pyproject.toml`, no README, no `SPECIFICATION.md`/`ARCHITECTURE.md`/`ROADMAP.md`/`PROGRESS.md`/`CHANGELOG.md`.

**Treat `skill.md` as the development constitution for this project.** Read it in full before doing any planning or implementation work — it defines the product vision, architecture boundaries, and non-negotiable process rules for everything built here.

## What this project is

A project-agnostic CLI tool (`universal-test`) that, given an unfamiliar or a user's own software project, performs discovery, generates conservative functional/performance tests, executes them safely, and produces an evidence-based initial quality assessment (JSON/Markdown/HTML reports). It is explicitly **not** a security scanner, QA replacement, or correctness guarantee — see `skill.md` §29.

## Required workflow before implementing anything

Per `skill.md` §32, the correct first move in this repo is **not** to start implementing the framework. The sequence is:

1. Inspect the repository to confirm no project structure exists yet (already true as of this writing).
2. Create/update planning docs: `SPECIFICATION.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `PROGRESS.md`, `CHANGELOG.md`, `README.md`.
3. Convert `skill.md`'s requirements into a concrete implementation plan — finalize architecture and the Phase 1 Core spec, pick technology choices, define core domain models/interfaces, and define the initial test strategy.
4. Stop after planning docs are produced and report the proposed architecture plus any assumptions needing approval. Do not jump ahead to Phase 2+ (Discovery, REST Adapter, etc.) without that checkpoint.

Once planning docs exist, follow `skill.md` §23's phase order (Phase 0 Repo init → Phase 1 Core → Phase 2 Discovery → Phase 3 REST Adapter → Phase 4 Performance → Phase 5 Reports → Phase 6 SQL Adapter → Phase 7 Browser Adapter → Phase 8 .NET/Node/Python adapters → Phase 9 AI integration). Work incrementally; do not attempt the entire platform in one pass.

## Core architecture (from skill.md §5)

The mandated separation is **Universal Core + Project Adapters + Explicit Evidence**. Core must stay independent of any specific language, framework, database, or cloud platform — technology-specific logic belongs only in adapters.

```
src/
  core/          domain models, test engine, assertions, orchestration, configuration
  discovery/     filesystem, language, framework, service, API, database detection
  adapters/      rest, graphql, browser, database, docker, dotnet, node, python, blockchain
  testing/       functional, performance, regression, reliability
  assessment/    scoring, findings, recommendations
  reporting/     json, html, markdown
  cli/
tests/
docs/
examples/
plugins/
schemas/
reports/
```

Adapter priority order (skill.md §15): REST/OpenAPI first, then SQL (read-only), Browser (Playwright preferred), Docker, .NET, Node/Python. Each adapter exposes `detect() / describe() / discover() / generate_tests() / execute() / collect_metrics()` and declares its capabilities.

## Non-negotiable rules (from skill.md, do not violate)

- **Never overclaim** (§4.1): distinguish detected / tested / passed / failed / skipped / unknown / inferred / not applicable. "No test found" ≠ "feature is broken"; "no vulnerability detected" ≠ "secure". Report `UNKNOWN` / `NOT_ASSESSED` explicitly rather than defaulting to pass/fail — see §20.
- **Safe by default** (§4.2): never auto-delete files, modify source/production data, run destructive SQL, rotate credentials, change cloud resources, or attack arbitrary remote hosts. Performance tests require an explicit `--target` and explicit configuration.
- **Evidence first** (§4.3): every finding traces to structured evidence, not just a verdict.
- **Secret redaction** (§26): never print passwords, tokens, API keys, connection strings, or private keys into logs, reports, screenshots, exceptions, or generated test cases.
- **No mandatory LLM dependency**: the deterministic engine must work without AI. Any AI-assisted output (test generation, failure explanation, etc.) must be labeled "AI-generated hypothesis," never presented as deterministic fact, and must never bypass the validation/execution layer (§13).
- Keep Core technology-independent; put technology-specific behavior only in adapters.
- Add tests with every non-trivial implementation; run the smallest relevant test suite first, then the full suite; never silently disable failing tests.
- Update `PROGRESS.md` after each meaningful phase and `CHANGELOG.md` for user-visible changes.
- When a requirement is ambiguous, choose the safest implementation and document the assumption rather than guessing destructively.

## End-of-phase reporting

Per `skill.md` §31.20, report at the end of each implementation phase: files changed, functionality added, tests executed, test results, known limitations, and the next recommended phase.
