"""Discovery regression: detected-item changes are always `INFO` (brief §12
— "這是 CHANGE，而不是直接 FAIL"; a detection disappearing is very plausibly a
configuration change, not a defect). Discovery snapshots always exist (`scan`
always runs as part of the pipeline), so this category is never
`NOT_ASSESSED`.
"""

from __future__ import annotations

from universal_test.core.models.enums import Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import ChangeType, DiscoverySnapshot, RegressionCategory, RegressionFinding
from universal_test.regression.rules import status_from_findings

_CATEGORIES = (
    ("languages", "Language"), ("frameworks", "Framework"), ("databases", "Database"),
    ("apis", "API"), ("test_frameworks", "Test framework"), ("infrastructure", "Infrastructure"),
)


def compare_discovery(baseline: DiscoverySnapshot, current: DiscoverySnapshot) -> RegressionCategory:
    findings: list[RegressionFinding] = []

    for attr, label in _CATEGORIES:
        b_items = set(getattr(baseline, attr))
        c_items = set(getattr(current, attr))
        for name in sorted(c_items - b_items):
            findings.append(RegressionFinding(
                id=f"DISCOVERY-ADDED-{attr}-{name}", category="Discovery", change=ChangeType.ADDED,
                severity=Severity.INFO, confidence=0.8, title=f"{label} newly detected: {name}",
                description=f"{label} {name} is detected in the current scan but was not in the baseline.",
                evidence=[Evidence("discovery_item", {"kind": attr, "name": name})],
            ))
        for name in sorted(b_items - c_items):
            findings.append(RegressionFinding(
                id=f"DISCOVERY-REMOVED-{attr}-{name}", category="Discovery", change=ChangeType.REMOVED,
                severity=Severity.INFO, confidence=0.8, title=f"{label} no longer detected: {name}",
                description=(
                    f"{label} {name} was detected in the baseline but not in the current scan - this may "
                    "simply reflect a configuration change, not a regression."
                ),
                evidence=[Evidence("discovery_item", {"kind": attr, "name": name})],
            ))

    status = status_from_findings(findings)  # always PASS: every finding here is INFO severity
    summary = f"{len(findings)} discovery change(s) noted" if findings else "no discovery changes since the baseline"
    return RegressionCategory(name="Discovery", status=status, summary=summary, findings=findings)
