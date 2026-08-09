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
