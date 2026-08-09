"""Potential-secret pattern scanning.

This only ever records *that* a pattern matched (file, line, pattern type) —
never the matched value (skill.md §26, Phase 2 brief). A pattern match is
evidence of a pattern, not a confirmed secret or a vulnerability finding;
callers must not upgrade `SecretFinding` into a security verdict.
"""

from __future__ import annotations

import re

from universal_test.core.models.enums import DetectionConfidence
from universal_test.discovery.filesystem import EXCLUDED_DIR_NAMES, ScannedFile, read_text_safe
from universal_test.discovery.models import SecretFinding

_PATTERNS: dict[str, re.Pattern[str]] = {
    "password": re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*(\S+)"),
    "api_key": re.compile(r"(?i)\b(api[_-]?key|apikey)\b\s*[:=]\s*(\S+)"),
    "token": re.compile(r"(?i)\b(token|access[_-]?token)\b\s*[:=]\s*(\S+)"),
    "secret": re.compile(r"(?i)\b(secret|client[_-]?secret)\b\s*[:=]\s*(\S+)"),
    "connection_string": re.compile(r"(?i)\b[a-z][a-z0-9+.\-]*://[^:/\s@]+:[^@/\s]+@"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

_PLACEHOLDER_VALUES = {
    "changeme", "change_me", "xxx", "xxxx", "xxxxx", "your_api_key", "your-api-key",
    "replace_me", "replaceme", "example", "test", "dummy", "placeholder", "todo",
    "<password>", "<api_key>", "<token>", "<secret>", "none", "null", "", "''",
}

# secrets scanning is inherently more sensitive than log redaction, so also skip
# obvious non-source/binary/lock files to keep signal-to-noise reasonable.
_SKIP_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".lock",
)
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml", "cargo.lock"}


def _is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("\"'").lower()
    return cleaned in _PLACEHOLDER_VALUES or not cleaned


def scan_for_secrets(files: list[ScannedFile]) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for f in files:
        if f.extension in _SKIP_SUFFIXES or f.path.name.lower() in _SKIP_NAMES:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in f.path.parts):
            continue
        text = read_text_safe(f.path)
        if not text:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_type, pattern in _PATTERNS.items():
                match = pattern.search(line)
                if not match:
                    continue
                if pattern_type in ("password", "api_key", "token", "secret"):
                    value = match.group(2)
                    if _is_placeholder(value):
                        continue
                findings.append(SecretFinding(
                    file=f.relative, line=line_number, pattern_type=pattern_type,
                    confidence=DetectionConfidence.INFERRED,
                ))
    return findings
