"""Human-readable Markdown report, structured per Phase 5 brief §15."""

from __future__ import annotations

from universal_test.reporting.report_bundle import AssessReportBundle


def _status_badge(status_value: str) -> str:
    return status_value.upper()


_CLASSIFICATION_LABELS = {
    "defect": "Confirmed defect signal - something that actually executed showed a problem.",
    "testability_gap": "Testability limitation - automated coverage is limited here. This does NOT indicate the application has a defect.",
    "not_assessed": "Not assessed - this could not be fully evaluated.",
    "informational": "Informational - an unconfirmed observation, not a proven issue.",
    "execution_failure": "Execution/connectivity failure - the target could not be reached, distinct from a behavioral defect.",
}


def _classification_label(classification_value: str) -> str:
    return _CLASSIFICATION_LABELS.get(classification_value, classification_value)


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

    # Assessment Summary - a WARNING category does not by itself mean the
    # application is broken (Semantics Hardening brief §10/§11/§29):
    # Application Health only reflects categories driven by something that
    # actually executed against the live project; Testability/Assessment
    # Coverage are separate dimensions, not folded into one status.
    testability_cat_for_summary = next(c for c in a.categories if c.name == "Testability")
    lines += ["## Assessment Summary", ""]
    lines += [
        f"- **Application Health: {_status_badge(a.application_health.value)}** - "
        "reflects only categories driven by something that actually executed "
        "(Functional/Performance/Browser Testing). A `PASS` here means no confirmed defect was "
        "found; it does not mean every capability was tested."
    ]
    lines += [
        f"- **Testability: {_status_badge(testability_cat_for_summary.status.value)}** - "
        "how testable this project currently is (test framework/target/fixture "
        "availability), independent of whether the application itself works."
    ]
    lines += [
        f"- **Assessment Coverage: {a.assessment_completeness.upper()}** - whether every "
        "assessable area was actually assessed this run; see Coverage/Unknown "
        "sections below for what wasn't."
    ]
    lines.append("")

    # Quality Gate (Phase 8) — always present in 'assess' output, deterministic default policy
    lines += ["## Quality Gate", ""]
    if bundle.quality_gate is None:
        lines.append("_Quality Gate was not evaluated._")
    else:
        qg = bundle.quality_gate
        lines.append(f"**{_status_badge(qg.status.value)}** (exit code {qg.exit_code})")
        if qg.status.value == "pass":
            lines.append("> No configured quality-gate rule failed. This does not mean all "
                          "application behavior was tested.")
        elif qg.status.value == "fail":
            lines.append("> A configured quality-gate condition failed. See findings below.")
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

    # Frontend / Web Application
    frontend_cat = next((c for c in a.categories if c.name == "Frontend / Web Application Health"), None)
    lines += ["## Frontend / Web Application", ""]
    if frontend_cat is not None:
        lines += [f"**Status: {_status_badge(frontend_cat.status.value)}**", ""]
        lines += [frontend_cat.summary]
        if frontend_cat.reason:
            lines.append(f"\n> Reason: {frontend_cat.reason}")
    fe = model.frontend
    if fe.detected:
        lines.append("")
        if fe.frontend_type:
            lines.append(f"- **Type:** `{fe.frontend_type.value}`")
        if fe.entry_points:
            lines.append(f"- **Entry point(s):** {', '.join(f'`{e}`' for e in fe.entry_points)}")
        if len(fe.web_roots) > 1:
            lines.append(f"- **Multiple web roots detected:** {', '.join(f'`{r}`' for r in fe.web_roots)}")
        if fe.html_page_count or fe.css_file_count or fe.js_file_count:
            lines.append(
                f"- **HTML pages:** {fe.html_page_count} · **CSS files:** {fe.css_file_count} · "
                f"**JS files:** {fe.js_file_count} (inline CSS blocks: {fe.inline_css_count}, "
                f"inline JS blocks: {fe.inline_js_count})"
            )
        if fe.application_pattern:
            lines.append(
                f"- **Application pattern:** `{fe.application_pattern}` "
                "_(evidence suggests, not confirmed - static analysis cannot verify runtime behavior)_"
            )
        if fe.css_frameworks:
            lines.append(f"- **CSS frameworks:** {', '.join(fe.css_frameworks)}")
        if fe.browser_apis:
            lines.append(f"- **Browser APIs detected:** {', '.join(fe.browser_apis)}")
        if fe.external_resources:
            lines.append(f"- **External resources:** {', '.join(fe.external_resources)}")
        lines.append("")
        lines.append("| Signal | Status |")
        lines.append("|---|---|")
        lines.append(f"| Routes | {fe.routes.status.value} |")
        lines.append(f"| Components | {fe.components.status.value} |")
        lines.append(f"| Forms | {fe.forms.status.value} |")
        lines.append(f"| Interactive UI | {fe.interactive_ui.status.value} |")
        lines.append(f"| API clients | {fe.api_clients.status.value} |")
        lines.append(f"| Responsive design | {fe.responsive.status.value} |")
        lines.append(f"| Authentication UI | {fe.auth_ui.status.value} |")
        lines.append(f"| Content-Security-Policy | {fe.csp.status.value} |")
        lines.append("")
        browser_cat_for_frontend = next((c for c in a.categories if c.name == "Browser Testing"), None)
        if browser_cat_for_frontend is not None and browser_cat_for_frontend.status.value != "not_assessed":
            lines.append(
                f"> **Browser/UI Execution: {_status_badge(browser_cat_for_frontend.status.value)}** - "
                "see the Browser Testing section below for details."
            )
        else:
            reason = browser_cat_for_frontend.reason if browser_cat_for_frontend else "browser testing was not requested"
            lines.append(
                f"> **Browser/UI Execution: NOT_ASSESSED** - {reason}. Frontend detected does "
                "not mean the frontend was functionally tested."
            )
    lines.append("")

    # Browser Testing (Phase 9 spec section 39)
    lines += ["## Browser Testing", ""]
    browser_cat = next((c for c in a.categories if c.name == "Browser Testing"), None)
    if browser_cat is None or browser_cat.status.value == "not_assessed":
        lines.append("**NOT ASSESSED**")
        lines.append("")
        reason = browser_cat.reason if browser_cat else "browser testing was not requested"
        lines.append(f"Browser testing was not requested. Reason: {reason}")
        lines.append("")
        lines.append("Static frontend analysis was completed separately (see Frontend / Web Application above).")
    else:
        lines.append(f"**Status: {_status_badge(browser_cat.status.value)}**")
        lines.append("")
        lines.append(f"- Target: `{bundle.browser_result.target if bundle.browser_result else a.target}`")
        lines.append(f"- Browser: {bundle.browser_result.browser if bundle.browser_result else 'unknown'}")
        lines.append(f"- {browser_cat.summary}")
        if browser_cat.status.value in ("fail", "warning") and any(
            f.classification.value == "execution_failure" for f in browser_cat.findings
        ):
            lines.append("")
            lines.append(
                "> The browser test could not be reliably executed for one or more cases "
                "(target/selector/timeout issue). This does not by itself prove the "
                "application is defective."
            )
        if bundle.browser_result and bundle.browser_result.screenshots:
            lines.append("")
            lines.append("Evidence:")
            for path in bundle.browser_result.screenshots:
                lines.append(f"- screenshot: `{path}`")
    lines.append("")

    # Web Scenarios (Phase 11 spec section 34)
    lines += ["## Web Scenarios", ""]
    scenario_cat = next((c for c in a.categories if c.name == "Web Scenarios"), None)
    if scenario_cat is None or scenario_cat.status.value == "not_assessed":
        lines.append("**NOT ASSESSED**")
        lines.append("")
        reason = scenario_cat.reason if scenario_cat else "no scenario was requested"
        lines.append(f"No explicit Web Scenario was executed. Reason: {reason}")
    else:
        lines.append(f"**Status: {_status_badge(scenario_cat.status.value)}**")
        lines.append("")
        lines.append(f"- {scenario_cat.summary}")
        lines.append("")
        lines.append("| Scenario | Status | Steps (passed/failed/error/skipped) | Duration |")
        lines.append("|---|---|---|---|")
        for result in bundle.scenario_results or []:
            lines.append(
                f"| {result.scenario_name} (`{result.scenario_id}`) | {result.status.upper()} | "
                f"{result.passed_steps}/{result.failed_steps}/{result.error_steps}/{result.skipped_steps} | "
                f"{result.duration_seconds:.2f}s |"
            )
        if any(f.classification.value == "execution_failure" for f in scenario_cat.findings):
            lines.append("")
            lines.append(
                "> A scenario could not be reliably executed for one or more cases "
                "(target/selector/timeout issue). This does not by itself prove the "
                "application is defective."
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
            lines.append(f"- Type: {_classification_label(f.classification.value)}")
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
