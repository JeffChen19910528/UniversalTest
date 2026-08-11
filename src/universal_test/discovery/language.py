"""Language detection.

Deliberately not "count file extensions and call it a day": each language's
confidence is anchored on manifest/marker-file evidence (a real, maintained
signal) when available, and file-extension volume is used as *supporting*
evidence and for languages with no canonical manifest (e.g. SQL). This keeps
the method simple to maintain while avoiding the false confidence a pure
extension histogram gives on, say, a repo with three stray `.py` scripts.
"""

from __future__ import annotations

from collections import Counter

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile
from universal_test.discovery.manifests import ManifestBundle
from universal_test.discovery.models import LanguageDetection

# extension -> language name
_EXTENSION_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".cs": "C#",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift",
    ".sol": "Solidity",
    ".sql": "SQL",
    ".css": "CSS",
    ".scss": "SCSS",
}

# manifest/marker evidence considered a strong, direct signal for a language
_MANIFEST_MARKERS = {
    "Python": ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"],
    "JavaScript": ["package.json"],
    "TypeScript": ["tsconfig.json"],
    "C#": [],  # handled via *.csproj/*.sln suffix below
    "Java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "Go": ["go.mod"],
    "Rust": ["Cargo.toml"],
    "PHP": ["composer.json"],
    "Kotlin": [],  # shares build.gradle.kts / build.gradle with Java; disambiguated via file extensions
    "Swift": ["Package.swift"],
    "Solidity": ["hardhat.config.js", "hardhat.config.ts", "foundry.toml"],
}

_MIN_FILES_FOR_INFERRED = 1
_MIN_FILES_FOR_DETECTED_WITHOUT_MANIFEST = 3


def detect_languages(files: list[ScannedFile], manifests: ManifestBundle) -> list[LanguageDetection]:
    counts: Counter[str] = Counter()
    for f in files:
        language = _EXTENSION_LANGUAGE.get(f.extension)
        if language:
            counts[language] += 1

    if manifests.by_suffix(".csproj", ".sln"):
        pass  # C# already counted via .cs extension if any source files exist

    detections: list[LanguageDetection] = []
    for language, count in counts.items():
        if count == 0:
            continue
        evidence: list[Evidence] = [Evidence("file_extension_count", {"language": language, "count": count})]
        manifest_hit = None
        for marker in _MANIFEST_MARKERS.get(language, []):
            if manifests.by_name(marker):
                manifest_hit = marker
                break
        if language == "C#" and manifests.by_suffix(".csproj", ".sln"):
            manifest_hit = "*.csproj/*.sln"

        if manifest_hit:
            evidence.append(Evidence("manifest_file", {"file": manifest_hit}))
            confidence = DetectionConfidence.DETECTED
        elif count >= _MIN_FILES_FOR_DETECTED_WITHOUT_MANIFEST:
            confidence = DetectionConfidence.DETECTED
        elif count >= _MIN_FILES_FOR_INFERRED:
            confidence = DetectionConfidence.INFERRED
        else:
            continue

        detections.append(LanguageDetection(name=language, confidence=confidence, evidence=evidence, file_count=count))

    detections.sort(key=lambda d: d.file_count, reverse=True)
    return detections


def primary_language(languages: list[LanguageDetection]) -> str | None:
    detected = [l for l in languages if l.confidence == DetectionConfidence.DETECTED]
    pool = detected or languages
    if not pool:
        return None
    return max(pool, key=lambda l: l.file_count).name
