"""Functional Health: aggregate Phase 3's `RunResult` — never recompute
what Phase 3 already measured (Phase 5 brief §8/§9).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding
from universal_test.assessment.rules import execution_health_status


def assess_functional_health(
    run_result: RunResult | None, generated_count: int, not_run_reason: str | None,
) -> AssessmentCategory:
    if run_result is None:
        return AssessmentCategory(
            name="Functional Health", status=AssessmentStatus.NOT_ASSESSED,
            summary="functional testing was not executed",
            reason=not_run_reason or "no execution target was provided",
        )

    counts = run_result.summary
    passed, failed, error = counts.get("passed", 0), counts.get("failed", 0), counts.get("error", 0)
    skipped, unknown = counts.get("skipped", 0), counts.get("unknown", 0)
    executed = passed + failed + error

    status = execution_health_status(total_attempted=executed, total_transport_failed=error, total_check_failed=failed)

    findings: list[AssessmentFinding] = []
    if failed:
        findings.append(AssessmentFinding(
            id="FUNC-FAILED", category="Functional Health", status=AssessmentStatus.WARNING,
            severity=Severity.MEDIUM, confidence=0.9,
            title=f"{failed} functional test(s) failed",
            description=f"{failed} of {executed} executed functional test(s) failed their assertions.",
            evidence=[Evidence("functional_summary", {"passed": passed, "failed": failed, "error": error})],
            recommendation="Review each failed test's assertion evidence. Confirm whether the "
                            "behavior is a genuine defect or an outdated expectation.",
        ))
    if error:
        severity = Severity.HIGH if error == executed else Severity.MEDIUM
        findings.append(AssessmentFinding(
            id="FUNC-ERROR", category="Functional Health", status=AssessmentStatus.WARNING,
            severity=severity, confidence=0.9,
            title=f"{error} functional test(s) errored",
            description=f"{error} of {executed} executed functional test(s) could not complete "
                         f"(connection/timeout/transport failure rather than an assertion mismatch).",
            evidence=[Evidence("functional_summary", {"passed": passed, "failed": failed, "error": error})],
            recommendation="Confirm the target is reachable and responsive; a total transport "
                            "failure usually means the target URL, port, or network path is wrong.",
        ))

    summary = (
        f"Generated: {generated_count}, Executed: {executed}, Passed: {passed}, "
        f"Failed: {failed}, Skipped: {skipped}, Unknown: {unknown}"
    )
    evidence = [Evidence("functional_counts", {
        "generated": generated_count, "executed": executed, "passed": passed,
        "failed": failed, "skipped": skipped, "unknown": unknown,
    })]
    return AssessmentCategory(name="Functional Health", status=status, summary=summary, findings=findings, evidence=evidence)
