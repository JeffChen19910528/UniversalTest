"""Browser-output redaction -- reuses `core.redaction` exclusively (spec §40-§41).

No second redaction system. Also enforces spec §41: browser storage
(localStorage/sessionStorage/cookies/IndexedDB) is never read into evidence
in the first place, so there is nothing to redact -- the executor simply
never collects it.
"""

from __future__ import annotations

from typing import Any

from universal_test.core.redaction import redact, redact_mapping


def redact_console_message(message: dict[str, Any]) -> dict[str, Any]:
    return redact_mapping(message)


def redact_network_failure(failure: dict[str, Any]) -> dict[str, Any]:
    return redact_mapping(failure)


def redact_text(text: str) -> str:
    return redact(text)


def redact_context(context: dict[str, Any]) -> dict[str, Any]:
    """Redact a full browser execution context dict before it is handed to
    the AssertionEngine's evidence or persisted anywhere."""
    return redact_mapping(context)
