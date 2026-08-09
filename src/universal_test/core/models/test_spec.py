"""Framework-independent test specification (skill.md §16).

The Core test engine consumes only this representation — never a
framework/adapter-specific object — so the same TestCase can run against any
adapter that implements `execute()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TestTarget:
    """Where/how a test executes. `adapter` selects which adapter's `execute()` runs it."""

    adapter: str
    method: str | None = None
    path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssertionSpec:
    """Declarative assertion: a `type` name the AssertionEngine resolves, plus params."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestCase:
    """One conservative, generated (or hand-written) test."""

    id: str
    name: str
    type: str  # e.g. "functional", "performance"
    target: TestTarget
    request: dict[str, Any] = field(default_factory=dict)
    assertions: list[AssertionSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "target": {
                "adapter": self.target.adapter,
                "method": self.target.method,
                "path": self.target.path,
                **self.target.extra,
            },
            "request": self.request,
            "assertions": [
                {"type": a.type, **a.params} for a in self.assertions
            ],
        }
