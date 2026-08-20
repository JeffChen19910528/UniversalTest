"""Project type + build-system detection, driven by manifest presence."""

from __future__ import annotations

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile
from universal_test.discovery.manifests import ManifestBundle
from universal_test.discovery import frontend as _frontend
from universal_test.discovery.frontend import FRONTEND_CONFIG_MARKERS as _FRONTEND_CONFIG_MARKERS
from universal_test.discovery.frontend import FRONTEND_PACKAGE_HINTS as _FRONTEND_PACKAGE_HINTS
from universal_test.discovery.language import _CPP_ONLY_EXTENSIONS
from universal_test.discovery.models import BuildSystemDetection, ProjectTypeDetection

# Native build-system marker files shared by C and C++ projects. "Makefile"
# alone is deliberately excluded here — plenty of Python/Node/Go repos carry
# a Makefile as a task runner with no C/C++ code, so it would be a weak,
# misleading signal on its own; it only counts once paired with actual
# .c/.cpp source evidence (see below).
_NATIVE_BUILD_MARKERS = (
    "CMakeLists.txt", "meson.build", "configure.ac", "configure.in",
    "conanfile.txt", "conanfile.py", "vcpkg.json", "WORKSPACE", "BUILD.bazel",
)
_MIN_NATIVE_FILES_WITHOUT_MARKER = 3


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
        matched_deps = deps & _FRONTEND_PACKAGE_HINTS
        matched_config = manifests.by_name(*_FRONTEND_CONFIG_MARKERS)
        if matched_deps or matched_config:
            evidence = []
            if matched_deps:
                evidence.append(Evidence("dependency", {"matched": sorted(matched_deps)}))
            if matched_config:
                evidence.append(Evidence("config_file", {"matched": sorted(f.relative for f in matched_config)}))
            detections.append(ProjectTypeDetection(
                name="frontend", confidence=DetectionConfidence.DETECTED, evidence=evidence,
            ))
    else:
        matched_config = manifests.by_name(*_FRONTEND_CONFIG_MARKERS)
        if matched_config:
            detections.append(ProjectTypeDetection(
                name="frontend", confidence=DetectionConfidence.DETECTED,
                evidence=[Evidence("config_file", {"matched": sorted(f.relative for f in matched_config)})],
            ))

    # A plain static HTML/CSS/JS website has neither a package.json nor a
    # framework config file, so the branches above never fire for it - a
    # pure static site still deserves a "frontend" project-type signal
    # (Static Web Analysis brief §8: don't leave a valid static website
    # showing "0 languages, generic project").
    if not any(d.name == "frontend" for d in detections):
        static = _frontend.detect_static_web(files)
        if static.detected:
            detections.append(ProjectTypeDetection(
                name="frontend", confidence=static.confidence, evidence=static.evidence,
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

    c_files = [f for f in files if f.extension == ".c"]
    cpp_files = [f for f in files if f.extension in _CPP_ONLY_EXTENSIONS]
    h_files = [f for f in files if f.extension == ".h"]
    native_markers = manifests.by_name(*_NATIVE_BUILD_MARKERS) + manifests.by_name("Makefile", "makefile", "GNUmakefile")
    native_marker_names = sorted({m.relative for m in native_markers})

    if cpp_files and (native_marker_names or len(cpp_files) + len(h_files) >= _MIN_NATIVE_FILES_WITHOUT_MARKER):
        evidence = [Evidence("file_extension_count", {"count": len(cpp_files) + len(h_files)})]
        confidence = DetectionConfidence.DETECTED
        if native_marker_names:
            evidence.append(Evidence("manifest_file", {"files": native_marker_names}))
        else:
            confidence = DetectionConfidence.INFERRED
        detections.append(ProjectTypeDetection(name="cpp", confidence=confidence, evidence=evidence))
    elif (c_files or h_files) and (native_marker_names or len(c_files) >= _MIN_NATIVE_FILES_WITHOUT_MARKER):
        evidence = [Evidence("file_extension_count", {"count": len(c_files) + len(h_files)})]
        confidence = DetectionConfidence.DETECTED
        if native_marker_names:
            evidence.append(Evidence("manifest_file", {"files": native_marker_names}))
        else:
            confidence = DetectionConfidence.INFERRED
        detections.append(ProjectTypeDetection(name="c", confidence=confidence, evidence=evidence))

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
        if manifests.by_name("bun.lockb", "bun.lock"):
            detections.append(BuildSystemDetection("bun", DetectionConfidence.DETECTED,
                                                     [Evidence("lockfile", {"file": "bun.lockb/bun.lock"})]))
        elif manifests.by_name("pnpm-lock.yaml"):
            detections.append(BuildSystemDetection("pnpm", DetectionConfidence.DETECTED,
                                                     [Evidence("lockfile", {"file": "pnpm-lock.yaml"})]))
        elif manifests.by_name("yarn.lock"):
            detections.append(BuildSystemDetection("yarn", DetectionConfidence.DETECTED,
                                                     [Evidence("lockfile", {"file": "yarn.lock"})]))
        else:
            detections.append(BuildSystemDetection("npm", DetectionConfidence.INFERRED,
                                                     [Evidence("manifest_file", {"file": "package.json"})]))

        npm_deps = set(manifests.package_json.get("dependencies", {}) or {})
        npm_deps |= set(manifests.package_json.get("devDependencies", {}) or {})
        for bundler, dep_names, config_names in (
            ("Vite", ("vite",), ("vite.config.js", "vite.config.ts", "vite.config.mjs")),
            ("Webpack", ("webpack",), ("webpack.config.js", "webpack.config.ts")),
            ("Rollup", ("rollup",), ("rollup.config.js", "rollup.config.ts")),
            ("Turbopack", (), ("turbo.json",)),
            ("Angular CLI", ("@angular/cli",), ("angular.json",)),
        ):
            matched_deps = npm_deps & set(dep_names)
            matched_config = manifests.by_name(*config_names)
            if not matched_deps and not matched_config:
                continue
            evidence = []
            if matched_deps:
                evidence.append(Evidence("dependency", {"source": "package.json", "matched": sorted(matched_deps)}))
            if matched_config:
                evidence.append(Evidence("config_file", {"matched": sorted(f.relative for f in matched_config)}))
            detections.append(BuildSystemDetection(bundler, DetectionConfidence.DETECTED, evidence))

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

    if manifests.by_name("CMakeLists.txt"):
        detections.append(BuildSystemDetection("cmake", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "CMakeLists.txt"})]))
    if manifests.by_name("meson.build"):
        detections.append(BuildSystemDetection("meson", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "meson.build"})]))
    if manifests.by_name("WORKSPACE", "BUILD.bazel"):
        detections.append(BuildSystemDetection("bazel", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "WORKSPACE/BUILD.bazel"})]))
    if manifests.conanfile_texts:
        detections.append(BuildSystemDetection("conan", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "conanfile.txt/conanfile.py"})]))
    if manifests.by_name("vcpkg.json"):
        detections.append(BuildSystemDetection("vcpkg", DetectionConfidence.DETECTED,
                                                 [Evidence("manifest_file", {"file": "vcpkg.json"})]))
    if not any(d.name in ("cmake", "meson", "bazel") for d in detections) and manifests.by_name("Makefile", "makefile", "GNUmakefile"):
        detections.append(BuildSystemDetection("make", DetectionConfidence.INFERRED,
                                                 [Evidence("manifest_file", {"file": "Makefile"})]))

    return detections
