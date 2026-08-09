"""Cross-cutting regression test for the Windows-console-garbling class of
bug found repeatedly during Phase 6/7/8 (non-ASCII characters like `section
sign` and em dash print as mojibake on this project's default Windows
console codepage) and again during the V1 hardening audit, where several
finding/warning description strings still contained a raw em dash. House
rule (documented in PROGRESS.md since Phase 2): no `section sign` or em
dash in any string that can reach console output — use a plain ASCII
hyphen instead. This test exercises the actual code paths that produced
the audit findings, not just a static grep, so a future regression is
caught even if introduced through string concatenation/formatting.
"""

from __future__ import annotations

_FORBIDDEN = ("§", "—")  # section sign (section-sign), em dash


def _assert_ascii_safe(text: str, context: str) -> None:
    for ch in _FORBIDDEN:
        assert ch not in text, f"forbidden character {ch!r} found in {context}: {text!r}"


def test_configuration_hygiene_finding_text_is_ascii_safe():
    from universal_test.discovery import discover
    from universal_test.assessment.configuration_assessment import assess_configuration_hygiene

    model = discover("tests/fixtures/dotnet-api")
    assert model.secrets, "fixture must actually contain a detected secret pattern for this test to be meaningful"
    category = assess_configuration_hygiene(model)
    for finding in category.findings:
        _assert_ascii_safe(finding.title, "ConfigurationHygiene finding title")
        _assert_ascii_safe(finding.description, "ConfigurationHygiene finding description")


def test_database_health_finding_text_is_ascii_safe():
    from universal_test.adapters.database.adapter import discover as db_discover
    from universal_test.adapters.database.profile import DatabaseProfile
    from universal_test.assessment.database_assessment import assess_database_health

    profile = DatabaseProfile(engine="sqlite", readonly=True, path="tests/fixtures/database/sqlite-relations/app.db")
    result = db_discover(profile)
    assert result.info is not None
    category = assess_database_health(result)
    assert category.findings, "sqlite-relations fixture must produce at least one INFO finding (no-PK table)"
    for finding in category.findings:
        _assert_ascii_safe(finding.title, "DatabaseHealth finding title")
        _assert_ascii_safe(finding.description, "DatabaseHealth finding description")


def test_discovery_regression_finding_text_is_ascii_safe():
    from universal_test.regression.discovery_compare import compare_discovery
    from universal_test.regression.models import DiscoverySnapshot

    baseline = DiscoverySnapshot(databases=["PostgreSQL"])
    current = DiscoverySnapshot(databases=[])
    category = compare_discovery(baseline, current)
    assert category.findings
    for finding in category.findings:
        _assert_ascii_safe(finding.title, "Discovery regression finding title")
        _assert_ascii_safe(finding.description, "Discovery regression finding description")


def test_regression_tool_version_mismatch_warning_is_ascii_safe():
    from universal_test.regression.engine import compare
    from universal_test.regression.models import AssessmentSnapshot, BaselineSnapshot, DiscoverySnapshot, SourceInfo

    def _snap(tool_version: str) -> BaselineSnapshot:
        return BaselineSnapshot(
            schema_version="1.0", tool_version=tool_version, generated_at="t", project_path="./p",
            source=SourceInfo(is_git=False, commit=None, branch=None, dirty=None),
            discovery=DiscoverySnapshot(), functional=None, performance=None, database=None,
            assessment=AssessmentSnapshot(overall_status="pass", categories=[]),
        )

    summary = compare(_snap("0.1.0"), _snap("0.2.0"), performance_thresholds={})
    assert summary.warnings
    for warning in summary.warnings:
        _assert_ascii_safe(warning, "regression tool-version-mismatch warning")


def test_html_and_markdown_reports_are_ascii_safe_end_to_end():
    from universal_test.discovery import discover
    from universal_test.assessment import build_assessment
    from universal_test.reporting import AssessReportBundle, to_html, to_markdown

    model = discover("tests/fixtures/dotnet-api")
    assessment = build_assessment(
        project_path="tests/fixtures/dotnet-api", target=None, model=model, generated_count=0,
        run_result=None, functional_not_run_reason="no execution target was provided",
        perf_result=None, performance_not_run_reason="performance execution was not enabled",
        has_confirmed_openapi=False,
    )
    bundle = AssessReportBundle(assessment=assessment, model=model, run_result=None, generated_count=0, perf_result=None)
    _assert_ascii_safe(to_html(bundle), "report.html")
    _assert_ascii_safe(to_markdown(bundle), "report.md")
