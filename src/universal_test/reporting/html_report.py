"""Offline, static HTML report (Phase 5 brief §16).

No CDN, no external JavaScript, no external CSS — a single self-contained
file that opens directly from disk. Built with plain string templates
rather than adding a templating-engine dependency (`Jinja2` stays deferred
until a later phase actually needs it — see ARCHITECTURE.md). Every piece
of text derived from the scanned project (finding titles/descriptions,
evidence values, file paths) is passed through `html.escape()` before
insertion, since that content is attacker-influenceable input, not
tool-authored text.
"""

from __future__ import annotations

import html

from universal_test.reporting.report_bundle import AssessReportBundle

_STATUS_COLORS = {
    "pass": "#1a7f37", "warning": "#9a6700", "fail": "#cf222e",
    "unknown": "#57606a", "not_assessed": "#57606a",
}


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _status_span(status_value: str) -> str:
    color = _STATUS_COLORS.get(status_value, "#57606a")
    return f'<span style="color:{color};font-weight:600">{_e(status_value.upper())}</span>'


def _evidence_html(evidence) -> str:
    if not evidence:
        return ""
    items = "".join(
        f"<li><strong>{_e(ev.type)}:</strong> "
        + ", ".join(f"{_e(k)}={_e(v)}" for k, v in ev.data.items())
        + "</li>"
        for ev in evidence
    )
    return f"<ul>{items}</ul>"


_CLASSIFICATION_LABELS = {
    "defect": "Confirmed defect signal - something that actually executed showed a problem.",
    "testability_gap": "Testability limitation - automated coverage is limited here. This does NOT indicate the application has a defect.",
    "not_assessed": "Not assessed - this could not be fully evaluated.",
    "informational": "Informational - an unconfirmed observation, not a proven issue.",
    "execution_failure": "Execution/connectivity failure - the target could not be reached, distinct from a behavioral defect.",
}


def _classification_label(classification_value: str) -> str:
    return _CLASSIFICATION_LABELS.get(classification_value, classification_value)


