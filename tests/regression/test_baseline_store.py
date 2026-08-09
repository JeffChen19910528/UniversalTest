import json

import pytest

from universal_test.core.errors import RegressionError
from universal_test.regression.baseline_store import load_baseline, save_baseline
from universal_test.regression.models import (
    AssessmentSnapshot,
    BaselineSnapshot,
    DiscoverySnapshot,
    SourceInfo,
)


def _snapshot() -> BaselineSnapshot:
    return BaselineSnapshot(
        schema_version="1.0", tool_version="0.1.0", generated_at="2026-01-01T00:00:00Z",
        project_path="./p", source=SourceInfo(is_git=True, commit="abc123", branch="main", dirty=False),
        discovery=DiscoverySnapshot(languages=["Python"], frameworks=["FastAPI"]),
        functional=None, performance=None, database=None,
        assessment=AssessmentSnapshot(overall_status="pass", categories=[]),
    )


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline(_snapshot(), path)
    loaded = load_baseline(path)
    assert loaded.tool_version == "0.1.0"
    assert loaded.source.commit == "abc123"
    assert loaded.discovery.languages == ["Python"]


def test_load_missing_file_raises():
    with pytest.raises(RegressionError):
        load_baseline("/nonexistent/path/baseline.json")


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(RegressionError):
        load_baseline(path)


def test_load_non_baseline_json_raises(tmp_path):
    path = tmp_path / "notabaseline.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(RegressionError):
        load_baseline(path)


def test_incompatible_schema_version_raises(tmp_path):
    path = tmp_path / "old.json"
    data = _snapshot().to_dict()
    data["schema_version"] = "99.0"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegressionError, match="unsupported baseline schema version"):
        load_baseline(path)


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "baseline.json"
    save_baseline(_snapshot(), path)
    assert path.is_file()


def test_load_never_writes_back_to_the_file(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline(_snapshot(), path)
    before = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns
    load_baseline(path)
    load_baseline(path)
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == before_mtime
