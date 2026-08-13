"""Browser test definition model (spec §12-§14).

Deliberately reuses Core's `TestCase`/`AssertionSpec` (`core/models/test_spec.py`)
rather than inventing a parallel model -- browser-specific data (the ordered
action list) lives in `TestTarget.extra["steps"]`, the existing escape hatch
`TestTarget` already provides. `BrowserStep`/`BrowserSelector` are typed
helpers for building that `extra["steps"]` list; `to_dict()`/`from_dict()`
round-trip through the same plain-dict shape `TestCase.to_dict()` already
serializes, so no new report/serialization code is needed elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from universal_test.core.orchestration.orchestrator import RunResult

# Conservative initial action set (spec §13) -- no arbitrary JS execution.
ALLOWED_ACTIONS = frozenset({
    "navigate", "click", "fill", "select", "check", "uncheck", "press", "wait_for",
})

# Robust selector strategies (spec §14) -- brittle XPath is deliberately not the default.
ALLOWED_SELECTOR_TYPES = frozenset({"role", "label", "text", "placeholder", "test_id", "css"})


@dataclass(frozen=True)
class BrowserSelector:
    type: str  # one of ALLOWED_SELECTOR_TYPES
    value: str
    role: str | None = None  # only used when type == "role" (e.g. "button")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type, "value": self.value}
        if self.role is not None:
            data["role"] = self.role
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "BrowserSelector":
        return BrowserSelector(type=data["type"], value=data.get("value", ""), role=data.get("role"))


@dataclass(frozen=True)
class BrowserStep:
    action: str  # one of ALLOWED_ACTIONS
    selector: BrowserSelector | None = None
    value: str | None = None  # fill text / select option / press key / wait_for timeout marker
    timeout_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"action": self.action}
        if self.selector is not None:
            data["selector"] = self.selector.to_dict()
        if self.value is not None:
            data["value"] = self.value
        if self.timeout_seconds is not None:
            data["timeout_seconds"] = self.timeout_seconds
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "BrowserStep":
        selector_data = data.get("selector")
        return BrowserStep(
            action=data["action"],
            selector=BrowserSelector.from_dict(selector_data) if selector_data else None,
            value=data.get("value"),
            timeout_seconds=data.get("timeout_seconds"),
        )


@dataclass
class BrowserRunResult:
    """Mirrors `adapters/rest/adapter.py::RestRunResult`'s shape: honest,
    explicit states rather than a bare pass/fail."""

    test_cases: list = field(default_factory=list)
    run_result: RunResult | None = None
    executed: bool = False
    no_target_reason: str | None = None
    not_assessed_reason: str | None = None  # Playwright/browser unavailable
    target: str | None = None
    browser: str | None = None
    screenshots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "run_result": self.run_result.to_dict() if self.run_result else None,
            "executed": self.executed,
            "no_target_reason": self.no_target_reason,
            "not_assessed_reason": self.not_assessed_reason,
            "target": self.target,
            "browser": self.browser,
            "screenshots": list(self.screenshots),
        }
