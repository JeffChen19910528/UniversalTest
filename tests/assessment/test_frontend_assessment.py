from pathlib import Path

from universal_test.core.models.enums import AssessmentStatus, FindingClassification
from universal_test.discovery.engine import discover
from universal_test.assessment.frontend_assessment import assess_frontend_health

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_no_frontend_evidence_is_not_assessed():
    model = discover(FIXTURES / "backend-mentions-react")
    category = assess_frontend_health(model)
    assert category.status == AssessmentStatus.NOT_ASSESSED
    assert category.reason == "no frontend framework/build evidence was detected in this repository"


def test_frontend_with_test_framework_is_pass():
    model = discover(FIXTURES / "react-vite-vitest")
    category = assess_frontend_health(model)
    assert category.status == AssessmentStatus.PASS


def test_frontend_without_test_framework_is_warning_not_fail():
    model = discover(FIXTURES / "frontend-no-tests")
    category = assess_frontend_health(model)
    assert category.status == AssessmentStatus.WARNING
    assert category.status != AssessmentStatus.FAIL
    no_test_finding = next(f for f in category.findings if f.id == "FRONTEND-NO-TEST")
    assert no_test_finding.status == AssessmentStatus.WARNING
    assert no_test_finding.classification == FindingClassification.TESTABILITY_GAP


def test_no_browser_automation_framework_is_info_not_fail():
    # react-vite-vitest has Vitest (unit) + Playwright (browser) - use a
    # fixture with only unit-level testing to exercise the "no browser test"
    # info finding distinctly.
    model = discover(FIXTURES / "sveltekit-app")
    category = assess_frontend_health(model)
    assert category.status != AssessmentStatus.FAIL
    browser_finding = next((f for f in category.findings if f.id == "FRONTEND-NO-BROWSER-TEST"), None)
    assert browser_finding is not None
    assert browser_finding.severity.value == "info"
    assert browser_finding.status == AssessmentStatus.PASS  # testability gap, not a defect


def test_status_is_never_fail_across_all_fixtures():
    for name in (
        "react-vite-vitest", "vue-app", "angular-app", "nextjs-app", "sveltekit-app",
        "frontend-no-tests", "frontend-malformed-package-json", "frontend-empty-dir",
        "backend-mentions-react", "frontend-static-basic", "frontend-static-form",
        "frontend-static-api", "frontend-single-html", "frontend-docs-only",
        "frontend-coverage-only", "backend-html-template",
    ):
        model = discover(FIXTURES / name)
        category = assess_frontend_health(model)
        assert category.status != AssessmentStatus.FAIL, f"{name} should never be FAIL"


def test_static_web_summary_mentions_html_css_js_counts_not_broken():
    model = discover(FIXTURES / "frontend-static-basic")
    category = assess_frontend_health(model)
    assert "Static HTML website" in category.summary
    assert "HTML pages: 2" in category.summary
    assert category.status == AssessmentStatus.WARNING  # no test framework detected, not a defect
    no_test_finding = next(f for f in category.findings if f.id == "FRONTEND-NO-TEST")
    assert "not proof the frontend has defects" in no_test_finding.description


def test_docs_only_html_is_not_assessed_as_frontend():
    model = discover(FIXTURES / "frontend-docs-only")
    category = assess_frontend_health(model)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_full_stack_web_summary_present():
    model = discover(FIXTURES / "mixed-project")
    category = assess_frontend_health(model)
    assert "Full-stack web project" in category.summary
    assert category.status != AssessmentStatus.FAIL