def to_html(bundle: AssessReportBundle) -> str:
    a = bundle.assessment

    category_rows = "\n".join(
        f"<tr><td>{_e(c.name)}</td><td>{_status_span(c.status.value)}</td>"
        f"<td>{_e(c.summary)}</td><td>{_e(c.reason or '')}</td></tr>"
        for c in a.categories
    )

    finding_blocks = "\n".join(
        f'<div class="finding">'
        f'<h3>[{_e(f.severity.value.upper())}] {_e(f.title)}</h3>'
        f'<p><strong>Category:</strong> {_e(f.category)} &middot; '
        f'<strong>Status:</strong> {_status_span(f.status.value)} &middot; '
        f'<strong>Type:</strong> {_e(_classification_label(f.classification.value))} &middot; '
        f'<strong>Confidence:</strong> {_e(f.confidence)}</p>'
        f'<p>{_e(f.description)}</p>'
        + _evidence_html(f.evidence)
        + (f'<p><strong>Recommendation:</strong> {_e(f.recommendation)}</p>' if f.recommendation else "")
        + "</div>"
        for f in a.findings
    ) or "<p><em>No findings were raised.</em></p>"

    testability_cat_for_summary = next(c for c in a.categories if c.name == "Testability")
    assessment_summary_html = (
        f'<p><strong>Application Health:</strong> {_status_span(a.application_health.value)} '
        "- reflects only categories driven by something that actually executed "
        "(Functional/Performance/Browser Testing). A PASS here means no confirmed defect was found; "
        "it does not mean every capability was tested.</p>"
        f'<p><strong>Testability:</strong> {_status_span(testability_cat_for_summary.status.value)} '
        "- how testable this project currently is, independent of whether the "
        "application itself works.</p>"
        f'<p><strong>Assessment Coverage:</strong> {_e(a.assessment_completeness.upper())} '
        "- whether every assessable area was actually assessed this run.</p>"
    )

    coverage_rows = "\n".join(
        f"<tr><td>{_e(item.name)}</td>"
        f"<td>{_e(f'{item.percent:.0f}%') if item.percent is not None else 'N/A'}</td>"
        f"<td>{_e(item.reason or '')}</td></tr>"
        for item in a.coverage
    )

    unassessed_items = "\n".join(
        f"<li><strong>{_e(u.name)}</strong> - {_e(u.reason)}</li>" for u in a.unassessed
    ) or "<li>Nothing outstanding.</li>"

    recommendation_items = "\n".join(f"<li>{_e(r)}</li>" for r in a.recommendations) or "<li>None.</li>"
    limitation_items = "\n".join(f"<li>{_e(lim)}</li>" for lim in a.limitations)

    critical_findings = [f for f in a.findings if f.severity.value in ("critical", "high")]
    critical_html = (
        "\n".join(f"<li>{_e(f.title)}</li>" for f in critical_findings)
        if critical_findings else "<li>None.</li>"
    )

    functional_cat = next(c for c in a.categories if c.name == "Functional Health")
    performance_cat = next(c for c in a.categories if c.name == "Performance")
    database_cat = next(c for c in a.categories if c.name == "Database Health")
    frontend_cat = next((c for c in a.categories if c.name == "Frontend / Web Application Health"), None)
    browser_cat = next((c for c in a.categories if c.name == "Browser Testing"), None)

    if browser_cat is None or browser_cat.status.value == "not_assessed":
        reason = browser_cat.reason if browser_cat else "browser testing was not requested"
        browser_html = (
            "<p><strong>NOT ASSESSED</strong></p>"
            f"<p>Browser testing was not requested. Reason: {_e(reason)}</p>"
            "<p>Static frontend analysis was completed separately (see Frontend / Web Application above).</p>"
        )
        frontend_browser_note = (
            f'<em><strong>Browser/UI Execution: NOT_ASSESSED</strong> - {_e(reason)}. '
            "Frontend detected does not mean the frontend was functionally tested.</em>"
        )
    else:
        target_text = bundle.browser_result.target if bundle.browser_result else a.target
        browser_name = bundle.browser_result.browser if bundle.browser_result else "unknown"
        screenshots_html = ""
        if bundle.browser_result and bundle.browser_result.screenshots:
            screenshots_html = "<ul>" + "".join(
                f"<li>screenshot: <code>{_e(path)}</code></li>" for path in bundle.browser_result.screenshots
            ) + "</ul>"
        execution_failure_note = ""
        if browser_cat.status.value in ("fail", "warning") and any(
            f.classification.value == "execution_failure" for f in browser_cat.findings
        ):
            execution_failure_note = (
                "<p><em>The browser test could not be reliably executed for one or more cases. "
                "This does not by itself prove the application is defective.</em></p>"
            )
        browser_html = (
            f'<p><strong>Status:</strong> {_status_span(browser_cat.status.value)}</p>'
            f'<p><strong>Target:</strong> <code>{_e(target_text)}</code> &middot; '
            f'<strong>Browser:</strong> {_e(browser_name)}</p>'
            f'<p>{_e(browser_cat.summary)}</p>'
            + execution_failure_note + screenshots_html
        )
        frontend_browser_note = (
            f'<strong>Browser/UI Execution: {_e(browser_cat.status.value.upper())}</strong> - '
            "see Browser Testing section below for details."
        )

    scenario_cat = next((c for c in a.categories if c.name == "Web Scenarios"), None)
    if scenario_cat is None or scenario_cat.status.value == "not_assessed":
        reason = scenario_cat.reason if scenario_cat else "no scenario was requested"
        scenario_html = (
            "<p><strong>NOT ASSESSED</strong></p>"
            f"<p>No explicit Web Scenario was executed. Reason: {_e(reason)}</p>"
        )
    else:
        scenario_rows = "\n".join(
            f"<tr><td>{_e(r.scenario_name)}</td><td><code>{_e(r.scenario_id)}</code></td>"
            f"<td>{_e(r.status.upper())}</td>"
            f"<td>{r.passed_steps}/{r.failed_steps}/{r.error_steps}/{r.skipped_steps}</td>"
            f"<td>{r.duration_seconds:.2f}s</td></tr>"
            for r in (bundle.scenario_results or [])
        )
        scenario_execution_failure_note = ""
        if any(f.classification.value == "execution_failure" for f in scenario_cat.findings):
            scenario_execution_failure_note = (
                "<p><em>A scenario could not be reliably executed for one or more cases. "
                "This does not by itself prove the application is defective.</em></p>"
            )
        scenario_html = (
            f'<p><strong>Status:</strong> {_status_span(scenario_cat.status.value)}</p>'
            f'<p>{_e(scenario_cat.summary)}</p>'
            + scenario_execution_failure_note
            + "<table><tr><th>Scenario</th><th>ID</th><th>Status</th>"
              "<th>Steps (P/F/E/S)</th><th>Duration</th></tr>" + scenario_rows + "</table>"
        )

    fe = bundle.model.frontend
    if fe.detected:
        frontend_signal_rows = "\n".join(
            f"<tr><td>{_e(label)}</td><td>{_e(signal.status.value)}</td></tr>"
            for label, signal in (
                ("Routes", fe.routes), ("Components", fe.components),
                ("Forms", fe.forms), ("Interactive UI", fe.interactive_ui),
                ("API clients", fe.api_clients),
                ("Responsive design", fe.responsive), ("Authentication UI", fe.auth_ui),
                ("Content-Security-Policy", fe.csp),
            )
        )
        frontend_meta_bits = []
        if fe.frontend_type:
            frontend_meta_bits.append(f"<strong>Type:</strong> {_e(fe.frontend_type.value)}")
        if fe.entry_points:
            frontend_meta_bits.append(f"<strong>Entry point(s):</strong> {_e(', '.join(fe.entry_points))}")
        if len(fe.web_roots) > 1:
            frontend_meta_bits.append(f"<strong>Multiple web roots detected:</strong> {_e(', '.join(fe.web_roots))}")
        if fe.html_page_count or fe.css_file_count or fe.js_file_count:
            frontend_meta_bits.append(
                f"<strong>HTML pages:</strong> {fe.html_page_count} &middot; "
                f"<strong>CSS files:</strong> {fe.css_file_count} &middot; "
                f"<strong>JS files:</strong> {fe.js_file_count} "
                f"(inline CSS blocks: {fe.inline_css_count}, inline JS blocks: {fe.inline_js_count})"
            )
        if fe.application_pattern:
            frontend_meta_bits.append(
                f"<strong>Application pattern:</strong> {_e(fe.application_pattern)} "
                "<em>(evidence suggests, not confirmed)</em>"
            )
        if fe.css_frameworks:
            frontend_meta_bits.append(f"<strong>CSS frameworks:</strong> {_e(', '.join(fe.css_frameworks))}")
        if fe.browser_apis:
            frontend_meta_bits.append(f"<strong>Browser APIs detected:</strong> {_e(', '.join(fe.browser_apis))}")
        if fe.external_resources:
            frontend_meta_bits.append(f"<strong>External resources:</strong> {_e(', '.join(fe.external_resources))}")
        frontend_meta_html = (
            "<p>" + " &middot; ".join(frontend_meta_bits) + "</p>" if frontend_meta_bits else ""
        )
        frontend_html = (
            f'<p><strong>Status:</strong> {_status_span(frontend_cat.status.value) if frontend_cat else "N/A"}</p>'
            f'<p>{_e(frontend_cat.summary) if frontend_cat else ""}</p>'
            + frontend_meta_html
            + f"<table><tr><th>Signal</th><th>Status</th></tr>{frontend_signal_rows}</table>"
            + f"<p><em>{frontend_browser_note}</em></p>"
        )
    elif frontend_cat is not None:
        frontend_html = (
            f'<p><strong>Status:</strong> {_status_span(frontend_cat.status.value)}</p>'
            f'<p>{_e(frontend_cat.summary)}</p>'
            + (f'<p><em>Reason: {_e(frontend_cat.reason)}</em></p>' if frontend_cat.reason else "")
        )
    else:
        frontend_html = "<p><em>Frontend was not assessed.</em></p>"

    if bundle.regression is None:
        regression_html = "<p><em>No baseline was provided; regression comparison was not performed.</em></p>"
    else:
        r = bundle.regression
        category_blocks = "\n".join(
            f'<div class="finding"><h3>{_e(rc.name)}: {_status_span(rc.status.value)}</h3>'
            f'<p>{_e(rc.summary)}</p>'
            + (f'<p><em>Reason: {_e(rc.reason)}</em></p>' if rc.reason else "")
            + ("<ul>" + "".join(
                f"<li>[{_e(f.severity.value.upper())}] {_e(f.title)}</li>" for f in rc.findings
            ) + "</ul>" if rc.findings else "")
            + "</div>"
            for rc in r.categories
        )
        regression_html = (
            f'<p><strong>Status:</strong> {_status_span(r.status.value)}</p>'
            f'<p><strong>Baseline:</strong> {_e(r.baseline_meta["generated_at"])} '
            f'(tool {_e(r.baseline_meta["tool_version"])}) &middot; '
            f'<strong>Current:</strong> {_e(r.current_meta["generated_at"])} '
            f'(tool {_e(r.current_meta["tool_version"])})</p>'
            + category_blocks
        )

    if bundle.quality_gate is None:
        quality_gate_html = "<p><em>Quality Gate was not evaluated.</em></p>"
    else:
        qg = bundle.quality_gate
        qg_finding_rows = "\n".join(
            f"<tr><td>{_e(f.rule)}</td><td>{_e(f.level.upper())}</td><td>{_e(f.title)}</td></tr>"
            for f in qg.findings
        )
        qg_clarification = ""
        if qg.status.value == "pass":
            qg_clarification = ('<p><em>No configured quality-gate rule failed. This does not mean '
                                 "all application behavior was tested.</em></p>")
        elif qg.status.value == "fail":
            qg_clarification = "<p><em>A configured quality-gate condition failed. See findings below.</em></p>"
        quality_gate_html = (
            f'<p><strong>Status:</strong> {_status_span(qg.status.value)} '
            f'&middot; <strong>Exit code:</strong> {_e(qg.exit_code)}</p>'
            + qg_clarification
            + (f'<p><em>Reason: {_e(qg.reason)}</em></p>' if qg.reason else "")
            + (
                f"<table><tr><th>Rule</th><th>Level</th><th>Title</th></tr>{qg_finding_rows}</table>"
                if qg.findings else "<p><em>No Quality Gate findings.</em></p>"
            )
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Universal Project Assessment - {_e(a.project_path)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; max-width: 960px;
          margin: 2rem auto; padding: 0 1rem; color: #1f2328; line-height: 1.5; }}
  h1 {{ border-bottom: 2px solid #d0d7de; padding-bottom: .5rem; }}
  h2 {{ margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: .3rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #d0d7de; padding: .4rem .6rem; text-align: left; font-size: .95em; }}
  th {{ background: #f6f8fa; }}
  .finding {{ border: 1px solid #d0d7de; border-radius: 6px; padding: .8rem 1rem; margin: .8rem 0; }}
  .banner {{ padding: 1rem; border-radius: 6px; background: #f6f8fa; margin: 1rem 0; }}
  .disclaimer {{ background: #fff8c5; border: 1px solid #d4a72c; border-radius: 6px; padding: 1rem; }}
  code {{ background: #f6f8fa; padding: .1rem .3rem; border-radius: 4px; }}
</style>
</head>
<body>
<h1>Universal Project Assessment</h1>

<div class="banner">
  <p><strong>Overall Status:</strong> {_status_span(a.overall_status.value)}</p>
  <p><strong>Project:</strong> <code>{_e(a.project_path)}</code></p>
  <p><strong>Target:</strong> {f"<code>{_e(a.target)}</code>" if a.target else "<em>not provided</em>"}</p>
  <p><strong>Generated:</strong> {_e(a.generated_at)} &middot; tool version {_e(a.tool_version)} &middot; schema {_e(a.schema_version)}</p>
</div>

<h2>Assessment Summary</h2>
{assessment_summary_html}

<h2>Critical Findings</h2>
<ul>{critical_html}</ul>

<h2>Quality Gate</h2>
{quality_gate_html}

<h2>Category Summary</h2>
<table>
<tr><th>Category</th><th>Status</th><th>Summary</th><th>Reason</th></tr>
{category_rows}
</table>

<h2>Functional Summary</h2>
<p><strong>Status:</strong> {_status_span(functional_cat.status.value)}</p>
<p>{_e(functional_cat.summary)}</p>

<h2>Performance Summary</h2>
<p><strong>Status:</strong> {_status_span(performance_cat.status.value)}</p>
<p>{_e(performance_cat.summary)}</p>

<h2>Database Summary</h2>
<p><strong>Status:</strong> {_status_span(database_cat.status.value)}</p>
<p>{_e(database_cat.summary)}</p>
{f"<p><em>Reason: {_e(database_cat.reason)}</em></p>" if database_cat.reason else ""}

<h2>Frontend / Web Application</h2>
{frontend_html}

<h2>Browser Testing</h2>
{browser_html}

<h2>Web Scenarios</h2>
{scenario_html}

<h2>Regression</h2>
{regression_html}

<h2>Findings</h2>
{finding_blocks}

<h2>Recommendations</h2>
<ul>{recommendation_items}</ul>

<h2>Coverage</h2>
<table>
<tr><th>Area</th><th>Coverage</th><th>Reason</th></tr>
{coverage_rows}
</table>

<h2>Unknown / Not Assessed</h2>
<ul>{unassessed_items}</ul>

<h2>Limitations</h2>
<div class="disclaimer">
<ul>{limitation_items}</ul>
</div>

</body>
</html>
"""
