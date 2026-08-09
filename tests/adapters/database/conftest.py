from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "database"


@pytest.fixture
def sqlite_basic_path() -> Path:
    path = FIXTURES_DIR / "sqlite-basic" / "app.db"
    assert path.is_file(), f"missing fixture: {path}"
    return path


@pytest.fixture
def sqlite_relations_path() -> Path:
    path = FIXTURES_DIR / "sqlite-relations" / "app.db"
    assert path.is_file(), f"missing fixture: {path}"
    return path
