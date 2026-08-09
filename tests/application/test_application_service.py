"""Tests for the GUI Application Service Layer (Post-V1 GUI brief §4/§32).

Covers the safety-critical behaviors the GUI relies on: safe defaults, "no
target -> no network traffic", performance's explicit confirmation gate,
database opt-in, and progress-event emission -- without duplicating the
underlying Core/adapter test coverage that already exists elsewhere.
"""

from pathlib import Path

import pytest

from tests.adapters.rest.fixture_server import FixtureServer
from universal_test.application.events import PHASE_SKIPPED, PHASE_STARTED, STAGE_PERFORMANCE_TEST
from universal_test.application.service import AssessmentRequest, run_assessment

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


def test_safe_defaults_run_only_project_analysis_and_functional_generation(tmp_path):
    request = AssessmentRequest(project_path=str(FIXTURES_DIR / "openapi-basic"), output_dir=str(tmp_path))
    outcome = run_assessment(request)

    assert outcome.run_result is None  # no target -> functional generation only, never executed
    assert outcome.performance_not_run_reason == "performance testing was not enabled"
    assert outcome.database_result is None


def test_no_target_means_no_network_traffic_even_with_functional_enabled(tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), target=None, run_functional=True, output_dir=str(tmp_path),
    )
    outcome = run_assessment(request)
    assert outcome.run_result is None
    assert outcome.functional_not_run_reason is not None


def test_functional_executes_against_an_explicit_target(live_server, tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), target=live_server.base_url, output_dir=str(tmp_path),
    )
    outcome = run_assessment(request)
    assert outcome.run_result is not None
    assert outcome.functional_not_run_reason is None


def test_performance_checkbox_alone_does_not_run_performance(live_server, tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), target=live_server.base_url,
        run_performance=True, performance_confirmed=False, output_dir=str(tmp_path),
    )
    events = []
    outcome = run_assessment(request, on_event=events.append)

    assert outcome.perf_result is None
    assert outcome.performance_not_run_reason == "performance testing requires explicit user confirmation"
    assert not any(e.stage == STAGE_PERFORMANCE_TEST and e.phase == PHASE_STARTED for e in events)
    assert any(e.stage == STAGE_PERFORMANCE_TEST and e.phase == PHASE_SKIPPED for e in events)


def test_performance_runs_only_with_both_enable_and_explicit_confirmation(live_server, tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), target=live_server.base_url,
        run_performance=True, performance_confirmed=True, perf_profile="baseline",
        perf_endpoint="/users", perf_method="GET", perf_requests=1, output_dir=str(tmp_path),
    )
    outcome = run_assessment(request)
    assert outcome.perf_result is not None
    assert outcome.performance_not_run_reason is None


def test_database_is_not_assessed_without_an_explicit_profile(tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), run_database=True,
        database_profile_path=None, output_dir=str(tmp_path),
    )
    outcome = run_assessment(request)
    assert outcome.database_result is None


def test_progress_events_are_emitted_in_stable_stage_order(tmp_path):
    request = AssessmentRequest(project_path=str(FIXTURES_DIR / "openapi-basic"), output_dir=str(tmp_path))
    events = []
    run_assessment(request, on_event=events.append)

    stages_seen = [e.stage for e in events]
    assert stages_seen.index("project_scan") < stages_seen.index("functional_test")
    assert stages_seen.index("functional_test") < stages_seen.index("assessment")
    assert stages_seen.index("assessment") < stages_seen.index("report_generation")


def test_reports_are_written_for_every_requested_format(tmp_path):
    request = AssessmentRequest(
        project_path=str(FIXTURES_DIR / "openapi-basic"), output_dir=str(tmp_path),
        report_formats=["json", "markdown", "html"],
    )
    outcome = run_assessment(request)
    for fmt, path in outcome.report_paths.items():
        assert Path(path).is_file()
    assert set(outcome.report_paths) == {"json", "markdown", "html"}


def test_overall_status_is_one_of_the_five_assessment_statuses(tmp_path):
    request = AssessmentRequest(project_path=str(FIXTURES_DIR / "openapi-basic"), output_dir=str(tmp_path))
    outcome = run_assessment(request)
    assert outcome.assessment.overall_status.value in {"pass", "warning", "fail", "unknown", "not_assessed"}
