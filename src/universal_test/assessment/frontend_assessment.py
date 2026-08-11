"""Frontend / Web Application Health: aggregates Phase 2's `FrontendInfo` +
the framework/language/build-system/test-framework facts discovery already
attached to `ProjectModel`. Never re-scans, never executes anything.

Status is deliberately capped **below `FAIL`** (Frontend Adapter brief §19):
missing UI/browser test tooling is a testability gap, not evidence the
assessed frontend itself is broken, so this category only ever reports
`PASS`, `WARNING`, or `NOT_ASSESSED` - never `FAIL`. Mirrors the same rule
`database_assessment.py` already enforces for connectivity problems.
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.frontend import (
    BROWSER_AUTOMATION_TEST_FRAMEWORK_NAMES,
    FRONTEND_FRAMEWORK_NAMES,
    FRONTEND_TEST_FRAMEWORK_NAMES,
)
from universal_test.discovery.models import FrontendType, ProjectModel
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding


def assess_frontend_health(model: ProjectModel) -> AssessmentCategory:
    if not model.frontend.detected:
        return AssessmentCategory(
            name="Frontend / Web Application Health", status=AssessmentStatus.NOT_ASSESSED,
            summary="no frontend detected",
            reason="no frontend framework/build evidence was detected in this repository",
        )

    frameworks = [f.name for f in model.frameworks if f.name in FRONTEND_FRAMEWORK_NAMES]
    languages = [l.name for l in model.languages if l.name in ("JavaScript", "TypeScript", "CSS", "SCSS")]
    build_systems = [
        b.name for b in model.build_systems
        if b.name in ("Vite", "Webpack", "Rollup", "Turbopack", "Angular CLI", "npm", "yarn", "pnpm", "bun")
    ]
    test_frameworks = [t.name for t in model.test_frameworks if t.name in FRONTEND_TEST_FRAMEWORK_NAMES]
    browser_test_frameworks = [t for t in test_frameworks if t in BROWSER_AUTOMATION_TEST_FRAMEWORK_NAMES]

    findings: list[AssessmentFinding] = []
    if not test_frameworks:
        findings.append(AssessmentFinding(
            id="FRONTEND-NO-TEST", category="Frontend / Web Application Health",
            status=AssessmentStatus.WARNING, severity=Severity.LOW, confidence=0.8,
            title="No frontend test framework was detected",
            description=(
                "No unit/component test framework (Jest, Vitest, Testing Library, etc.) was "
                "found. This is a testability gap, not proof the frontend has defects."
            ),
            recommendation="Add a frontend test framework (e.g. Vitest, Jest) if automated coverage is desired.",
            classification=FindingClassification.TESTABILITY_GAP,
        ))
    elif not browser_test_frameworks:
        findings.append(AssessmentFinding(
            id="FRONTEND-NO-BROWSER-TEST", category="Frontend / Web Application Health",
            status=AssessmentStatus.PASS, severity=Severity.INFO, confidence=0.8,
            title="No browser/UI automation test framework was detected",
            description=(
                "Unit-level testing tools were found, but no browser automation framework "
                "(Playwright, Cypress, WebdriverIO, Puppeteer). This is a testability "
                "limitation, not evidence the UI itself is broken - browser/UI execution "
                "is out of scope for this version regardless (see Browser/UI Execution: Not Assessed)."
            ),
            classification=FindingClassification.TESTABILITY_GAP,
        ))

    status = AssessmentStatus.WARNING if not test_frameworks else AssessmentStatus.PASS

    fe = model.frontend
    if fe.frontend_type in (FrontendType.STATIC_WEB, FrontendType.UNKNOWN_WEB):
        type_label = "Static HTML website" if fe.frontend_type == FrontendType.STATIC_WEB else "Web project (technology unclear)"
        summary = (
            f"{type_label} detected; HTML pages: {fe.html_page_count}; CSS files: {fe.css_file_count}; "
            f"JavaScript files: {fe.js_file_count}; forms: {fe.forms.status.value}; "
            f"CSS frameworks: {', '.join(fe.css_frameworks) or 'none detected'}; "
            f"test frameworks: {', '.join(test_frameworks) or 'none detected'}"
        )
    else:
        type_label = "Full-stack web project" if fe.frontend_type == FrontendType.FULL_STACK_WEB else "Frontend"
        summary = (
            f"{type_label} detected: {', '.join(frameworks) or 'unknown framework'}; "
            f"languages: {', '.join(languages) or 'none detected'}; "
            f"build: {', '.join(build_systems) or 'none detected'}; "
            f"test frameworks: {', '.join(test_frameworks) or 'none detected'}"
        )

    evidence = [
        Evidence("frontend_summary", {
            "frontend_type": fe.frontend_type.value if fe.frontend_type else None,
            "entry_points": fe.entry_points,
            "web_roots": fe.web_roots,
            "html_page_count": fe.html_page_count,
            "css_file_count": fe.css_file_count,
            "js_file_count": fe.js_file_count,
            "css_frameworks": fe.css_frameworks,
            "frameworks": frameworks,
            "languages": languages,
            "build_systems": build_systems,
            "test_frameworks": test_frameworks,
            "browser_automation_frameworks": browser_test_frameworks,
            "routes": fe.routes.to_dict(),
            "components": fe.components.to_dict(),
            "forms": fe.forms.to_dict(),
            "api_clients": fe.api_clients.to_dict(),
            "responsive": fe.responsive.to_dict(),
            "auth_ui": fe.auth_ui.to_dict(),
        }),
    ]

    return AssessmentCategory(
        name="Frontend / Web Application Health", status=status, summary=summary,
        findings=findings, evidence=evidence,
    )
