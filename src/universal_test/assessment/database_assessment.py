"""Database Health: aggregate Phase 6's `DatabaseDiscoveryResult` — never
re-connects, never re-queries.

Status is deliberately capped **below `FAIL`** (Phase 6 brief §16): a
missing driver, refused connection, or timeout is an access/environment
problem, not evidence the assessed project's database is broken, so it is
always `NOT_ASSESSED`, never `FAIL`. Likewise, zero foreign keys or a gap in
primary-key coverage is reported as `INFO` evidence, never downgraded to a
defect (brief §13: "不要把「沒有 foreign key」直接判定成 database defect").
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding

_TEST_DB_NAME_HINTS = ("test", "staging", "dev", "sandbox", "demo")


def assess_database_health(result: DatabaseDiscoveryResult | None) -> AssessmentCategory:
    if result is None:
        return AssessmentCategory(
            name="Database Health", status=AssessmentStatus.NOT_ASSESSED,
            summary="database access was not assessed",
            reason="database credentials/access were not explicitly configured",
        )

    if result.info is None:
        return AssessmentCategory(
            name="Database Health", status=AssessmentStatus.NOT_ASSESSED,
            summary=f"could not connect to the configured {result.profile.engine} database",
            reason=result.not_assessed_reason,
            evidence=[Evidence("database_profile", result.profile.to_dict())],
        )

    info = result.info
    total_tables = sum(len(s.tables) for s in info.schemas)
    total_views = sum(len(s.views) for s in info.schemas)
    tables_without_pk = [
        f"{s.name}.{t.name}" for s in info.schemas for t in s.tables if t.primary_key is None
    ]
    total_fks = sum(len(t.foreign_keys) for s in info.schemas for t in s.tables)
    total_indexes = sum(len(t.indexes) for s in info.schemas for t in s.tables)

    findings: list[AssessmentFinding] = []
    if tables_without_pk:
        findings.append(AssessmentFinding(
            id="DB-NO-PK", category="Database Health", status=AssessmentStatus.PASS,
            severity=Severity.INFO, confidence=0.9,
            title=f"{len(tables_without_pk)} table(s) have no detected primary key",
            description=(
                "This is informational, not a defect finding - some tables (e.g. pure "
                "association/log tables) legitimately have no primary key. Tables: "
                + ", ".join(tables_without_pk[:20])
                + (f" (+{len(tables_without_pk) - 20} more)" if len(tables_without_pk) > 20 else "")
            ),
            classification=FindingClassification.INFORMATIONAL,
        ))
    if total_tables > 0 and total_fks == 0:
        findings.append(AssessmentFinding(
            id="DB-NO-FK", category="Database Health", status=AssessmentStatus.PASS,
            severity=Severity.INFO, confidence=0.7,
            title="No foreign key relationships were detected",
            description="This is informational, not a defect finding - the schema may "
                        "legitimately enforce relationships at the application layer instead.",
            classification=FindingClassification.INFORMATIONAL,
        ))
    if info.warnings:
        findings.append(AssessmentFinding(
            id="DB-WARN", category="Database Health", status=AssessmentStatus.WARNING,
            severity=Severity.LOW, confidence=0.8,
            title="Some database metadata could not be fully discovered",
            description="; ".join(info.warnings),
            classification=FindingClassification.NOT_ASSESSED,
        ))

    if total_tables == 0 and total_views == 0:
        status = AssessmentStatus.UNKNOWN
    elif info.warnings:
        status = AssessmentStatus.WARNING
    else:
        status = AssessmentStatus.PASS

    summary = (
        f"Connected to {info.engine.value} ({info.server_version or 'version unknown'}); "
        f"{len(info.schemas)} schema(s), {total_tables} table(s), {total_views} view(s), "
        f"{total_fks} foreign key(s), {total_indexes} index(es)"
    )

    evidence = [
        Evidence("database_profile", result.profile.to_dict()),
        Evidence("database_summary", {
            "schemas": len(info.schemas), "tables": total_tables, "views": total_views,
            "foreign_keys": total_fks, "indexes": total_indexes,
            "tables_without_primary_key": len(tables_without_pk),
        }),
    ]

    return AssessmentCategory(
        name="Database Health", status=status, summary=summary, findings=findings, evidence=evidence,
    )


def database_testability_signal(result: DatabaseDiscoveryResult | None, database_detected_in_repo: bool) -> str:
    """A single coarse signal consumed by `testability_assessment.py`'s
    existing "Database testability" row (Phase 5) — kept coarse there
    deliberately; the detailed breakdown lives in this category instead.
    """
    if result is None:
        return "NOT_ASSESSED" if database_detected_in_repo else "NONE"
    if result.info is None:
        return "NOT_ASSESSED"
    total_tables = sum(len(s.tables) for s in result.info.schemas)
    return "GOOD" if total_tables > 0 else "PARTIAL"


def looks_like_a_test_database(database_name: str | None) -> bool:
    if not database_name:
        return False
    lowered = database_name.lower()
    return any(hint in lowered for hint in _TEST_DB_NAME_HINTS)
