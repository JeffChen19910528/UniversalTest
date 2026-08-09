"""Application Service Layer (Post-V1 GUI brief §4).

A thin orchestration facade the GUI (and, in principle, any future
non-CLI front end) calls instead of re-implementing `cli/main.py`'s
`_run_pipeline`/`_run_assess` logic. Every step below delegates to the
same Phase 1-8 Core/adapter functions the CLI already uses — this module
adds *only*: a request/result shape, structured progress events, and the
GUI-specific safety gate (`performance_confirmed`) that replaces the CLI's
interactive `input()` confirmation prompt with an explicit boolean the GUI
must have already obtained via its own confirmation checkbox
(brief §25 — "不要在 GUI 中默默等價於 --yes").

Nothing here touches discovery/testing/assessment internals; it only calls
their public entry points, exactly like `cli/main.py` does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from universal_test.adapters.database import discover as db_discover
from universal_test.adapters.database import load_database_profile
from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.adapters.rest.adapter import run as rest_run
from universal_test.adapters.rest.auth import resolve_auth_from_env
from universal_test.adapters.rest.discovery_bridge import MultipleSpecsFoundError
from universal_test.adapters.rest.performance import resolve_auth_headers, resolve_performance_target
from universal_test.adapters.rest.performance_executor import make_performance_executor
from universal_test.application.events import (
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_SKIPPED,
    PHASE_STARTED,
    STAGE_ASSESSMENT,
    STAGE_DATABASE_ASSESSMENT,
    STAGE_FUNCTIONAL_TEST,
    STAGE_PERFORMANCE_TEST,
    STAGE_PROJECT_SCAN,
    STAGE_REGRESSION,
    STAGE_REPORT_GENERATION,
    ProgressEvent,
)
from universal_test.assessment import build_assessment
from universal_test.assessment.models import ProjectAssessment
from universal_test.core.configuration import Config, load_config
from universal_test.core.errors import ConfigurationError, DiscoveryError, OpenApiError
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery import discover
from universal_test.discovery.models import ProjectModel
from universal_test.quality_gate import QualityGatePolicy, evaluate as qg_evaluate
from universal_test.quality_gate.models import QualityGateResult
from universal_test.regression import build_snapshot, compare as regression_compare, load_baseline
from universal_test.regression.models import RegressionSummary
from universal_test.reporting import AssessReportBundle
from universal_test.reporting import to_html as report_to_html
from universal_test.reporting import to_json as report_to_json
from universal_test.reporting import to_markdown as report_to_markdown
from universal_test.testing.performance import PerformanceRunner, build_load_profile
from universal_test.testing.performance.models import PerformanceResult

OnEvent = Callable[[ProgressEvent], None]

_REPORT_RENDERERS = {"json": report_to_json, "markdown": report_to_markdown, "html": report_to_html}
_REPORT_EXTENSIONS = {"json": "json", "markdown": "md", "html": "html"}


@dataclass
class AssessmentRequest:
    """Everything one GUI "開始專案健檢" click needs. Every field defaults to
    the safest possible value (brief §7's "safe defaults" simple-mode
    checkboxes) — nothing here is ever inferred from OpenAPI `servers:` or
    any other guess (brief §6).
    """

    project_path: str
    target: str | None = None

    run_functional: bool = True
    run_performance: bool = False
    # Explicit GUI checkbox confirmation (brief §25); performance never runs
    # without both `run_performance` AND this being True.
    performance_confirmed: bool = False
    run_database: bool = False
    database_profile_path: str | None = None

    baseline_path: str | None = None
    output_dir: str | None = None
    report_formats: list[str] = field(default_factory=lambda: ["json", "markdown", "html"])

    # Advanced options (brief §8) -- all optional, hidden behind a GUI toggle.
    openapi_override: str | None = None
    timeout_seconds: float = 10.0
    perf_endpoint: str | None = None
    perf_method: str | None = None
    perf_profile: str = "load"
    perf_concurrency: list[int] | None = None
    perf_max_concurrency: int | None = None
    perf_requests: int | None = None
    perf_duration: float | None = None
    perf_stop_error_rate: float | None = None
    perf_stop_p95_ms: float | None = None

    bearer_token_env: str | None = None
    api_key_env: str | None = None
    api_key_header: str | None = None
    basic_auth_user_env: str | None = None
    basic_auth_pass_env: str | None = None


@dataclass
class AssessmentOutcome:
    model: ProjectModel
    run_result: RunResult | None
    functional_not_run_reason: str | None
    perf_result: PerformanceResult | None
    performance_not_run_reason: str | None
    database_result: DatabaseDiscoveryResult | None
    assessment: ProjectAssessment
    regression: RegressionSummary | None
    quality_gate: QualityGateResult
    bundle: AssessReportBundle
    report_paths: dict[str, str]


def _emit(on_event: OnEvent | None, stage: str, phase: str, message: str = "", **detail: Any) -> None:
    if on_event is not None:
        on_event(ProgressEvent(stage=stage, phase=phase, message=message, detail=detail))


def run_assessment(
    request: AssessmentRequest,
    on_event: OnEvent | None = None,
    config: Config | None = None,
) -> AssessmentOutcome:
    """Runs the full discovery + functional + performance + database +
    assessment + (optional) regression + report pipeline for one GUI
    "開始專案健檢" click, emitting `ProgressEvent`s as it goes (brief §9/§11).
    """
    if config is None:
        config = load_config(project_path=request.project_path, config_path=None)

    _emit(on_event, STAGE_PROJECT_SCAN, PHASE_STARTED, "Scanning project structure")
    model = discover(request.project_path)
    _emit(
        on_event, STAGE_PROJECT_SCAN, PHASE_COMPLETED, "Project structure analyzed",
        languages=[lang.name for lang in model.languages], apis=len(model.apis),
    )

    has_confirmed_openapi = any(a.kind == "openapi" and a.confidence.value == "detected" for a in model.apis)

    auth_config, auth_warnings = resolve_auth_from_env(
        bearer_token_env=request.bearer_token_env,
        api_key_env=request.api_key_env,
        api_key_header=request.api_key_header,
        basic_user_env=request.basic_auth_user_env,
        basic_pass_env=request.basic_auth_pass_env,
    )

    generated_count, run_result, functional_not_run_reason = _run_functional(request, auth_config, on_event)
    perf_result, performance_not_run_reason = _run_performance(request, config, auth_config, on_event)
    database_result = _run_database(request, on_event)

    _emit(on_event, STAGE_ASSESSMENT, PHASE_STARTED, "Aggregating assessment")
    assessment = build_assessment(
        project_path=request.project_path, target=request.target, model=model, generated_count=generated_count,
        run_result=run_result, functional_not_run_reason=functional_not_run_reason,
        perf_result=perf_result, performance_not_run_reason=performance_not_run_reason,
        has_confirmed_openapi=has_confirmed_openapi, database_result=database_result,
    )
    _emit(on_event, STAGE_ASSESSMENT, PHASE_COMPLETED, "Assessment complete", overall_status=assessment.overall_status.value)

    regression = None
    if request.baseline_path:
        _emit(on_event, STAGE_REGRESSION, PHASE_STARTED, "Comparing against baseline")
        baseline_snapshot = load_baseline(request.baseline_path)
        current_snapshot = build_snapshot(
            project_path=request.project_path, target=request.target, model=model, generated_count=generated_count,
            run_result=run_result, perf_result=perf_result, database_result=database_result, assessment=assessment,
        )
        thresholds = dict(config.regression.performance) if config.regression.performance else {}
        regression = regression_compare(baseline_snapshot, current_snapshot, performance_thresholds=thresholds)
        _emit(on_event, STAGE_REGRESSION, PHASE_COMPLETED, "Baseline comparison complete", status=regression.status.value)

    policy = QualityGatePolicy(fail_on=config.quality_gate.fail_on, warn_on=config.quality_gate.warn_on)
    quality_gate = qg_evaluate(assessment, regression, policy)

    bundle = AssessReportBundle(
        assessment=assessment, model=model, run_result=run_result, generated_count=generated_count,
        perf_result=perf_result, database_result=database_result, regression=regression, quality_gate=quality_gate,
    )

    _emit(on_event, STAGE_REPORT_GENERATION, PHASE_STARTED, "Generating reports")
    report_paths = _write_reports(bundle, request.output_dir, request.report_formats)
    _emit(on_event, STAGE_REPORT_GENERATION, PHASE_COMPLETED, "Reports generated", paths=report_paths)

    return AssessmentOutcome(
        model=model, run_result=run_result, functional_not_run_reason=functional_not_run_reason,
        perf_result=perf_result, performance_not_run_reason=performance_not_run_reason,
        database_result=database_result, assessment=assessment, regression=regression,
        quality_gate=quality_gate, bundle=bundle, report_paths=report_paths,
    )


def _run_functional(request: AssessmentRequest, auth_config, on_event: OnEvent | None):
    if not request.run_functional:
        return 0, None, "functional testing was not enabled"

    _emit(on_event, STAGE_FUNCTIONAL_TEST, PHASE_STARTED, "Running API functional tests")
    try:
        rest_result = rest_run(
            request.project_path, openapi_override=request.openapi_override, target=request.target,
            auth_config=auth_config, timeout_seconds=request.timeout_seconds, dry_run=False,
        )
    except MultipleSpecsFoundError as exc:
        _emit(on_event, STAGE_FUNCTIONAL_TEST, PHASE_FAILED, str(exc))
        return 0, None, str(exc)
    except (OpenApiError, DiscoveryError) as exc:
        _emit(on_event, STAGE_FUNCTIONAL_TEST, PHASE_FAILED, str(exc))
        return 0, None, str(exc)

    generated_count = len(rest_result.test_cases)
    if not rest_result.executed:
        reason = rest_result.no_target_reason or "no execution target was provided"
        _emit(on_event, STAGE_FUNCTIONAL_TEST, PHASE_SKIPPED, reason, generated=generated_count)
        return generated_count, None, reason

    _emit(
        on_event, STAGE_FUNCTIONAL_TEST, PHASE_COMPLETED, "API functional tests complete",
        summary=rest_result.run_result.summary,
    )
    return generated_count, rest_result.run_result, None


def _run_performance(request: AssessmentRequest, config: Config, auth_config, on_event: OnEvent | None):
    if not request.run_performance:
        _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_SKIPPED, "performance testing was not enabled")
        return None, "performance testing was not enabled"
    if not request.target:
        _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_SKIPPED, "no execution target was provided")
        return None, "no execution target was provided"
    if not request.performance_confirmed:
        # The GUI safety gate (brief §25): checking "run performance" alone is
        # never enough -- the explicit confirmation checkbox must also be set.
        _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_SKIPPED, "performance testing requires explicit user confirmation")
        return None, "performance testing requires explicit user confirmation"

    _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_STARTED, "Running performance test", target=request.target)
    try:
        spec, endpoint, perf_request, gen_warnings = resolve_performance_target(
            request.project_path, openapi_override=request.openapi_override,
            endpoint_path=request.perf_endpoint, method=request.perf_method,
        )
        profile, plan_warnings = build_load_profile(
            request.perf_profile, concurrency=request.perf_concurrency, requests=request.perf_requests,
            duration=request.perf_duration, max_concurrency=request.perf_max_concurrency,
            stop_on_error_rate_percent=request.perf_stop_error_rate, stop_on_p95_ms=request.perf_stop_p95_ms,
        )
    except MultipleSpecsFoundError as exc:
        _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_FAILED, str(exc))
        return None, str(exc)
    except (OpenApiError, DiscoveryError, ConfigurationError) as exc:
        _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_FAILED, str(exc))
        return None, str(exc)

    thresholds = dict(config.performance.thresholds) if config.performance.thresholds else {}
    auth_headers, auth_query = resolve_auth_headers(spec, endpoint, auth_config)
    executor, close = make_performance_executor(request.target, request.timeout_seconds, auth_headers, auth_query)
    try:
        perf_result = PerformanceRunner(executor).run(
            request.target, f"{perf_request.method} {perf_request.path}", perf_request, profile, thresholds=thresholds,
        )
    finally:
        close()
    perf_result.warnings = gen_warnings + plan_warnings + perf_result.warnings
    _emit(on_event, STAGE_PERFORMANCE_TEST, PHASE_COMPLETED, "Performance test complete")
    return perf_result, None


def _run_database(request: AssessmentRequest, on_event: OnEvent | None):
    if not request.run_database or not request.database_profile_path:
        _emit(on_event, STAGE_DATABASE_ASSESSMENT, PHASE_SKIPPED, "database assessment was not configured")
        return None

    _emit(on_event, STAGE_DATABASE_ASSESSMENT, PHASE_STARTED, "Assessing database (read-only)")
    try:
        profile = load_database_profile(request.database_profile_path)
    except ConfigurationError as exc:
        _emit(on_event, STAGE_DATABASE_ASSESSMENT, PHASE_FAILED, str(exc))
        return None
    result = db_discover(profile)
    _emit(on_event, STAGE_DATABASE_ASSESSMENT, PHASE_COMPLETED, "Database assessment complete")
    return result


def _write_reports(bundle: AssessReportBundle, output_dir: str | None, formats: list[str]) -> dict[str, str]:
    output_path = Path(output_dir) if output_dir else Path("reports")
    output_path.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for fmt in formats:
        renderer = _REPORT_RENDERERS.get(fmt)
        if renderer is None:
            continue
        rendered = renderer(bundle)
        file_path = output_path / f"report.{_REPORT_EXTENSIONS[fmt]}"
        file_path.write_text(rendered, encoding="utf-8")
        paths[fmt] = str(file_path)
    return paths
