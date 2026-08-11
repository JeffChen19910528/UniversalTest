"""Assess Phase 2 discovery output: "Project Discovery" and "Build / Project
Health" categories, plus "Test Infrastructure".
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, DetectionConfidence, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.models import FrontendType, ProjectModel
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding


def assess_project_discovery(model: ProjectModel) -> AssessmentCategory:
    detected_languages = [l for l in model.languages if l.confidence == DetectionConfidence.DETECTED]
    detected_types = [t for t in model.project_types if t.confidence == DetectionConfidence.DETECTED and t.name != "generic"]

    if not model.languages and not detected_types:
        status = AssessmentStatus.UNKNOWN
        reason = "no language or project type could be detected"
    elif detected_languages or detected_types:
        status = AssessmentStatus.PASS
        reason = None
    else:
        status = AssessmentStatus.WARNING
        reason = "only weak (inferred) language/project-type signals were found"

    findings: list[AssessmentFinding] = []
    if model.warnings:
        findings.append(AssessmentFinding(
            id="DISC-001", category="Project Discovery", status=AssessmentStatus.WARNING,
            severity=Severity.LOW, confidence=0.7,
            title="Discovery encountered non-fatal issues",
            description="; ".join(model.warnings),
            recommendation="Review the listed files/parsers. Discovery continued and produced a "
                            "result, but some data may be incomplete.",
            classification=FindingClassification.INFORMATIONAL,
        ))

    summary = (
        f"{len(model.languages)} language(s), {len(model.project_types)} project type(s) detected "
        f"across {model.file_count} scanned file(s)"
    )
    evidence = [Evidence("discovery_summary", {
        "primary_language": model.primary_language,
        "languages": [l.name for l in model.languages],
        "project_types": [t.name for t in model.project_types],
    })]
    return AssessmentCategory(
        name="Project Discovery", status=status, summary=summary, reason=reason,
        findings=findings, evidence=evidence,
    )


def assess_build_health(model: ProjectModel) -> AssessmentCategory:
    detected = [b for b in model.build_systems if b.confidence == DetectionConfidence.DETECTED]
    is_static_web_only = (
        not model.build_systems
        and model.frontend.detected
        and model.frontend.frontend_type in (FrontendType.STATIC_WEB, FrontendType.UNKNOWN_WEB)
    )
    if detected:
        status = AssessmentStatus.PASS
        reason = None
    elif is_static_web_only:
        # A static HTML/CSS/JS website legitimately has no package manager
        # or build tool - this is not a build-health problem (Static Web
        # Analysis brief §7). Only a project that could plausibly need one
        # (a framework/backend detected, or ambiguous evidence) still WARNs.
        status = AssessmentStatus.PASS
        reason = "static website detected; a package manager/build system is not required"
    elif model.build_systems:
        status = AssessmentStatus.WARNING
        reason = "build system evidence is weak (inferred only)"
    else:
        status = AssessmentStatus.WARNING
        reason = "no package manager/build tool manifest was found"

    names = [b.name for b in model.build_systems]
    summary = f"{len(model.build_systems)} build system(s) detected: {', '.join(names) or 'none'}"
    evidence = [Evidence("build_systems", {"names": names})]
    return AssessmentCategory(
        name="Build / Project Health", status=status, summary=summary, reason=reason, evidence=evidence,
    )


def assess_test_infrastructure(model: ProjectModel) -> AssessmentCategory:
    if model.test_frameworks:
        status = AssessmentStatus.PASS
        reason = None
    else:
        status = AssessmentStatus.WARNING
        reason = "no recognized test framework or configuration was found"

    findings: list[AssessmentFinding] = []
    if not model.test_frameworks and not model.test_directories:
        findings.append(AssessmentFinding(
            id="TESTINFRA-001", category="Test Infrastructure", status=AssessmentStatus.WARNING,
            severity=Severity.MEDIUM, confidence=0.6,
            title="No test framework or test directory detected",
            description=(
                "Neither a recognized test framework/config file nor a conventional test "
                "directory (tests/, test/, __tests__/, spec/) was found. This is a testability "
                "limitation - automated regression testing is not currently available for this "
                "project - it does NOT indicate that the application itself contains defects."
            ),
            recommendation="Add an automated test framework appropriate for the project's primary "
                            "language, even a minimal one, to make future regressions detectable.",
            classification=FindingClassification.TESTABILITY_GAP,
        ))

    names = [t.name for t in model.test_frameworks]
    summary = f"{len(model.test_frameworks)} test framework(s) detected: {', '.join(names) or 'none'}"
    evidence = [Evidence("test_infrastructure", {
        "test_frameworks": names, "test_directories": model.test_directories,
    })]
    return AssessmentCategory(
        name="Test Infrastructure", status=status, summary=summary, reason=reason,
        findings=findings, evidence=evidence,
    )
