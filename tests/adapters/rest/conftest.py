from pathlib import Path

import pytest

from .fixture_server import FixtureServer

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


@pytest.fixture
def openapi_fixture_path():
    def _get(name: str) -> Path:
        path = FIXTURES_DIR / name
        assert path.is_dir(), f"missing fixture directory: {path}"
        return path

    return _get
