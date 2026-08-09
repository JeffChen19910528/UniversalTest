from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixture_path():
    def _get(name: str) -> Path:
        path = FIXTURES_DIR / name
        assert path.is_dir(), f"missing fixture directory: {path}"
        return path

    return _get
