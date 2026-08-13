"""Browser regression: per-test-ID PASS/FAIL/ERROR identity comparison
(Phase 9 spec section 38), mirroring `functional_compare.py` exactly --
same classification ladder, no numeric score. Missing browser data on
either side is `NOT_ASSESSED`, never a regression: an old baseline
predates Phase 9, or browser testing simply wasn't requested for one of
the two runs -- neither means "browser behavior regressed."
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import (
    BrowserSnapshot,
    ChangeType,
    MetricDelta,
    RegressionCategory,
    RegressionFinding,
)
from universal_test.regression.rules import status_from_findings

_GOOD_STATUSES = {"passed"}
_BAD_STATUSES = {"failed", "error"}

_COUNT_METRICS = ("passed", "failed", "error", "skipped", "unknown")


def _classify(baseline_status: str | None, current_status: str | None) -> ChangeType:
    if baseline_status is None:
        return ChangeType.ADDED
    if current_status is None:
        return ChangeType.REMOVED
    if baseline_status == current_status:
        return ChangeType.UNCHANGED
    if baseline_status in _GOOD_STATUSES and current_status in _BAD_STATUSES:
        return ChangeType.REGRESSED
    if baseline_status in _BAD_STATUSES and current_status in _GOOD_STATUSES:
        return ChangeType.IMPROVED
    return ChangeType.CHANGED


def compare_browser(baseline: BrowserSnapshot | None, current: BrowserSnapshot | None) -> RegressionCategory:
    if baseline is None or current is None:
        return RegressionCategory(
            name="Browser",
            status=AssessmentStatus.NOT_ASSESSED,
            summary="browser test results are not available in the baseline and/or the current run",
            reason="baseline and current must both have executed browser tests "
                   "(--browser --target ... --yes) to compare",
        )

    baseline_by_id = {t.id: t.status for t in baseline.tests}
    current_by_id = {t.id: t.status for t in current.tests}
    all_ids = sorted(set(baseline_by_id) | set(current_by_id))

    findings: list[RegressionFinding] = []
    added = removed = improved = unchanged = 0
    for test_id in all_ids:
        b_status = baseline_by_id.get(test_id)
        c_status = current_by_id.get(test_id)
        change = _classify(b_status, c_status)

        if change == ChangeType.ADDED:
            added += 1
        elif change == ChangeType.REMOVED:
            removed += 1
        elif change == ChangeType.UNCHANGED:
            unchanged += 1
        elif change == ChangeType.IMPROVED:
            improved += 1
        elif change == ChangeType.REGRESSED:
            findings.append(RegressionFinding(
                id=f"BROWSER-REGR-{test_id}", category="Browser", change=change,
                severity=Severity.HIGH, confidence=1.0,
                title=f"{test_id} regressed: {b_status} -> {c_status}",
                description=f"Browser test {test_id} passed in the baseline and now {c_status} in the current run.",
                evidence=[Evidence("browser_test", {"id": test_id, "baseline": b_status, "current": c_status})],
                recommendation=f"Investigate why {test_id} started failing since the baseline was captured.",
            ))
        elif change == ChangeType.CHANGED:
            findings.append(RegressionFinding(
                id=f"BROWSER-CHANGED-{test_id}", category="Browser", change=change,
                severity=Severity.MEDIUM, confidence=0.8,
                title=f"{test_id} changed: {b_status} -> {c_status}",
                description=f"Browser test {test_id}'s result changed from {b_status} to {c_status}.",
                evidence=[Evidence("browser_test", {"id": test_id, "baseline": b_status, "current": c_status})],
            ))

    metrics = []
    for key in _COUNT_METRICS:
        b_val = baseline.summary.get(key, 0)
        c_val = current.summary.get(key, 0)
        delta = c_val - b_val
        metrics.append(MetricDelta(
            name=f"{key}_count", baseline_value=b_val, current_value=c_val, direction="neutral",
            change=ChangeType.UNCHANGED if delta == 0 else ChangeType.CHANGED,
            absolute_delta=delta,
        ))

    status = status_from_findings(findings)
    summary = (
        f"{len(all_ids)} browser test ID(s) compared: {added} added, {removed} removed, "
        f"{improved} improved, {unchanged} unchanged, {len(findings)} finding(s) raised"
    )
    return RegressionCategory(name="Browser", status=status, summary=summary, findings=findings, metrics=metrics)
