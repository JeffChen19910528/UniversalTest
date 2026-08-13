"""Web Scenarios health category (Phase 11 spec §37-§38).

Aggregates a list of `ScenarioResult` (one run may execute several
explicitly-selected scenarios) -- never re-executes anything. Mirrors
`assessment/browser_assessment.py`'s shape exactly: `NOT_ASSESSED` when no
scenario was requested, otherwise driven by the same
`execution_health_status()` rule Functional Health/Performance/Browser
Testing already share, so a total wipeout (every scenario errored) reads
`FAIL` while a genuine assertion failure reads `WARNING` -- never silently
turned into `PASS` (spec §38).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding
from universal_test.assessment.rules import execution_health_status

CATEGORY_NAME = "Web Scenarios"


def assess_scenario_health(scenario_results: list | None, not_run_reason: str | None) -> AssessmentCategory:
    if not scenario_results:
        return AssessmentCategory(
            name=CATEGORY_NAME, status=AssessmentStatus.NOT_ASSESSED,
            summary="no explicit Web Scenario was executed",
            reason=not_run_reason or "no scenario was requested",
        )

    executed = [r for r in scenario_results if r.status != "not_assessed"]
    not_assessed = [r for r in scenario_results if r.status == "not_assessed"]
    if not executed:
        reasons = "; ".join(r.not_assessed_reason or "" for r in not_assessed if r.not_assessed_reason)
        return AssessmentCategory(
            name=CATEGORY_NAME, status=AssessmentStatus.NOT_ASSESSED,
            summary="no explicit Web Scenario was executed",
            reason=reasons or "no scenario was requested",
        )

    passed = sum(1 for r in executed if r.status == "pass")
    failed = sum(1 for r in executed if r.status == "fail")
    errored = sum(1 for r in executed if r.status == "error")
    total = len(executed)

    status = execution_health_status(total_attempted=total, total_transport_failed=errored, total_check_failed=failed)

    findings: list[AssessmentFinding] = []
    for result in executed:
        if result.status == "fail":
            findings.append(AssessmentFinding(
                id=f"SCENARIO-FAILED-{result.scenario_id}", category=CATEGORY_NAME, status=AssessmentStatus.WARNING,
                severity=Severity.MEDIUM, confidence=0.9,
                title=f"Scenario {result.scenario_name!r} failed",
                description=f"{result.failed_steps} of {result.step_count} step(s) failed "
                             f"({result.passed_steps} passed, {result.skipped_steps} skipped after the failure).",
                evidence=[Evidence("scenario_summary", {
                    "scenario_id": result.scenario_id, "passed_steps": result.passed_steps,
                    "failed_steps": result.failed_steps, "skipped_steps": result.skipped_steps,
                })],
                recommendation="Open the scenario's step-by-step evidence to confirm whether this "
                                "is a genuine UI defect or an outdated scenario expectation.",
                classification=FindingClassification.DEFECT,
            ))
        elif result.status == "error":
            findings.append(AssessmentFinding(
                id=f"SCENARIO-ERROR-{result.scenario_id}", category=CATEGORY_NAME, status=AssessmentStatus.WARNING,
                severity=Severity.HIGH if errored == total else Severity.MEDIUM, confidence=0.9,
                title=f"Scenario {result.scenario_name!r} could not complete",
                description="Target/selector/timeout/browser-infrastructure failure -- not necessarily "
                             "an application defect.",
                evidence=[Evidence("scenario_summary", {
                    "scenario_id": result.scenario_id, "passed_steps": result.passed_steps,
                    "error_steps": result.error_steps,
                })],
                recommendation="Confirm the target is reachable and the scenario's selectors still "
                                "match the current UI before treating this as a defect.",
                classification=FindingClassification.EXECUTION_FAILURE,
            ))

    summary = f"{total} scenario(s) executed: {passed} passed, {failed} failed, {errored} error"
    if not_assessed:
        summary += f", {len(not_assessed)} not assessed"
    evidence = [Evidence("scenario_counts", {
        "total": total, "passed": passed, "failed": failed, "error": errored,
        "not_assessed": len(not_assessed),
        "scenario_ids": [r.scenario_id for r in scenario_results],
    })]
    return AssessmentCategory(name=CATEGORY_NAME, status=status, summary=summary, findings=findings, evidence=evidence)
