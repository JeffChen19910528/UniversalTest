"""Web Test Scenario domain model (Phase 11 spec §5-§9).

Framework-independent and fully serializable -- no Playwright objects, no
live browser handles, only dataclasses/enums/plain values, matching
`core/models/test_spec.py`'s own design rule. Deliberately reuses
`adapters/browser/models.py::BrowserSelector` (same selector types the
Browser Adapter already supports) rather than inventing a second selector
system, and maps every scenario action onto either the existing
`ALLOWED_ACTIONS` (real browser actions) or the existing browser
`AssertionEngine` evaluator names (`ASSERT_ACTIONS`) -- no second
assertion vocabulary either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from universal_test.adapters.browser.models import ALLOWED_ACTIONS, BrowserSelector

# assert_* scenario actions -> the existing browser assertion type each one evaluates
# to (see adapters/browser/assertions.py) -- no second assertion engine (spec §8).
ASSERT_ACTION_MAP: dict[str, str] = {
    "assert_visible": "visible",
    "assert_hidden": "hidden",
    "assert_text": "text_contains",
    "assert_text_equals": "text_equals",
    "assert_value": "input_value",
    "assert_attribute": "attribute_equals",
    "assert_url": "url_contains",
    "assert_url_equals": "url_equals",
    "assert_title": "page_title",
    "assert_count": "element_count",
    "assert_enabled": "enabled",
    "assert_disabled": "disabled",
    "assert_checked": "checked",
}

# Selector-free assert actions (evaluate page-level state, not one element).
_NO_SELECTOR_ASSERT_ACTIONS = frozenset({"assert_url", "assert_url_equals", "assert_title"})

# Action-name aliases accepted from scenario YAML for readability/portability
# (spec §7's own examples use "select_option"/"wait"; the existing Browser
# Adapter action set spells these "select"/"wait_for" -- aliasing here avoids
# forcing scenario authors to know that internal naming detail).
ACTION_ALIASES: dict[str, str] = {"select_option": "select", "wait": "wait_for"}

ALL_ACTIONS = frozenset(ALLOWED_ACTIONS) | frozenset(ASSERT_ACTION_MAP) | frozenset(ACTION_ALIASES)


def normalize_action(action: str) -> str:
    """Resolves an alias to its canonical action name; unknown actions pass
    through unchanged so validation can report them as such."""
    return ACTION_ALIASES.get(action, action)


def _parse_selector(selector_data: dict[str, Any]) -> BrowserSelector:
    """Wraps `BrowserSelector.from_dict()` (the existing, shared selector
    model -- spec §9 forbids a second one) with one scenario-authoring
    convenience: a `role` selector's accessible-name field may be spelled
    `name` (matching this project's own scenario examples/docs) as an
    alias for the underlying model's `value` field, since "value" reads
    oddly for what is conceptually a role's accessible *name*.
    """
    if selector_data.get("type") == "role" and "name" in selector_data and "value" not in selector_data:
        selector_data = {**selector_data, "value": selector_data["name"]}
    return BrowserSelector.from_dict(selector_data)


@dataclass(frozen=True)
class ScenarioStep:
    """One scenario step -- either a real browser action (navigate/click/
    fill/select/check/uncheck/press/wait_for) or an `assert_*` step
    evaluated via the existing browser `AssertionEngine`. Never both in one
    step, by design: this keeps per-step PASS/FAIL/ERROR reporting
    unambiguous (spec §21-§22) -- an action step's status answers "did the
    operation succeed", an assertion step's status answers "was the
    expected condition true".
    """

    id: str
    action: str
    selector: BrowserSelector | None = None
    url: str | None = None  # navigate target (relative preferred, spec §41)
    value: str | None = None  # fill text / select option / press key / wait_for state /
    #                           assert_text(_equals) needle / assert_value/url(_equals)/title expected
    value_env: str | None = None  # secret-safe source for `value` (spec §10/§42) -- resolved only
    #                                at the last possible moment, during execution, never at load/validate/dry-run time
    attribute: str | None = None  # assert_attribute's attribute name
    count_equals: int | None = None
    count_min: int | None = None
    count_max: int | None = None
    timeout_seconds: float | None = None
    description: str | None = None

    @property
    def is_assertion(self) -> bool:
        return normalize_action(self.action) in ASSERT_ACTION_MAP

    def requires_selector(self) -> bool:
        canonical = normalize_action(self.action)
        if canonical in _NO_SELECTOR_ASSERT_ACTIONS:
            return False
        if canonical in ASSERT_ACTION_MAP:
            return True
        return canonical in ("click", "fill", "select", "check", "uncheck", "press")

    def public_dict(self) -> dict[str, Any]:
        """Serialization safe for reports/GUI/logs: never the resolved
        `value_env` secret, never a literal `value` on a step that sources
        it from an environment variable (spec §35 -- "Fill password /
        source: TEST_PASSWORD", never the plaintext). A literal `value` on
        a step that does NOT use `value_env` is shown as-is (the author's
        own non-secret test data, e.g. a search term) but still passes
        through `core.redaction.redact()` at the report-rendering layer as
        defense in depth.
        """
        data: dict[str, Any] = {"id": self.id, "action": self.action}
        if self.description:
            data["description"] = self.description
        if self.selector is not None:
            data["selector"] = self.selector.to_dict()
        if self.url is not None:
            data["url"] = self.url
        if self.value_env is not None:
            data["value_env"] = self.value_env
        elif self.value is not None:
            data["value"] = self.value
        if self.attribute is not None:
            data["attribute"] = self.attribute
        if self.count_equals is not None:
            data["count_equals"] = self.count_equals
        if self.count_min is not None:
            data["count_min"] = self.count_min
        if self.count_max is not None:
            data["count_max"] = self.count_max
        if self.timeout_seconds is not None:
            data["timeout_seconds"] = self.timeout_seconds
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ScenarioStep":
        selector_data = data.get("selector")
        return ScenarioStep(
            id=str(data.get("id", "")),
            action=str(data.get("action", "")),
            selector=_parse_selector(selector_data) if selector_data else None,
            url=data.get("url"),
            value=data.get("value"),
            value_env=data.get("value_env"),
            attribute=data.get("attribute"),
            count_equals=data.get("count_equals"),
            count_min=data.get("count_min"),
            count_max=data.get("count_max"),
            timeout_seconds=data.get("timeout_seconds"),
            description=data.get("description"),
        )


@dataclass(frozen=True)
class WebScenario:
    id: str
    name: str
    description: str | None = None
    target: str | None = None  # optional scenario-level default; CLI/GUI --target always wins
    steps: list[ScenarioStep] = field(default_factory=list)
    timeout_seconds: float | None = None  # scenario-level wall-clock budget (spec §20)
    metadata: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
            "steps": [s.public_dict() for s in self.steps],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebScenario":
        return WebScenario(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=data.get("description"),
            target=data.get("target"),
            steps=[ScenarioStep.from_dict(s) for s in data.get("steps", [])],
            timeout_seconds=data.get("timeout_seconds"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ScenarioCollection:
    """All scenarios loaded from one scenario file (spec §12/§27)."""

    source_path: str
    scenarios: list[WebScenario] = field(default_factory=list)

    def get(self, scenario_id: str) -> WebScenario | None:
        return next((s for s in self.scenarios if s.id == scenario_id), None)
