"""Browser Testing health category (Phase 9 spec §35-§36).

Aggregates `BrowserRunResult` — never re-executes anything. Three states
must stay distinct (spec §36):

    NOT_ASSESSED -- browser testing was not requested (the common default)
    PASS/WARNING/FAIL -- the configured browser test executed; status is
        driven by `execution_health_status()`, the same rule Functional
        Health/Performance already use, so a total transport wipeout (bad
        target) reads as FAIL while a genuine assertion failure reads as
        WARNING (see `rules.py`'s "WARNING never overclaims to FAIL"
        convention already established for Functional Health, mirrored
        here rather than invented fresh).

`BrowserUnavailableError`/Playwright-missing is folded into NOT_ASSESSED by
`adapters/browser/adapter.py` before this module ever sees it -- "browser
binary missing" must never look like a defect (spec §25/§36).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding
from universal_test.assessment.rules import execution_health_status

CATEGORY_NAME = "Browser Testing"


def assess_browser_health(browser_result, browser_not_run_reason: str | None) -> AssessmentCategory:
    if browser_result is None or not browser_result.executed:
        reason = browser_not_run_reason or (
            browser_result.not_assessed_reason if browser_result else None
        ) or (
            browser_result.no_target_reason if browser_result else None
        ) or "browser testing was not requested"
        return AssessmentCategory(
            name=CATEGORY_NAME, status=AssessmentStatus.NOT_ASSESSED,
            summary="browser/UI testing was not executed", reason=reason,
        )

    run_result = browser_result.run_result
    counts = run_result.summary
    passed, failed, error = counts.get("passed", 0), counts.get("failed", 0), counts.get("error", 0)
    skipped, unknown = counts.get("skipped", 0), counts.get("unknown", 0)
    executed = passed + failed + error

    status = execution_health_status(total_attempted=executed, total_transport_failed=error, total_check_failed=failed)

    findings: list[AssessmentFinding] = []
    if failed:
        findings.append(AssessmentFinding(
            id="BROWSER-FAILED", category=CATEGORY_NAME, status=AssessmentStatus.WARNING,
            severity=Severity.MEDIUM, confidence=0.9,
            title=f"{failed} browser test(s) failed",
            description=f"{failed} of {executed} executed browser test(s) failed an assertion "
                         "(the configured UI behavior did not match expectations).",
            evidence=[Evidence("browser_summary", {"passed": passed, "failed": failed, "error": error})],
            recommendation="Review each failed test's assertion evidence to confirm whether this "
                            "is a genuine UI defect or an outdated expectation.",
            classification=FindingClassification.DEFECT,
        ))
    if error:
        severity = Severity.HIGH if error == executed else Severity.MEDIUM
        findings.append(AssessmentFinding(
            id="BROWSER-ERROR", category=CATEGORY_NAME, status=AssessmentStatus.WARNING,
            severity=severity, confidence=0.9,
            title=f"{error} browser test(s) errored",
            description=f"{error} of {executed} executed browser test(s) could not complete "
                         "(target unreachable, selector, timeout, or browser-infrastructure failure "
                         "-- not necessarily an application defect).",
            evidence=[Evidence("browser_summary", {"passed": passed, "failed": failed, "error": error})],
            recommendation="Confirm the target is reachable and the test's selectors still match "
                            "the current UI before treating this as a defect.",
            classification=FindingClassification.EXECUTION_FAILURE,
        ))

    summary = (
        f"Executed: {executed}, Passed: {passed}, Failed: {failed}, "
        f"Skipped: {skipped}, Unknown: {unknown} (target: {browser_result.target}, browser: {browser_result.browser})"
    )
    evidence = [Evidence("browser_counts", {
        "executed": executed, "passed": passed, "failed": failed,
        "skipped": skipped, "unknown": unknown, "screenshots": len(browser_result.screenshots),
    })]
    return AssessmentCategory(name=CATEGORY_NAME, status=status, summary=summary, findings=findings, evidence=evidence)
