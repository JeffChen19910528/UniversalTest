import json

from universal_test.core.models.enums import AssessmentStatus, DetectionConfidence, FindingClassification
from universal_test.discovery import discover
from universal_test.discovery.models import ProjectModel, SecretFinding
from universal_test.assessment.configuration_assessment import assess_configuration_hygiene


def _model_with_secrets(secrets: list[SecretFinding]) -> ProjectModel:
    model = ProjectModel(root_path="x", tool_version="0", scanned_at="now")
    model.secrets = secrets
    return model


def test_no_secrets_passes(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    model = discover(tmp_path)
    category = assess_configuration_hygiene(model)
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_secret_pattern_is_warning_never_fail():
    model = _model_with_secrets([
        SecretFinding(file="config.py", line=3, pattern_type="password", confidence=DetectionConfidence.INFERRED),
    ])
    category = assess_configuration_hygiene(model)
    assert category.status == AssessmentStatus.WARNING
    assert len(category.findings) == 1
    # an unconfirmed pattern match is informational, not a confirmed defect
    # (brief §5) - it must not count toward "Application Health".
    assert category.findings[0].classification == FindingClassification.INFORMATIONAL


def test_secret_value_never_appears_in_finding():
    model = _model_with_secrets([
        SecretFinding(file="config.py", line=3, pattern_type="password", confidence=DetectionConfidence.INFERRED),
    ])
    finding = assess_configuration_hygiene(model).findings[0]
    assert finding.evidence[0].data["value"] == "[REDACTED]"
    assert "[REDACTED]" in json.dumps(finding.to_dict())


def test_many_secrets_are_truncated_with_a_note():
    model = _model_with_secrets([
        SecretFinding(file=f"config{i}.py", line=1, pattern_type="token", confidence=DetectionConfidence.INFERRED)
        for i in range(40)
    ])
    category = assess_configuration_hygiene(model)
    assert len(category.findings) == 26  # 25 shown + 1 truncation note
    assert category.findings[-1].id == "CFG-SECRET-TRUNCATED"
