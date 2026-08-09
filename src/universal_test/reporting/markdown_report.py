"""Human-readable Markdown report, structured per Phase 5 brief §15."""

from __future__ import annotations

from universal_test.reporting.report_bundle import AssessReportBundle


def _status_badge(status_value: str) -> str:
    return status_value.upper()


def to_markdown(bundle: AssessReportBundle) -> str:
    a = bundle.assessment
    model = bundle.model
    lines: list[str] = []

    lines += ["# Universal Project Assessment", ""]

    # Executive Summary
    lines += ["## Executive Summary", ""]
    lines += [f"- **Overall Status: {_status_badge(a.overall_status.value)}**"]
    lines += [f"- Project: `{a.project_path}`"]
    lines += [f"- Target: `{a.target}`" if a.target else "- Target: _not provided_"]
    lines += [f"- Generated: {a.generated_at}"]
    lines += [""]
    lines += ["| Category | Status |", "|---|---|"]
    for c in a.categories:
        lines.append(f"| {c.name} | {_status_badge(c.status.value)} |")
    lines.append("")

    # Quality Gate (Phase 8) — always present in 'assess' output, deterministic default policy
    lines += ["## Quality Gate", ""]
    if bundle.quality_gate is None:
        lines.append("_Quality Gate was not evaluated._")
    else:
        qg = bundle.quality_gate
        lines.append(f"**{_status_badge(qg.status.value)}** (exit code {qg.exit_code})")
        if qg.reason:
            lines.append(f"\n> Reason: {qg.reason}")
        lines.append("")
        if qg.findings:
            lines.append("| Rule | Level | Title |")
            lines.append("|---|---|---|")
            for f in qg.findings:
                lines.append(f"| {f.rule} | {f.level.upper()} | {f.title} |")
        else:
            lines.append("_No Quality Gate findings._")
    lines.append("")

    # Project Discovery
    lines += ["## Project Discovery", ""]
    discovery_cat = next(c for c in a.categories if c.name == "Project Discovery")
    build_cat = next(c for c in a.categories if c.name == "Build / Project Health")
    lines += [f"**{discovery_cat.name}**: {_status_badge(discovery_cat.status.value)} - {discovery_cat.summary}"]
    if discovery_cat.reason:
        lines.append(f"> Reason: {discovery_cat.reason}")
    lines += ["", f"**{build_cat.name}**: {_status_badge(build_cat.status.value)} - {build_cat.summary}", ""]

    # Technology Detection (raw discovery data, not assessment judgement)
    lines += ["## Technology Detection", ""]
    lines += ["| Kind | Name | Confidence |", "|---|---|---|"]
    for lang in model.languages:
        lines.append(f"| Language | {lang.name} | {lang.confidence.value} |")
    for fw in model.frameworks:
        lines.append(f"| Framework | {fw.name} | {fw.confidence.value} |")
    for db in model.databases:
        lines.append(f"| Database | {db.name} | {db.confidence.value} |")
    for infra in model.infrastructure:
        lines.append(f"| Infrastructure | {infra.name} | {infra.confidence.value} |")
    if not (model.languages or model.frameworks or model.databases or model.infrastructure):
        lines.append("| _(none detected)_ | | |")
    lines.append("")

    # Testability
    testability_cat = next(c for c in a.categories if c.name == "Testability")
    lines += ["## Testability", ""]
    lines += [f"**Status: {_status_badge(testability_cat.status.value)}**", ""]
    signals = testability_cat.evidence[0].data if testability_cat.evidence else {}
    for name, value in signals.items():
        lines.append(f"- {name}: {value}")
    lines.append("")

    # Functional Testing
    functional_cat = next(c for c in a.categories if c.name == "Functional Health")
    lines += ["## Functional Testing", ""]
    lines += [f"**Status: {_status_badge(functional_cat.status.value)}**", ""]
    lines += [functional_cat.summary]
    if functional_cat.reason:
        lines.append(f"\n> Reason: {functional_cat.reason}")
    lines.append("")

    # Performance
    performance_cat = next(c for c in a.categories if c.name == "Performance")
    lines += ["## Performance", ""]
    lines += [f"**Status: {_status_badge(performance_cat.status.value)}**", ""]
    lines += [performance_cat.summary]
    if performance_cat.reason:
        lines.append(f"\n> Reason: {performance_cat.reason}")
    if bundle.perf_result:
        lines.append("")
        lines.append("| Concurrency | Total | Failed | Error % | P95 (ms) |")
        lines.append("|---|---|---|---|---|")
        for level in bundle.perf_result.levels:
            p95 = f"{level.metrics.latency.p95_ms:.1f}" if level.metrics.latency else "N/A"
            lines.append(
                f"| {level.concurrency} | {level.metrics.total_requests} | {level.metrics.failed_requests} | "
                f"{level.metrics.error_rate_percent:.2f} | {p95} |"
            )
    lines.append("")

    # Database
    database_cat = next(c for c in a.categories if c.name == "Database Health")
    lines += ["## Database", ""]
    lines += [f"**Status: {_status_badge(database_cat.status.value)}**", ""]
    lines += [database_cat.summary]
    if database_cat.reason:
        lines.append(f"\n> Reason: {database_cat.reason}")
    if bundle.database_result and bundle.database_result.info:
        info = bundle.database_result.info
        lines.append("")
        lines.append("| Schema | Table | Columns | Primary Key | Foreign Keys | Indexes | Row Count |")
        lines.append("|---|---|---|---|---|---|---|")
        for schema in info.schemas:
            for table in schema.tables:
                pk = ", ".join(table.primary_key.columns) if table.primary_key else "_none_"
                row_count = "N/A" if not table.row_count or table.row_count.value is None else str(table.row_count.value)
                lines.append(
                    f"| {schema.name} | {table.name} | {len(table.columns)} | {pk} | "
                    f"{len(table.foreign_keys)} | {len(table.indexes)} | {row_count} |"
                )
    lines.append("")

    # Regression (Phase 7 — only present when --baseline was given)
    lines += ["## Regression", ""]
    if bundle.regression is None:
        lines.append("_No baseline was provided; regression comparison was not performed._")
    else:
        r = bundle.regression
        lines.append(f"**Status: {_status_badge(r.status.value)}**")
        lines.append("")
        lines.append(f"- Baseline: {r.baseline_meta['generated_at']} (tool {r.baseline_meta['tool_version']})")
        lines.append(f"- Current: {r.current_meta['generated_at']} (tool {r.current_meta['tool_version']})")
        lines.append("")
        for category in r.categories:
            lines.append(f"### {category.name}")
            lines.append("")
            lines.append(f"**{_status_badge(category.status.value)}** - {category.summary}")
            if category.reason:
                lines.append(f"\n> Reason: {category.reason}")
            lines.append("")
            for finding in category.findings:
                lines.append(f"- [{finding.severity.value.upper()}] {finding.title}")
            lines.append("")
        if r.warnings:
            lines.append("**Warnings:**")
            for w in r.warnings:
                lines.append(f"- {w}")
            lines.append("")
    lines.append("")

    # Findings
    lines += ["## Findings", ""]
    if not a.findings:
        lines.append("_No findings were raised._")
    else:
        for f in a.findings:
            lines.append(f"### [{f.severity.value.upper()}] {f.title}")
            lines.append(f"- Category: {f.category}")
            lines.append(f"- Status: {_status_badge(f.status.value)}")
            lines.append(f"- Confidence: {f.confidence}")
            lines.append(f"- {f.description}")
            for ev in f.evidence:
                pairs = ", ".join(f"{k}: {v}" for k, v in ev.data.items())
                lines.append(f"- Evidence ({ev.type}): {pairs}")
            if f.recommendation:
                lines.append(f"- Recommendation: {f.recommendation}")
            lines.append("")
    lines.append("")

    # Recommendations
    lines += ["## Recommendations", ""]
    if not a.recommendations:
        lines.append("_No recommendations._")
    else:
        for r in a.recommendations:
            lines.append(f"- {r}")
    lines.append("")

    # Coverage
    lines += ["## Coverage", ""]
    lines += ["| Area | Coverage | Reason |", "|---|---|---|"]
    for item in a.coverage:
        percent = f"{item.percent:.0f}%" if item.percent is not None else "N/A"
        lines.append(f"| {item.name} | {percent} | {item.reason or ''} |")
    lines.append("")

    # Unknown / Not Assessed
    lines += ["## Unknown / Not Assessed", ""]
    if not a.unassessed:
        lines.append("_Nothing outstanding._")
    else:
        for i, u in enumerate(a.unassessed, start=1):
            lines.append(f"{i}. {u.name}")
            lines.append(f"   Reason: {u.reason}")
    lines.append("")

    # Limitations
    lines += ["## Limitations", ""]
    for lim in a.limitations:
        lines.append(f"- {lim}")
    lines.append("")

    # Execution Information
    lines += ["## Execution Information", ""]
    lines += [f"- Tool version: {a.tool_version}"]
    lines += [f"- Schema version: {a.schema_version}"]
    lines += [f"- Run timestamp: {a.generated_at}"]
    if a.warnings:
        lines.append("- Warnings:")
        for w in a.warnings:
            lines.append(f"  - {w}")

    return "\n".join(lines)
