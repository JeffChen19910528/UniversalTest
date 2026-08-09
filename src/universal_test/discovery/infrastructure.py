"""Infrastructure detection: files/directories only, never invoked or started."""

from __future__ import annotations

from pathlib import Path

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile, read_text_safe
from universal_test.discovery.models import InfrastructureDetection

_MAX_YAML_SCAN = 25  # bound how many yaml files we peek into for k8s evidence


def detect_infrastructure(files: list[ScannedFile]) -> list[InfrastructureDetection]:
    detections: list[InfrastructureDetection] = []

    dockerfiles = [f for f in files if Path(f.relative).name.lower().startswith("dockerfile")]
    if dockerfiles:
        detections.append(InfrastructureDetection(
            "Docker", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in dockerfiles]})],
        ))

    compose_files = [
        f for f in files
        if Path(f.relative).name.lower() in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    ]
    if compose_files:
        detections.append(InfrastructureDetection(
            "Docker Compose", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in compose_files]})],
        ))

    workflow_files = [f for f in files if f.relative.lower().startswith(".github/workflows/") and f.extension in (".yml", ".yaml")]
    if workflow_files:
        detections.append(InfrastructureDetection(
            "GitHub Actions", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in workflow_files]})],
        ))

    gitlab_ci = [f for f in files if Path(f.relative).name.lower() == ".gitlab-ci.yml"]
    if gitlab_ci:
        detections.append(InfrastructureDetection(
            "GitLab CI", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in gitlab_ci]})],
        ))

    jenkinsfiles = [f for f in files if Path(f.relative).name.lower() == "jenkinsfile"]
    if jenkinsfiles:
        detections.append(InfrastructureDetection(
            "Jenkins", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in jenkinsfiles]})],
        ))

    azure_pipelines = [f for f in files if Path(f.relative).name.lower() in ("azure-pipelines.yml", "azure-pipelines.yaml")]
    if azure_pipelines:
        detections.append(InfrastructureDetection(
            "Azure Pipelines", DetectionConfidence.DETECTED,
            [Evidence("file", {"files": [f.relative for f in azure_pipelines]})],
        ))

    terraform_files = [f for f in files if f.extension == ".tf"]
    if terraform_files:
        detections.append(InfrastructureDetection(
            "Terraform", DetectionConfidence.DETECTED,
            [Evidence("file", {"count": len(terraform_files), "sample": [f.relative for f in terraform_files[:5]]})],
        ))

    k8s_hits, k8s_confidence = _detect_kubernetes(files)
    if k8s_hits:
        detections.append(InfrastructureDetection(
            "Kubernetes", k8s_confidence, [Evidence("manifest_content", {"files": k8s_hits})],
        ))

    return detections


def _detect_kubernetes(files: list[ScannedFile]) -> tuple[list[str], DetectionConfidence]:
    # cheap directory-name signal first — a dedicated k8s/kubernetes directory is strong evidence
    dir_hits = [f.relative for f in files if any(part.lower() in ("k8s", "kubernetes") for part in Path(f.relative).parts[:-1])]
    if dir_hits:
        return sorted(set(dir_hits))[:10], DetectionConfidence.DETECTED

    # bounded content scan: yaml files containing both apiVersion: and kind: (weaker, heuristic signal)
    candidates = [
        f for f in files
        if f.extension in (".yml", ".yaml")
        and Path(f.relative).name.lower() not in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    ][:_MAX_YAML_SCAN]
    hits = []
    for f in candidates:
        text = read_text_safe(f.path)
        if text and "apiVersion:" in text and "kind:" in text:
            hits.append(f.relative)
    return hits, DetectionConfidence.INFERRED
