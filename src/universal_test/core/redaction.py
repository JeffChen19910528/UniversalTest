"""Secret redaction, applied to anything that may reach logs, reports, or exceptions.

Per skill.md §26, the tool must never print passwords, tokens, API keys,
connection-string credentials, or private keys. Patterns are intentionally
broad (favor over-redaction) and extensible via `register_pattern`.
"""

from __future__ import annotations

import re

REDACTED = "***REDACTED***"

# key=value / key: value style secrets (config files, env vars, query strings, logs).
# "cookie"/"set-cookie" is deliberately included -- a Set-Cookie response header
# (e.g. a session ID) is exactly as sensitive as a bearer token and was previously
# NOT covered by this pattern at all (V1 hardening audit finding).
_KEY_VALUE_PATTERN = re.compile(
    r"""(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|
        authorization|auth|private[_-]?key|client[_-]?secret|
        set[_-]?cookie|cookie)\b
        (\s*[:=]\s*)
        (?P<value>"[^"]*"|'[^']*'|Bearer\s+\S+|Basic\s+\S+|\S+)""",
    re.VERBOSE,
)

# connection strings with inline credentials, e.g. postgres://user:pass@host
_CONNECTION_STRING_PATTERN = re.compile(
    r"(?i)\b([a-z][a-z0-9+.\-]*://)([^:/\s@]+):([^@/\s]+)@"
)

# PEM-style private key blocks
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)

# key *names* considered sensitive when redacting structured data (dict/JSON), where
# the key and value are separate fields rather than one "key=value" string -- e.g. an
# HTTP response headers dict where the key is "Set-Cookie" and the value is the raw
# cookie string, which itself contains no "password"/"token"/etc keyword for the
# key=value pattern above to catch (V1 hardening audit finding).
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)^(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"authorization|auth|private[_-]?key|client[_-]?secret|set[_-]?cookie|cookie)$"
)

_extra_patterns: list[re.Pattern[str]] = []


def register_pattern(pattern: re.Pattern[str]) -> None:
    """Register an additional regex whose first match group (or whole match) is redacted."""
    _extra_patterns.append(pattern)


def redact(text: str) -> str:
    """Return `text` with known secret patterns replaced by a redaction marker."""
    if not text:
        return text

    def _replace_kv(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    result = _KEY_VALUE_PATTERN.sub(_replace_kv, text)
    result = _CONNECTION_STRING_PATTERN.sub(rf"\1{REDACTED}:{REDACTED}@", result)
    result = _PRIVATE_KEY_BLOCK_PATTERN.sub(REDACTED, result)

    for pattern in _extra_patterns:
        result = pattern.sub(REDACTED, result)

    return result


def redact_mapping(data: dict) -> dict:
    """Recursively redact a dict, treating sensitive *keys* as fully-redacted
    (their value carries no key=value text for `redact()` to pattern-match
    against), and running `redact()` over other string values in case a
    secret is embedded in free text.
    """
    redacted: dict = {}
    for key, value in data.items():
        if isinstance(key, str) and _SENSITIVE_KEY_PATTERN.match(key):
            redacted[key] = REDACTED if value is not None else None
        elif isinstance(value, str):
            redacted[key] = redact(value)
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_mapping(item) if isinstance(item, dict)
                else redact(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted
