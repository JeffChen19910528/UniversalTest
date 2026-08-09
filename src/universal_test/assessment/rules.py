"""Deterministic overall-status rule (Phase 5 brief §5).

No numeric quality score. `NOT_ASSESSED` categories are informational — a
missing target or disabled performance testing must never push the project
toward FAIL/WARNING/UNKNOWN, and must never count as a silent PASS either;
they are simply excluded from the vote. Priority order, worst to best,
mirrors the brief's own listed order exactly:

    FAIL     > WARNING > UNKNOWN > PASS

- FAIL:    at least one assessed category is FAIL.
- WARNING: no FAIL, but at least one assessed category is WARNING.
- UNKNOWN: no FAIL/WARNING, but at least one assessed category is UNKNOWN,
           OR every category was NOT_ASSESSED (nothing could be judged at all).
- PASS:    every assessed category is PASS (and at least one category was
           actually assessed).

No magic numbers, no weighting, no scoring — see `tests/assessment/
test_rules.py` for the exhaustive case coverage this rule is held to.
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus


def compute_overall_status(category_statuses: list[AssessmentStatus]) -> AssessmentStatus:
    assessed = [s for s in category_statuses if s != AssessmentStatus.NOT_ASSESSED]

    if AssessmentStatus.FAIL in assessed:
        return AssessmentStatus.FAIL
    if AssessmentStatus.WARNING in assessed:
        return AssessmentStatus.WARNING
    if AssessmentStatus.UNKNOWN in assessed:
        return AssessmentStatus.UNKNOWN
    if not assessed:
        return AssessmentStatus.UNKNOWN
    return AssessmentStatus.PASS


def execution_health_status(
    total_attempted: int, total_transport_failed: int, total_check_failed: int,
) -> AssessmentStatus:
    """Shared rule for both Functional Health and Performance categories —
    both answer "did execution work, and did what ran pass its checks?" with
    the same ladder:

    - `UNKNOWN`:  nothing was actually attempted (e.g. everything was
                  skipped/undecidable before a single request went out).
    - `FAIL`:     every attempted request failed at the transport layer
                  (connection refused/timeout/etc.) — the target itself
                  looks unreachable, a stronger signal than "some checks
                  didn't pass."
    - `WARNING`:  at least one transport failure or check failure, but not
                  a total transport wipeout.
    - `PASS`:     everything attempted succeeded and passed its checks.

    A caller with zero relevant activity at all (e.g. no target configured)
    should use `AssessmentStatus.NOT_ASSESSED` directly rather than calling
    this function — this function is only for "we did try to execute
    something."
    """
    if total_attempted == 0:
        return AssessmentStatus.UNKNOWN
    if total_transport_failed == total_attempted:
        return AssessmentStatus.FAIL
    if total_transport_failed > 0 or total_check_failed > 0:
        return AssessmentStatus.WARNING
    return AssessmentStatus.PASS
