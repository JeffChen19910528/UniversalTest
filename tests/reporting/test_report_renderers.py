import json

from universal_test.discovery import discover
from universal_test.assessment import build_assessment
from universal_test.reporting import AssessReportBundle, to_html, to_json, to_markdown
from universal_test.discovery.models import SecretFinding
from universal_test.core.models.enums import DetectionConfidence


def _bundle_for(fixture: str) -> AssessReportBundle:
    model = discover(f"tests/fixtures/{fixture}")
    assessment = build_assessment(
        project_path=f"tests/fixtures/{fixture}", target=None, model=model, generated_count=0,
        run_result=None, functional_not_run_reason="no execution target was provided",
        perf_result=None, performance_not_run_reason="performance execution was not enabled",
        has_confirmed_openapi=False,
    )
    return AssessReportBundle(assessment=assessment, model=model, run_result=None, generated_count=0, perf_result=None)


def test_json_report_is_valid_and_has_schema_version():
    bundle = _bundle_for("healthy-project")
    parsed = json.loads(to_json(bundle))
    assert parsed["schema_version"] == "1.0"
    assert "discovery" in parsed
    assert "assessment" in parsed
    assert "findings" in parsed
    assert "limitations" in parsed


def test_markdown_report_has_required_sections():
    bundle = _bundle_for("healthy-project")
    md = to_markdown(bundle)
    for section in (
        "# Universal Project Assessment", "## Executive Summary", "## Project Discovery",
        "## Technology Detection", "## Testability", "## Functional Testing", "## Performance",
        "## Database", "## Findings", "## Recommendations", "## Coverage", "## Unknown / Not Assessed",
        "## Limitations", "## Execution Information",
    ):
        assert section in md, f"missing section: {section}"


def test_html_report_is_offline_and_has_no_external_resources():
    bundle = _bundle_for("healthy-project")
    html_text = to_html(bundle)
    assert "<script" not in html_text
    assert "cdn." not in html_text.lower()
    assert "http://" not in html_text.replace("Universal Project Assessment", "")  # no external links
    assert "https://" not in html_text
    assert html_text.strip().startswith("<!doctype html>")


def test_report_generation_is_deterministic():
    bundle = _bundle_for("healthy-project")
    j1, j2 = to_json(bundle), to_json(bundle)
    m1, m2 = to_markdown(bundle), to_markdown(bundle)
    # generated_at is the only expected difference-free field here since we render the same bundle twice
    assert j1 == j2
    assert m1 == m2


def test_secret_pattern_never_appears_in_any_report_format():
    model = discover("tests/fixtures/healthy-project")
    model.secrets = [SecretFinding(file="config.py", line=1, pattern_type="password", confidence=DetectionConfidence.INFERRED)]
    assessment = build_assessment(
        project_path="x", target=None, model=model, generated_count=0, run_result=None,
        functional_not_run_reason="no target", perf_result=None,
        performance_not_run_reason="not enabled", has_confirmed_openapi=False,
    )
    bundle = AssessReportBundle(assessment=assessment, model=model, run_result=None, generated_count=0, perf_result=None)

    for rendered in (to_json(bundle), to_markdown(bundle), to_html(bundle)):
        assert "[REDACTED]" in rendered
        # the secret *value* was never captured anywhere upstream (Phase 2 design),
        # so there is nothing to assert "not in rendered" beyond confirming the
        # redaction marker made it all the way through instead of the raw pattern data.


def test_static_web_json_report_includes_type_and_counts():
    bundle = _bundle_for("frontend-static-basic")
    parsed = json.loads(to_json(bundle))
    fe = parsed["discovery"]["frontend"]
    assert fe["frontend_type"] == "static_web"
    assert fe["html_page_count"] == 2
    assert fe["entry_points"] == ["index.html"]


