from universal_test.quality_gate.ci_detection import detect_ci_environment


def test_no_markers_returns_none():
    assert detect_ci_environment({}) is None


def test_github_actions_detected():
    assert detect_ci_environment({"GITHUB_ACTIONS": "true"}) == "GitHub Actions"


def test_gitlab_ci_detected():
    assert detect_ci_environment({"GITLAB_CI": "true"}) == "GitLab CI"


def test_jenkins_detected():
    assert detect_ci_environment({"JENKINS_URL": "http://jenkins.local"}) == "Jenkins"


def test_azure_pipelines_detected():
    assert detect_ci_environment({"TF_BUILD": "True"}) == "Azure Pipelines"


def test_generic_ci_fallback():
    assert detect_ci_environment({"CI": "true"}) == "generic CI"


def test_specific_marker_preferred_over_generic_ci():
    assert detect_ci_environment({"CI": "true", "GITHUB_ACTIONS": "true"}) == "GitHub Actions"


def test_empty_string_value_is_not_detected():
    assert detect_ci_environment({"CI": ""}) is None
