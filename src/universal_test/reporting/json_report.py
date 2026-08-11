"""Unified machine-readable report (Phase 5 brief §14).

Deterministic: the only run-to-run-varying field is `generated_at` in
metadata, which never feeds assessment logic — the same discovery/
functional/performance input always produces the same `assessment`/
`findings`/`coverage` content (Phase 5 brief §17).
"""

from __future__ import annotations

import json

from universal_test.reporting.report_bundle import AssessReportBundle


def to_dict(bundle: AssessReportBundle) -> dict:
    assessment = bundle.assessment
    return {
        "schema_version": assessment.schema_version,
        "tool_version": assessment.tool_version,
        "generated_at": assessment.generated_at,
        "project": {"path": assessment.project_path, "target": assessment.target},
        "coverage": [c.to_dict() for c in assessment.coverage],
        "discovery": bundle.model.to_dict(),
        "functional": {
            "generated": bundle.generated_count,
            "result": bundle.run_result.to_dict() if bundle.run_result else None,
        },
        "performance": bundle.perf_result.to_dict() if bundle.perf_result else None,
        "database": (
            bundle.database_result.info.to_dict()
            if bundle.database_result and bundle.database_result.info else None
        ),
        "regression": bundle.regression.to_dict() if bundle.regression else None,
        "quality_gate": bundle.quality_gate.to_dict() if bundle.quality_gate else None,
        "assessment": {
            "overall_status": assessment.overall_status.value,
            "application_health": assessment.application_health.value,
            "assessment_completeness": assessment.assessment_completeness,
            "categories": [c.to_dict() for c in assessment.categories],
        },
        "findings": [f.to_dict() for f in assessment.findings],
        "recommendations": assessment.recommendations,
        "unassessed": [u.to_dict() for u in assessment.unassessed],
        "limitations": assessment.limitations,
        "warnings": assessment.warnings,
    }


def to_json(bundle: AssessReportBundle) -> str:
    return json.dumps(to_dict(bundle), indent=2, sort_keys=False)
