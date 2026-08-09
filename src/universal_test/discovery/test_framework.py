"""Test-infrastructure detection: which test frameworks/tools a project uses."""

from __future__ import annotations

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile, find_test_directories
from universal_test.discovery.manifests import ManifestBundle, npm_dependency_names, python_dependency_names
from universal_test.discovery.models import TestFrameworkDetection


def detect_test_frameworks(files: list[ScannedFile], manifests: ManifestBundle) -> list[TestFrameworkDetection]:
    detections: list[TestFrameworkDetection] = []

    python_deps = python_dependency_names(manifests)
    has_pytest_ini = bool(manifests.by_name("pytest.ini", "conftest.py"))
    has_pytest_pyproject = bool(
        manifests.pyproject and isinstance(manifests.pyproject.get("tool", {}).get("pytest"), dict)
    )
    if "pytest" in python_deps or has_pytest_ini or has_pytest_pyproject:
        evidence = [Evidence("dependency_or_config", {
            "pytest_in_deps": "pytest" in python_deps,
            "pytest_ini_or_conftest": has_pytest_ini,
            "pyproject_tool_pytest": has_pytest_pyproject,
        })]
        detections.append(TestFrameworkDetection("pytest", DetectionConfidence.DETECTED, evidence))

    python_test_files = [f for f in files if f.extension == ".py" and (
        f.path.name.startswith("test_") or f.path.name.endswith("_test.py")
    )]
    if python_test_files and not any(d.name == "pytest" for d in detections):
        detections.append(TestFrameworkDetection(
            "unittest", DetectionConfidence.INFERRED,
            [Evidence("file_pattern", {"count": len(python_test_files), "pattern": "test_*.py"})],
        ))

    npm_deps = npm_dependency_names(manifests)
    if "jest" in npm_deps or manifests.by_name("jest.config.js", "jest.config.ts", "jest.config.mjs"):
        detections.append(TestFrameworkDetection(
            "Jest", DetectionConfidence.DETECTED,
            [Evidence("dependency_or_config", {"in_deps": "jest" in npm_deps})],
        ))
    if "vitest" in npm_deps or manifests.by_name("vitest.config.js", "vitest.config.ts"):
        detections.append(TestFrameworkDetection(
            "Vitest", DetectionConfidence.DETECTED,
            [Evidence("dependency_or_config", {"in_deps": "vitest" in npm_deps})],
        ))
    if "mocha" in npm_deps or manifests.by_name(".mocharc.json", ".mocharc.js", ".mocharc.yml"):
        detections.append(TestFrameworkDetection(
            "Mocha", DetectionConfidence.DETECTED,
            [Evidence("dependency_or_config", {"in_deps": "mocha" in npm_deps})],
        ))

    for csproj_text, csproj_file in zip(manifests.csproj_texts, manifests.by_suffix(".csproj")):
        lowered = csproj_text.lower()
        for pkg, name in (("nunit", "NUnit"), ("xunit", "xUnit"), ("mstest.testframework", "MSTest")):
            if pkg in lowered:
                detections.append(TestFrameworkDetection(
                    name, DetectionConfidence.DETECTED,
                    [Evidence("dependency", {"source": csproj_file.relative, "matched": pkg})],
                ))

    gradle_or_pom = (manifests.build_gradle or "") + (manifests.pom_xml or "")
    if "junit" in gradle_or_pom.lower():
        detections.append(TestFrameworkDetection(
            "JUnit", DetectionConfidence.DETECTED,
            [Evidence("dependency", {"matched": "junit"})],
        ))

    go_test_files = [f for f in files if f.relative.endswith("_test.go")]
    if go_test_files:
        detections.append(TestFrameworkDetection(
            "go test", DetectionConfidence.DETECTED,
            [Evidence("file_pattern", {"count": len(go_test_files), "pattern": "*_test.go"})],
        ))

    if manifests.cargo_toml is not None:
        rust_test_files = [f for f in files if f.extension == ".rs" and "test" in f.relative.lower()]
        confidence = DetectionConfidence.DETECTED if rust_test_files else DetectionConfidence.INFERRED
        evidence = [Evidence("manifest_file", {"file": "Cargo.toml"})]
        if rust_test_files:
            evidence.append(Evidence("file_pattern", {"count": len(rust_test_files)}))
        detections.append(TestFrameworkDetection("cargo test", confidence, evidence))

    return detections


def detect_test_directories(files: list[ScannedFile]) -> list[str]:
    return find_test_directories(files)
