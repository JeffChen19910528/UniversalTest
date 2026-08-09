"""API/service evidence detection. Discovery only — no endpoint parsing or
requests; real OpenAPI parsing is Phase 3 (skill.md §7, this project's
ROADMAP.md).
"""

from __future__ import annotations

from pathlib import Path

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile, read_text_safe
from universal_test.discovery.manifests import ManifestBundle, npm_dependency_names, python_dependency_names
from universal_test.discovery.models import ApiDetection

OPENAPI_NAME_HINTS = ("openapi", "swagger")  # reused by adapters/rest for spec-file discovery
_GRAPHQL_PACKAGE_HINTS = {"graphql", "apollo-server", "apollo-server-express", "graphene", "strawberry-graphql"}
_ROUTE_DIR_HINTS = {"routes", "controllers", "api", "endpoints"}


def detect_apis(files: list[ScannedFile], manifests: ManifestBundle) -> list[ApiDetection]:
    detections: list[ApiDetection] = []

    openapi_candidates = [
        f for f in files
        if f.extension in (".yaml", ".yml", ".json")
        and any(hint in Path(f.relative).name.lower() for hint in OPENAPI_NAME_HINTS)
    ]
    confirmed_openapi = []
    for f in openapi_candidates:
        text = read_text_safe(f.path)
        if text and ("openapi:" in text or '"openapi"' in text or "swagger:" in text or '"swagger"' in text):
            confirmed_openapi.append(f.relative)
    if confirmed_openapi:
        detections.append(ApiDetection(
            name="OpenAPI/Swagger", kind="openapi", confidence=DetectionConfidence.DETECTED,
            evidence=[Evidence("file_content", {"files": confirmed_openapi})],
        ))
    elif openapi_candidates:
        detections.append(ApiDetection(
            name="OpenAPI/Swagger", kind="openapi", confidence=DetectionConfidence.INFERRED,
            evidence=[Evidence("filename", {"files": [f.relative for f in openapi_candidates]})],
        ))

    graphql_files = [f for f in files if f.extension == ".graphql" or f.relative.lower().endswith(".graphqls")]
    npm_deps = npm_dependency_names(manifests)
    python_deps = python_dependency_names(manifests)
    graphql_deps = (npm_deps | python_deps) & _GRAPHQL_PACKAGE_HINTS
    if graphql_files or graphql_deps:
        evidence = []
        if graphql_files:
            evidence.append(Evidence("file", {"files": [f.relative for f in graphql_files[:10]]}))
        if graphql_deps:
            evidence.append(Evidence("dependency", {"matched": sorted(graphql_deps)}))
        detections.append(ApiDetection(
            name="GraphQL", kind="graphql", confidence=DetectionConfidence.DETECTED, evidence=evidence,
        ))

    route_dir_hits = sorted({
        "/".join(Path(f.relative).parts[:i + 1])
        for f in files
        for i, part in enumerate(Path(f.relative).parts[:-1])
        if part.lower() in _ROUTE_DIR_HINTS
    })
    if route_dir_hits:
        detections.append(ApiDetection(
            name="REST-style routing", kind="rest_config", confidence=DetectionConfidence.INFERRED,
            evidence=[Evidence("directory", {"directories": route_dir_hits[:10]})],
        ))

    return detections
