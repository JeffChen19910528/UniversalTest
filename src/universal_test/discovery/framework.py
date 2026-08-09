"""Framework detection.

Only asserts a framework when there is concrete manifest-dependency or
marker-file evidence (skill.md Phase 2 brief: "don't assert a framework from
a single weak signal"). No source-code import scanning — that would be
expensive and error-prone across languages; dependency declarations are the
maintainable, direct signal a project's own tooling already relies on.
"""

from __future__ import annotations

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile
from universal_test.discovery.manifests import ManifestBundle, npm_dependency_names, python_dependency_names
from universal_test.discovery.models import FrameworkDetection


def _npm_framework(name: str, deps: set[str], *package_names: str) -> FrameworkDetection | None:
    matched = deps & set(package_names)
    if not matched:
        return None
    return FrameworkDetection(
        name=name, confidence=DetectionConfidence.DETECTED,
        evidence=[Evidence("dependency", {"source": "package.json", "matched": sorted(matched)})],
    )


def _python_framework(name: str, deps: set[str], *package_names: str) -> FrameworkDetection | None:
    matched = deps & {p.lower() for p in package_names}
    if not matched:
        return None
    return FrameworkDetection(
        name=name, confidence=DetectionConfidence.DETECTED,
        evidence=[Evidence("dependency", {"source": "requirements.txt/pyproject.toml", "matched": sorted(matched)})],
    )


def detect_frameworks(files: list[ScannedFile], manifests: ManifestBundle) -> list[FrameworkDetection]:
    detections: list[FrameworkDetection] = []

    npm_deps = npm_dependency_names(manifests)
    for framework, packages in [
        ("React", ("react",)),
        ("Angular", ("@angular/core",)),
        ("Vue", ("vue",)),
        ("Express", ("express",)),
    ]:
        result = _npm_framework(framework, npm_deps, *packages)
        if result:
            detections.append(result)

    has_frontend_framework = any(d.name in ("React", "Angular", "Vue") for d in detections)
    has_node_backend_hint = bool(npm_deps & {"express", "fastify", "koa"}) or _looks_like_node_service(manifests)
    if manifests.package_json is not None and has_node_backend_hint and not has_frontend_framework:
        # Generic "Node.js" backend service evidence only when there's no frontend
        # framework already claiming it — avoids double-labeling a React app as also
        # a "Node.js backend".
        detections.append(FrameworkDetection(
            name="Node.js", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": "package.json"})],
        ))

    python_deps = python_dependency_names(manifests)
    for framework, packages in [
        ("FastAPI", ("fastapi",)),
        ("Django", ("django",)),
        ("Flask", ("flask",)),
    ]:
        result = _python_framework(framework, python_deps, *packages)
        if result:
            detections.append(result)

    if manifests.by_name("manage.py") and not any(d.name == "Django" for d in detections):
        detections.append(FrameworkDetection(
            name="Django", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("marker_file", {"file": "manage.py"})],
        ))

    for csproj_text, csproj_file in zip(manifests.csproj_texts, manifests.by_suffix(".csproj")):
        lowered = csproj_text.lower()
        if "microsoft.aspnetcore" in lowered or 'sdk="microsoft.net.sdk.web"' in lowered:
            detections.append(FrameworkDetection(
                name="ASP.NET Core", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("manifest_file", {"file": csproj_file.relative, "matched": "Microsoft.AspNetCore*"})],
            ))
        if "<usewindowsforms>true" in lowered.replace(" ", ""):
            detections.append(FrameworkDetection(
                name="WinForms", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("manifest_file", {"file": csproj_file.relative, "matched": "UseWindowsForms"})],
            ))
        if "<usewpf>true" in lowered.replace(" ", ""):
            detections.append(FrameworkDetection(
                name="WPF", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("manifest_file", {"file": csproj_file.relative, "matched": "UseWPF"})],
            ))

    gradle_or_pom = (manifests.build_gradle or "") + (manifests.pom_xml or "")
    if "spring-boot" in gradle_or_pom.lower():
        source = "build.gradle" if manifests.build_gradle and "spring-boot" in manifests.build_gradle.lower() else "pom.xml"
        detections.append(FrameworkDetection(
            name="Spring Boot", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("manifest_file", {"file": source, "matched": "spring-boot"})],
        ))

    if manifests.composer_json is not None:
        deps = set(manifests.composer_json.get("require", {}) or {})
        if any(d.startswith("laravel/framework") for d in deps):
            detections.append(FrameworkDetection(
                name="Laravel", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("dependency", {"source": "composer.json", "matched": "laravel/framework"})],
            ))

    if manifests.by_name("hardhat.config.js", "hardhat.config.ts"):
        detections.append(FrameworkDetection(
            name="Hardhat", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("marker_file", {"file": "hardhat.config.js"})],
        ))
    if manifests.by_name("foundry.toml"):
        detections.append(FrameworkDetection(
            name="Foundry", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("marker_file", {"file": "foundry.toml"})],
        ))

    return detections


def _looks_like_node_service(manifests: ManifestBundle) -> bool:
    if not manifests.package_json:
        return False
    scripts = manifests.package_json.get("scripts", {})
    return isinstance(scripts, dict) and any(
        "node" in str(v).lower() or key in ("start", "server") for key, v in scripts.items()
    )