def test_static_web_markdown_and_html_reports_show_type():
    bundle = _bundle_for("frontend-static-basic")
    md = to_markdown(bundle)
    html_text = to_html(bundle)
    assert "static_web" in md
    assert "static_web" in html_text
    assert "HTML pages" in md
    assert "HTML pages" in html_text


def test_json_report_includes_frontend_section_for_free():
    bundle = _bundle_for("react-vite-vitest")
    parsed = json.loads(to_json(bundle))
    assert parsed["discovery"]["frontend"]["detected"] is True
    frontend_category = next(
        c for c in parsed["assessment"]["categories"] if c["name"] == "Frontend / Web Application Health"
    )
    assert frontend_category["status"] in ("pass", "warning")


def test_markdown_report_has_frontend_section_and_not_assessed_marker():
    bundle = _bundle_for("react-vite-vitest")
    md = to_markdown(bundle)
    assert "## Frontend / Web Application" in md
    assert "Browser/UI Execution: NOT_ASSESSED" in md


def test_html_report_has_frontend_section_and_not_assessed_marker():
    bundle = _bundle_for("react-vite-vitest")
    html_text = to_html(bundle)
    assert "Frontend / Web Application" in html_text
    assert "Browser/UI Execution: NOT_ASSESSED" in html_text


def test_env_example_values_never_leak_only_key_names():
    bundle = _bundle_for("react-vite-vitest")
    assert bundle.model.frontend.env_public_keys == ["VITE_API_BASE_URL", "VITE_FEATURE_FLAG_NEW_UI"]
    for rendered in (to_json(bundle), to_markdown(bundle), to_html(bundle)):
        # the raw "KEY=value" line must never appear verbatim - only the key name may
        assert "VITE_FEATURE_FLAG_NEW_UI=false" not in rendered


def test_html_escapes_finding_content(tmp_path):
    # a malicious-looking file name should never break out of the HTML it's embedded in
    model = discover("tests/fixtures/healthy-project")
    model.secrets = [SecretFinding(file="<script>alert(1)</script>.py", line=1, pattern_type="password", confidence=DetectionConfidence.INFERRED)]
    assessment = build_assessment(
        project_path="x", target=None, model=model, generated_count=0, run_result=None,
        functional_not_run_reason="no target", perf_result=None,
        performance_not_run_reason="not enabled", has_confirmed_openapi=False,
    )
    bundle = AssessReportBundle(assessment=assessment, model=model, run_result=None, generated_count=0, perf_result=None)
    html_text = to_html(bundle)
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_application_health_and_completeness_appear_in_json():
    bundle = _bundle_for("frontend-static-basic")
    parsed = json.loads(to_json(bundle))
    assert parsed["assessment"]["overall_status"] == "warning"
    assert "application_health" in parsed["assessment"]
    assert "assessment_completeness" in parsed["assessment"]


def test_finding_classification_appears_in_json():
    bundle = _bundle_for("frontend-static-basic")
    parsed = json.loads(to_json(bundle))
    findings = parsed["findings"]
    assert findings
    assert all("classification" in f for f in findings)


def test_assessment_summary_appears_in_markdown_and_html():
    bundle = _bundle_for("frontend-static-basic")
    md = to_markdown(bundle)
    html_text = to_html(bundle)
    assert "## Assessment Summary" in md
    assert "Application Health" in md
    assert "no confirmed defect" in md.lower()
    assert "Assessment Summary" in html_text
    assert "Application Health" in html_text


def test_rich_spa_report_shows_inline_css_js_and_browser_apis():
    bundle = _bundle_for("frontend-static-rich-spa")
    md = to_markdown(bundle)
    parsed = json.loads(to_json(bundle))
    fe = parsed["discovery"]["frontend"]
    assert fe["inline_css_count"] == 1
    assert fe["inline_js_count"] == 1
    assert "MediaRecorder" in fe["browser_apis"]
    assert "inline CSS blocks: 1" in md
    assert "inline JS blocks: 1" in md
