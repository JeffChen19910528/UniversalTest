"""Local-only GUI for Universal Test (Post-V1 Phase 1).

This package is an *additional* interface on top of the existing CLI and
Application Service Layer (`universal_test.application`) — it must never
duplicate Core/Discovery/Testing/Assessment logic (skill.md-derived rule,
GUI brief §2). It only serves a local web UI, translates HTTP requests
into `application.service.run_assessment()` calls, and streams the
resulting progress events back to the browser.
"""
