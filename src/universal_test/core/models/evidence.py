"""Structured evidence — every finding/result must carry this, never a bare verdict."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    """One piece of concrete, traceable evidence backing a result or finding.

    `type` is a short machine-readable tag (e.g. "http_response", "file",
    "config_value"); `data` holds the structured detail. Callers are
    responsible for redacting secrets in `data` before it is persisted or
    displayed (see core.redaction) — Evidence itself does not redact, since
    it doesn't know which fields are safe to show as-is.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data, "description": self.description}
