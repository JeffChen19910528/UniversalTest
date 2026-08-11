"""Configuration Hygiene: initial, non-security-audit-level assessment
(Phase 5 brief §12). A secret *pattern* match is evidence of a pattern, not
a confirmed secret or vulnerability — status is capped at WARNING, never
FAIL, and the matched value is never available to reach this module at all
(`discovery.models.SecretFinding` never stores it — see Phase 2).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.models import ProjectModel
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding

_MAX_SECRET_FINDINGS = 25


def assess_configuration_hygiene(model: ProjectModel) -> AssessmentCategory:
    findings: list[AssessmentFinding] = []

    for i, secret in enumerate(model.secrets[:_MAX_SECRET_FINDINGS]):
        findings.append(AssessmentFinding(
            id=f"CFG-SECRET-{i + 1:03d}", category="Configuration Hygiene",
            status=AssessmentStatus.WARNING, severity=Severity.MEDIUM,
            confidence=0.5 if secret.confidence.value == "inferred" else 0.9,
            title="Potential secret pattern detected",
            description=(
                f"A pattern matching {secret.pattern_type!r} was found in "
                f"{secret.file}:{secret.line}. This is not a confirmed secret and not a "
                f"vulnerability finding - it is a pattern match only."
            ),
            evidence=[Evidence("secret_pattern", {
                "file": secret.file, "line": secret.line, "type": secret.pattern_type, "value": "[REDACTED]",
            })],
            recommendation="Verify whether this is a real credential. If so, rotate it and move it "
                            "to a secret manager or environment variable outside version control.",
            classification=FindingClassification.INFORMATIONAL,
        ))

    truncated = len(model.secrets) > _MAX_SECRET_FINDINGS
    if truncated:
        findings.append(AssessmentFinding(
            id="CFG-SECRET-TRUNCATED", category="Configuration Hygiene",
            status=AssessmentStatus.WARNING, severity=Severity.LOW, confidence=1.0,
            title=f"{len(model.secrets) - _MAX_SECRET_FINDINGS} additional potential secret pattern(s) not shown",
            description=f"Only the first {_MAX_SECRET_FINDINGS} potential-secret findings are listed "
                         f"individually; run `universal-test scan --format json` for the full list.",
            classification=FindingClassification.INFORMATIONAL,
        ))

    if model.secrets:
        status = AssessmentStatus.WARNING
        summary = f"{len(model.secrets)} potential secret pattern(s) detected (values redacted)"
    else:
        status = AssessmentStatus.PASS
        summary = "no secret patterns detected in scanned files"

    return AssessmentCategory(
        name="Configuration Hygiene", status=status, summary=summary, findings=findings, evidence=[],
    )
