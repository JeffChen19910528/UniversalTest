import pytest

from universal_test.core.models.enums import AssessmentStatus as S
from universal_test.assessment.rules import compute_overall_status, execution_health_status


@pytest.mark.parametrize("statuses,expected", [
    ([S.PASS], S.PASS),
    ([S.PASS, S.PASS], S.PASS),
    ([S.PASS, S.NOT_ASSESSED], S.PASS),
    ([S.PASS, S.WARNING], S.WARNING),
    ([S.PASS, S.FAIL], S.FAIL),
    ([S.WARNING, S.FAIL], S.FAIL),
    ([S.FAIL, S.WARNING, S.UNKNOWN], S.FAIL),
    ([S.WARNING, S.UNKNOWN], S.WARNING),
    ([S.UNKNOWN, S.PASS], S.UNKNOWN),
    ([S.UNKNOWN, S.NOT_ASSESSED], S.UNKNOWN),
    ([S.NOT_ASSESSED, S.NOT_ASSESSED], S.UNKNOWN),
    ([], S.UNKNOWN),
    ([S.FAIL], S.FAIL),
    ([S.WARNING], S.WARNING),
    ([S.UNKNOWN], S.UNKNOWN),
    ([S.NOT_ASSESSED], S.UNKNOWN),
])
def test_compute_overall_status(statuses, expected):
    assert compute_overall_status(statuses) == expected


def test_not_assessed_never_forces_a_pass_or_fail_alone():
    # a project where literally everything was skipped/not-configured is UNKNOWN,
    # never silently PASS and never FAIL just because nothing ran.
    assert compute_overall_status([S.NOT_ASSESSED] * 5) == S.UNKNOWN


def test_a_single_fail_among_many_passes_still_fails():
    assert compute_overall_status([S.PASS] * 10 + [S.FAIL]) == S.FAIL


# --- execution_health_status ---

def test_execution_health_zero_attempted_is_unknown():
    assert execution_health_status(0, 0, 0) == S.UNKNOWN


def test_execution_health_total_transport_failure_is_fail():
    assert execution_health_status(5, 5, 0) == S.FAIL


def test_execution_health_partial_transport_failure_is_warning():
    assert execution_health_status(5, 1, 0) == S.WARNING


def test_execution_health_check_failure_only_is_warning():
    assert execution_health_status(5, 0, 2) == S.WARNING


def test_execution_health_all_succeed_is_pass():
    assert execution_health_status(5, 0, 0) == S.PASS


def test_execution_health_one_attempted_one_transport_failure_is_fail():
    assert execution_health_status(1, 1, 0) == S.FAIL
