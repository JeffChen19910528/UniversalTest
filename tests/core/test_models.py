from universal_test.core.models import (
    AssertionResult,
    AssertionSpec,
    Evidence,
    Finding,
    ResultStatus,
    Severity,
    TestCase,
    TestResult,
    TestTarget,
)
from universal_test.core.models.enums import AssessmentStatus


def test_evidence_to_dict():
    ev = Evidence("http_response", {"status_code": 200}, "ok")
    assert ev.to_dict() == {
        "type": "http_response",
        "data": {"status_code": 200},
        "description": "ok",
    }


def test_test_case_to_dict_roundtrip_shape():
    tc = TestCase(
        id="API-001",
        name="Create user",
        type="functional",
        target=TestTarget(adapter="rest", method="POST", path="/api/users"),
        request={"json": {"name": "Test"}},
        assertions=[AssertionSpec("status_code", {"equals": 201})],
    )
    d = tc.to_dict()
    assert d["id"] == "API-001"
    assert d["target"]["adapter"] == "rest"
    assert d["target"]["method"] == "POST"
    assert d["assertions"] == [{"type": "status_code", "equals": 201}]


def test_test_result_to_dict_matches_skillmd_shape():
    result = TestResult(
        id="API-001",
        category="functional",
        status=ResultStatus.FAILED,
        severity=Severity.MEDIUM,
        confidence=0.94,
        evidence=[Evidence("http_response", {"status_code": 500})],
        message="Endpoint returned HTTP 500 for valid request",
        recommendation="Inspect server-side exception handling",
    )
    d = result.to_dict()
    assert d["status"] == "failed"
    assert d["severity"] == "medium"
    assert d["confidence"] == 0.94
    assert d["evidence"][0]["data"]["status_code"] == 500


def test_finding_status_is_distinct_from_result_status():
    finding = Finding(
        category="Functional Health",
        status=AssessmentStatus.NOT_ASSESSED,
        summary="No authorized test credentials supplied",
    )
    assert finding.status == AssessmentStatus.NOT_ASSESSED
    assert finding.to_dict()["status"] == "not_assessed"


def test_assertion_result_to_dict():
    spec = AssertionSpec("status_code", {"equals": 200})
    ar = AssertionResult(assertion=spec, passed=True, message="ok")
    d = ar.to_dict()
    assert d["passed"] is True
    assert d["assertion"] == {"type": "status_code", "equals": 200}
