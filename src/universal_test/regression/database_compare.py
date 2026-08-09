"""Database (schema metadata) regression: conservative, informational-only
comparison (brief §11 — "不要把 schema change 自動判定成 defect"). Every
finding here is `Severity.INFO`, so `status_from_findings()` can never push
this category past `PASS` — a schema change is something to report, not a
verdict, unless a project explicitly configures a baseline policy (not
built in Phase 7's first version).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import ChangeType, DatabaseSnapshot, RegressionCategory, RegressionFinding
from universal_test.regression.rules import status_from_findings


def compare_database(baseline: DatabaseSnapshot | None, current: DatabaseSnapshot | None) -> RegressionCategory:
    if baseline is None or current is None:
        return RegressionCategory(
            name="Database", status=AssessmentStatus.NOT_ASSESSED,
            summary="database schema is not available in the baseline and/or the current run",
            reason="baseline and current must both have a --database-profile connection to compare",
        )

    b_tables = {t.qualified_name: t for t in baseline.tables}
    c_tables = {t.qualified_name: t for t in current.tables}
    added_tables = sorted(set(c_tables) - set(b_tables))
    removed_tables = sorted(set(b_tables) - set(c_tables))
    common_tables = sorted(set(b_tables) & set(c_tables))

    findings: list[RegressionFinding] = []
    for name in added_tables:
        findings.append(RegressionFinding(
            id=f"DB-TABLE-ADDED-{name}", category="Database", change=ChangeType.ADDED,
            severity=Severity.INFO, confidence=1.0, title=f"Table added: {name}",
            description=f"Table {name} exists in the current schema but not in the baseline.",
            evidence=[Evidence("database_table", {"table": name})],
        ))
    for name in removed_tables:
        findings.append(RegressionFinding(
            id=f"DB-TABLE-REMOVED-{name}", category="Database", change=ChangeType.REMOVED,
            severity=Severity.INFO, confidence=1.0, title=f"Table removed: {name}",
            description=f"Table {name} existed in the baseline but was not found in the current schema.",
            evidence=[Evidence("database_table", {"table": name})],
        ))

    for name in common_tables:
        b_table, c_table = b_tables[name], c_tables[name]
        added_cols = sorted(set(c_table.columns) - set(b_table.columns))
        removed_cols = sorted(set(b_table.columns) - set(c_table.columns))
        if added_cols:
            findings.append(RegressionFinding(
                id=f"DB-COL-ADDED-{name}", category="Database", change=ChangeType.CHANGED,
                severity=Severity.INFO, confidence=1.0,
                title=f"{name}: column(s) added: {', '.join(added_cols)}",
                description=f"Table {name} gained column(s) {', '.join(added_cols)} since the baseline.",
                evidence=[Evidence("database_column", {"table": name, "added": added_cols})],
            ))
        if removed_cols:
            findings.append(RegressionFinding(
                id=f"DB-COL-REMOVED-{name}", category="Database", change=ChangeType.CHANGED,
                severity=Severity.INFO, confidence=1.0,
                title=f"{name}: column(s) removed: {', '.join(removed_cols)}",
                description=f"Table {name} lost column(s) {', '.join(removed_cols)} since the baseline.",
                evidence=[Evidence("database_column", {"table": name, "removed": removed_cols})],
            ))
        if b_table.foreign_key_count != c_table.foreign_key_count:
            findings.append(RegressionFinding(
                id=f"DB-FK-CHANGED-{name}", category="Database", change=ChangeType.CHANGED,
                severity=Severity.INFO, confidence=0.9,
                title=f"{name}: foreign key count changed: {b_table.foreign_key_count} -> {c_table.foreign_key_count}",
                description=f"Table {name}'s foreign key count changed since the baseline.",
                evidence=[Evidence("database_foreign_key", {
                    "table": name, "baseline_count": b_table.foreign_key_count, "current_count": c_table.foreign_key_count,
                })],
            ))
        if b_table.index_count != c_table.index_count:
            findings.append(RegressionFinding(
                id=f"DB-INDEX-CHANGED-{name}", category="Database", change=ChangeType.CHANGED,
                severity=Severity.INFO, confidence=0.9,
                title=f"{name}: index count changed: {b_table.index_count} -> {c_table.index_count}",
                description=f"Table {name}'s index count changed since the baseline.",
                evidence=[Evidence("database_index", {
                    "table": name, "baseline_count": b_table.index_count, "current_count": c_table.index_count,
                })],
            ))

    status = status_from_findings(findings)  # always PASS: every finding here is INFO severity
    summary = (
        f"{len(common_tables)} table(s) compared, {len(added_tables)} added, {len(removed_tables)} removed, "
        f"{len(findings)} schema change(s) noted"
    )
    return RegressionCategory(name="Database", status=status, summary=summary, findings=findings)
