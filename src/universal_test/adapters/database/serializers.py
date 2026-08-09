"""Rendering for `universal-test database` (dry-run plan + discovery result).

Same convention as every other phase's lightweight serializers
(`discovery/serializers.py`, `adapters/rest/serializers.py`,
`testing/performance/serializers.py`) — not the unified Phase 5 report
(that's `reporting/`, which also gets a Database section — see
`reporting/markdown_report.py`/`html_report.py`).
"""

from __future__ import annotations

import json

from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.adapters.database.profile import DatabaseProfile

_OPERATIONS = [
    "connectivity check", "schema discovery", "table metadata", "view metadata",
    "column metadata", "key metadata", "index metadata", "safe row-count estimate",
]


def plan_to_text(profile: DatabaseProfile) -> str:
    lines = ["Database Assessment Plan", "=" * 24, "", "Engine:", profile.engine, ""]
    if profile.engine == "sqlite":
        lines += ["Path:", profile.path or "", ""]
    else:
        lines += ["Host:", profile.host or "", "", "Database:", profile.database or "", ""]
    lines += ["Operations:"]
    lines += [f"- {op}" for op in _OPERATIONS]
    lines += ["", "Mode:", "READ ONLY", ""]
    return "\n".join(lines)


def result_to_text(result: DatabaseDiscoveryResult) -> str:
    if result.info is None:
        return (
            f"Database connection: FAIL\n\n"
            f"Reason:\n{result.not_assessed_reason}\n\n"
            f"Assessment: NOT_ASSESSED"
        )

    info = result.info
    lines = [
        f"Engine: {info.engine.value}",
        f"Server version: {info.server_version or 'unknown'}",
        f"Database: {info.database_name or 'unknown'}",
        "",
    ]
    for schema in info.schemas:
        lines.append(f"Schema: {schema.name}")
        lines.append(f"  Tables: {len(schema.tables)}")
        for table in schema.tables:
            pk = ", ".join(table.primary_key.columns) if table.primary_key else "(none)"
            row_count = "N/A" if not table.row_count or table.row_count.value is None else str(table.row_count.value)
            lines.append(
                f"    - {table.name}: {len(table.columns)} column(s), PK=[{pk}], "
                f"{len(table.foreign_keys)} FK(s), {len(table.indexes)} index(es), rows~={row_count}"
            )
        lines.append(f"  Views: {len(schema.views)}")
        for view in schema.views:
            lines.append(f"    - {view.name}: {len(view.columns)} column(s)")
        lines.append("")

    if info.warnings:
        lines.append("Warnings")
        lines.append("-" * 8)
        for w in info.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def result_to_json(result: DatabaseDiscoveryResult) -> str:
    payload = {
        "profile": result.profile.to_dict(),
        "connected": result.info is not None,
        "not_assessed_reason": result.not_assessed_reason,
        "database": result.info.to_dict() if result.info else None,
    }
    return json.dumps(payload, indent=2)


def result_to_markdown(result: DatabaseDiscoveryResult) -> str:
    lines = ["# Database Assessment", ""]
    lines += [f"- Engine: {result.profile.engine}"]
    if result.info is None:
        lines += ["- Connected: no", "", f"> Reason: {result.not_assessed_reason}"]
        return "\n".join(lines)

    info = result.info
    lines += [
        "- Connected: yes",
        f"- Server version: {info.server_version or 'unknown'}",
        f"- Database: {info.database_name or 'unknown'}",
        "",
        "| Schema | Table | Columns | Primary Key | Foreign Keys | Indexes | Row Count |",
        "|---|---|---|---|---|---|---|",
    ]
    for schema in info.schemas:
        for table in schema.tables:
            pk = ", ".join(table.primary_key.columns) if table.primary_key else "_none_"
            row_count = "N/A" if not table.row_count or table.row_count.value is None else str(table.row_count.value)
            lines.append(
                f"| {schema.name} | {table.name} | {len(table.columns)} | {pk} | "
                f"{len(table.foreign_keys)} | {len(table.indexes)} | {row_count} |"
            )
    lines.append("")
    if info.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in info.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)
