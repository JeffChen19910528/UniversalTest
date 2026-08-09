"""Project type + build-system detection, driven by manifest presence."""

from __future__ import annotations

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile
from universal_test.discovery.manifests import ManifestBundle
from universal_test.discovery.models import BuildSystemDetection, ProjectTypeDetection

_FRONTEND_PACKAGE_HINTS = {
    "react", "react-dom", "vue", "@angular/core", "svelte", "next", "nuxt", "vite",
}


def detect_project_types(files: list[ScannedFile], manifests: ManifestBundle) -> list[ProjectTypeDetection]:
    detections: list[ProjectTypeDetection] = []

    if manifests.by_name("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"):
        marker = next(
            m.relative for m in manifests.by_name(
                "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"
            )
        )
        detections.append(ProjectTypeDetection(
            name="python", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": marker})],
        ))

    if manifests.package_json is not None:
        detections.append(ProjectTypeDetection(
            name="node", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": "package.json"})],
        ))
        deps = set(manifests.package_json.get("dependencies", {}) or {})
        deps |= set(manifests.package_json.get("devDependencies", {}) or {})
        if deps & _FRONTEND_PACKAGE_HINTS:
            detections.append(ProjectTypeDetection(
                name="frontend", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("dependency", {"matched": sorted(deps & _FRONTEND_PACKAGE_HINTS)})],
            ))

    if manifests.by_suffix(".csproj", ".sln"):
        files_found = [f.relative for f in manifests.by_suffix(".csproj", ".sln")]
        detections.append(ProjectTypeDetection(
            name="dotnet", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"files": files_found})],
        ))

    if manifests.pom_xml or manifests.build_gradle:
        source = "pom.xml" if manifests.pom_xml else "build.gradle"
        detections.append(ProjectTypeDetection(
            name="java", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": source})],
        ))

    if manifests.go_mod is not None:
        detections.append(ProjectTypeDetection(
            name="go", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": "go.mod"})],
        ))

    if manifests.cargo_toml is not None:
        detections.append(ProjectTypeDetection(
            name="rust", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": "Cargo.toml"})],
        ))

    if manifests.composer_json is not None:
        detections.append(ProjectTypeDetection(
            name="php", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": "composer.json"})],
        ))

    if not detections:
        detections.append(ProjectTypeDetection(
            name="generic", confidence=DetectionConfidence.UNKNOWN,
            evidence=[Evidence("absence", {"reason": "no recognized manifest file found"})],
        ))

    return detections


def detect_build_systems(files: list[ScannedFile], manifests: ManifestBundle) -> list[BuildSystemDetection]:
    detections: list[BuildSystemDetection] = []

    if manifests.by_name("poetry.lock"):
        detections.append(BuildSystemDetection("poetry", DetectionConfidence.DETECTED,
                                                 [Evidence("lockfile", {"file": "poetry.lock"})]))
    elif manifests.pyproject and isinstance(manifests.pyproject.get("tool", {}).get("poetry"), dict):
        detections.append(BuildSystemDetection("poetry", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "pyproject.toml", "section": "tool.poetry"})]))
    elif manifests.by_name("requirements.txt", "pyproject.toml", "setup.py"):
        detections.append(BuildSystemDetection("pip", DetectionConfidence.INFERRED,
                                                 [Evidence("manifest_file", {"file": "requirements.txt/pyproject.toml"})]))

    if manifests.package_json is not None:
        if manifests.by_name("pnpm-lock.yaml"):
            detections.append(BuildSystemDetection("pnpm", DetectionConfidence.DETECTED,
                                                     [Evidence("lockfile", {"file": "pnpm-lock.yaml"})]))
        elif manifests.by_name("yarn.lock"):
            detections.append(BuildSystemDetection("yarn", DetectionConfidence.DETECTED,
                                                     [Evidence("lockfile", {"file": "yarn.lock"})]))
        else:
            detections.append(BuildSystemDetection("npm", DetectionConfidence.INFERRED,
                                                     [Evidence("manifest_file", {"file": "package.json"})]))

    if manifests.by_suffix(".csproj", ".sln"):
        detections.append(BuildSystemDetection("dotnet sdk", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "*.csproj/*.sln"})]))

    if manifests.by_name("build.gradle", "build.gradle.kts"):
        detections.append(BuildSystemDetection("gradle", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "build.gradle"})]))
    elif manifests.pom_xml:
        detections.append(BuildSystemDetection("maven", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "pom.xml"})]))

    if manifests.go_mod is not None:
        detections.append(BuildSystemDetection("go modules", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "go.mod"})]))

    if manifests.cargo_toml is not None:
        detections.append(BuildSystemDetection("cargo", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "Cargo.toml"})]))

    if manifests.composer_json is not None:
        detections.append(BuildSystemDetection("composer", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "composer.json"})]))

    return detections
