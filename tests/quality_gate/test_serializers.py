import json

from universal_test.quality_gate.models import QualityGateFinding, QualityGateResult, QualityGateStatus
from universal_test.quality_gate.serializers import result_to_json, result_to_text


def _result() -> QualityGateResult:
    return QualityGateResult(
        status=QualityGateStatus.FAIL, exit_code=1,
        findings=[QualityGateFinding(rule="regression.high", level="fail", id="X-1", title="t", description="d")],
        summary={
            "functional_status": "pass", "performance_status": None, "database_status": None,
            "regression_status": "fail", "regression_findings_by_severity": {"high": 1},
        },
    )


def test_text_output_includes_status_and_exit_code():
    text = result_to_text(_result())
    assert "FAIL" in text
    assert "Exit code:" in text
    assert "1" in text


def test_text_output_has_no_secrets_by_construction():
    # a description sourced from tool-authored content only, never a raw header/body -- sanity check
    text = result_to_text(_result())
    assert "Authorization" not in text
    assert "Bearer" not in text


def test_json_output_round_trips():
    data = json.loads(result_to_json(_result()))
    assert data["status"] == "fail"
    assert data["exit_code"] == 1
    assert data["findings"][0]["rule"] == "regression.high"
