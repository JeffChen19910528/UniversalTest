"""Config dataclass tree mirroring the `universal-test.yaml` shape (skill.md §18).

The tool must run with near-zero configuration: `load_config()` with no
arguments (or pointed at a project with no config file) returns safe
defaults — nothing here enables an intrusive or destructive behavior.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from universal_test.core.errors import ConfigurationError

CONFIG_FILENAME = "universal-test.yaml"


@dataclass
class ProjectConfig:
    name: str | None = None


@dataclass
class AssessmentConfig:
    enabled: bool = True


@dataclass
class FunctionalConfig:
    enabled: bool = True


@dataclass
class PerformanceConfig:
    """Performance testing is opt-in and requires an explicit target (skill.md §4.2)."""

    enabled: bool = False
    target: str | None = None
    concurrency: list[int] = field(default_factory=lambda: [1, 10])
    duration_seconds: int = 30
    thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class DatabaseConfig:
    """Read-only by default; never enables destructive SQL (skill.md §4.2, §15)."""

    enabled: bool = False


@dataclass
class SecurityConfig:
    enabled: bool = False


MAX_BROWSER_TIMEOUT_SECONDS = 120.0  # hard ceiling, independent of configuration,
                                      # same "config can never request unbounded waits" rule
                                      # `CiConfig`/`testing/performance/planner.py` already enforce.
MAX_BROWSER_TEST_TIMEOUT_SECONDS = MAX_BROWSER_TIMEOUT_SECONDS * 5  # the TestCase wall-clock ceiling
_MIN_BROWSER_TIMEOUT_SECONDS = 1.0


def _sanitize_timeout_seconds(value: object, *, default: float, cap: float) -> float:
    """Clamp a browser timeout to `[1.0, cap]`, falling back to `default` for
    anything that isn't a finite, sane number (NaN/+-infinity/non-numeric) --
    Phase 9 hardening: `min(float(nan), cap)` etc. previously "happened to"
    floor to 1.0 via Python's NaN comparison quirks rather than by explicit,
    documented intent. `0`, negative values, and absurdly large values are
    still accepted as *input* but clamped, never rejected outright, since a
    config typo should degrade to a safe bound, not crash the whole run.
    """
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return max(_MIN_BROWSER_TIMEOUT_SECONDS, min(numeric, cap))


@dataclass
class BrowserConfig:
    """Browser/UI functional testing (Phase 9). Disabled by default and requires
    an explicit target (skill.md §4.2) -- mirrors `PerformanceConfig`'s shape.
    Every timeout is hard-capped in `__post_init__` regardless of what a project
    configures, so a config file alone can never produce an unbounded browser wait.
    Neither the CLI, GUI, nor an environment variable has any path that bypasses
    this clamp -- every caller constructs a `BrowserConfig` (directly or via
    `load_config()`), and this is the only place these fields are ever set.
    """

    enabled: bool = False
    browser: str = "chromium"
    headless: bool = True
    navigation_timeout_seconds: float = 15.0
    action_timeout_seconds: float = 10.0
    test_timeout_seconds: float = 60.0
    allow_external: bool = False
    screenshots: bool = False

    def __post_init__(self) -> None:
        self.navigation_timeout_seconds = _sanitize_timeout_seconds(
            self.navigation_timeout_seconds, default=15.0, cap=MAX_BROWSER_TIMEOUT_SECONDS,
        )
        self.action_timeout_seconds = _sanitize_timeout_seconds(
            self.action_timeout_seconds, default=10.0, cap=MAX_BROWSER_TIMEOUT_SECONDS,
        )
        self.test_timeout_seconds = _sanitize_timeout_seconds(
            self.test_timeout_seconds, default=60.0, cap=MAX_BROWSER_TEST_TIMEOUT_SECONDS,
        )


@dataclass
class AIConfig:
    """Off by default; never required for core function (skill.md §13)."""

    enabled: bool = False


_DEFAULT_REGRESSION_PERFORMANCE_THRESHOLDS: dict[str, float] = {
    "p50_percent": 10.0,
    "p90_percent": 10.0,
    "p95_percent": 10.0,
    "p99_percent": 10.0,
    "rps_percent": 10.0,
    "error_rate_absolute": 1.0,
}


@dataclass
class RegressionConfig:
    """Configurable regression tolerances (Phase 7 brief §8/§10) — the
    *comparator* itself (`regression/performance_compare.py`) takes these as
    a parameter and contains no hard-coded percentage; only the *default
    value* used when the project hasn't configured its own lives here, the
    same pattern `PerformanceConfig.thresholds` already established. Without
    some non-zero default tolerance, ordinary measurement noise (a P95 of
    200ms vs. 202ms) would be reported as a regression on every run — see
    brief §10.
    """

    performance: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_REGRESSION_PERFORMANCE_THRESHOLDS))


_DEFAULT_QUALITY_GATE_FAIL_ON: dict[str, list[str]] = {
    "regression": ["critical", "high"],
    "functional": ["failure"],
    "performance": ["threshold"],
}
_DEFAULT_QUALITY_GATE_WARN_ON: dict[str, list[str]] = {
    "regression": ["medium"],
    "database": ["schema_change"],
    "discovery": ["change"],
}


@dataclass
class QualityGateConfig:
    """Deterministic, configurable Quality Gate policy (Phase 8 brief §2/§3):
    a `category -> [values]` mapping, never scattered `if` statements. The
    *evaluator* (`quality_gate/engine.py`) takes this as data and contains
    no hard-coded policy; only the *default* values live here, mirroring
    `RegressionConfig`'s precedent one section above. `UNKNOWN`/
    `NOT_ASSESSED` never appear in the default `fail_on`/`warn_on` (brief
    §9: "不應該自動導致 CI failure") — a project must opt in explicitly
    (e.g. add `database: [not_assessed]`) to make either one block a build.
    """

    fail_on: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in _DEFAULT_QUALITY_GATE_FAIL_ON.items()})
    warn_on: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in _DEFAULT_QUALITY_GATE_WARN_ON.items()})


MAX_CI_RETRY_COUNT = 2  # hard ceiling, independent of configuration -- brief section 19:
                        # "最多提供非常有限的 retry" (at most a very limited retry)


@dataclass
class RetryConfig:
    count: int = 0


@dataclass
class CiConfig:
    """Bounded retry for `assess`'s functional-execution step only, and only
    when every executed request failed at the transport layer (a total
    wipeout, not a partial one) -- retrying a genuine assertion/threshold
    failure would be exactly the "用 retry 掩蓋真實 regression" the brief
    explicitly warns against (§19). `retry.count` is clamped to
    `MAX_CI_RETRY_COUNT` regardless of what a project configures, the same
    "hard ceiling independent of CLI/config validation" pattern
    `testing/performance/planner.py` already established for Phase 4.
    """

    retry: RetryConfig = field(default_factory=RetryConfig)

    def __post_init__(self) -> None:
        if isinstance(self.retry, dict):
            self.retry = RetryConfig(count=self.retry.get("count", 0))
        self.retry.count = max(0, min(int(self.retry.count), MAX_CI_RETRY_COUNT))


@dataclass
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    assessment: AssessmentConfig = field(default_factory=AssessmentConfig)
    functional: FunctionalConfig = field(default_factory=FunctionalConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    regression: RegressionConfig = field(default_factory=RegressionConfig)
    quality_gate: QualityGateConfig = field(default_factory=QualityGateConfig)
    ci: CiConfig = field(default_factory=CiConfig)


_SECTION_TYPES: dict[str, type] = {
    "project": ProjectConfig,
    "assessment": AssessmentConfig,
    "functional": FunctionalConfig,
    "performance": PerformanceConfig,
    "database": DatabaseConfig,
    "security": SecurityConfig,
    "browser": BrowserConfig,
    "ai": AIConfig,
    "regression": RegressionConfig,
    "quality_gate": QualityGateConfig,
    "ci": CiConfig,
}


def _build_section(section_type: type, data: dict) -> Any:
    valid_keys = {f.name for f in fields(section_type)}
    unknown = set(data) - valid_keys
    defaults = section_type()
    filtered = {}
    for key, value in data.items():
        if key not in valid_keys:
            continue
        default_value = getattr(defaults, key)
        if isinstance(default_value, dict) and isinstance(value, dict):
            # Dict-valued fields (e.g. performance.thresholds, regression.performance)
            # are merged over their defaults, not replaced wholesale -- otherwise
            # overriding one threshold would silently drop every other default one.
            filtered[key] = {**default_value, **value}
        else:
            filtered[key] = value
    instance = section_type(**filtered)
    return instance, unknown


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    project_path: str | Path | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Load configuration with safe defaults.

    Resolution order (later wins): dataclass defaults -> config file (explicit
    `config_path`, or `<project_path>/universal-test.yaml` if present) -> `overrides`.
    Unknown top-level keys/sections are ignored (forward-compatible, non-fatal);
    unknown keys within a known section are also ignored rather than raising,
    since a stray key should never prevent a safe default run.
    """
    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path)
    elif project_path is not None:
        candidate = Path(project_path) / CONFIG_FILENAME
        if candidate.is_file():
            resolved_path = candidate

    raw: dict[str, Any] = {}
    if resolved_path is not None:
        if not resolved_path.is_file():
            raise ConfigurationError(f"Config file not found: {resolved_path}")
        try:
            loaded = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Invalid YAML in {resolved_path}: {exc}") from exc
        if loaded is not None:
            if not isinstance(loaded, dict):
                raise ConfigurationError(
                    f"Config file {resolved_path} must contain a mapping at the top level"
                )
            raw = loaded

    if overrides:
        raw = _deep_merge(raw, overrides)

    config = Config()
    for section_name, section_type in _SECTION_TYPES.items():
        section_data = raw.get(section_name)
        if section_data is None:
            continue
        if not isinstance(section_data, dict):
            raise ConfigurationError(
                f"Config section {section_name!r} must be a mapping, got {type(section_data).__name__}"
            )
        instance, _unknown = _build_section(section_type, section_data)
        setattr(config, section_name, instance)

    _validate_quality_gate_policy(config.quality_gate)
    return config


def _validate_quality_gate_policy(quality_gate: QualityGateConfig) -> None:
    """`fail_on`/`warn_on` drive CI exit codes directly (Phase 8) -- a
    malformed policy must be a clear, immediate `ConfigurationError` (exit 2
    at the CLI), never a later `AttributeError`/silent no-op deep inside gate
    evaluation."""
    for policy_name, policy in (("fail_on", quality_gate.fail_on), ("warn_on", quality_gate.warn_on)):
        if not isinstance(policy, dict):
            raise ConfigurationError(
                f"quality_gate.{policy_name} must be a mapping of category -> [values], "
                f"got {type(policy).__name__}"
            )
        for category, values in policy.items():
            if not isinstance(category, str):
                raise ConfigurationError(f"quality_gate.{policy_name} keys must be strings, got {category!r}")
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ConfigurationError(
                    f"quality_gate.{policy_name}.{category} must be a list of strings, got {values!r}"
                )


assert is_dataclass(Config)  # guard: keep Config a plain dataclass tree (no hidden state)
