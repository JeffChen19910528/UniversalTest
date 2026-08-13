"""Browser / Web UI functional testing adapter (Phase 9).

Given an explicit, user-authorized target, launches an isolated Playwright
browser, runs bounded UI actions/assertions declared on a `TestCase`, and
produces `TestResult`/`Finding` evidence through the existing Core
`TestEngine`/`AssertionEngine`/`Orchestrator` -- no second test engine.

Playwright is an optional dependency (`pip install universal-test[browser]`);
this package must remain importable with zero of it installed. Every
module that touches Playwright imports it lazily inside a function, never
at module scope.
"""
