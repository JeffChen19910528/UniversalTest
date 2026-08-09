"""Baseline persistence — `baseline save` writes, `baseline compare` /
`assess --baseline` only ever read (Phase 7 brief §4: "Baseline Must Be
Immutable" — no code path here modifies a baseline file once loaded).

Schema-version compatibility is enforced strictly (brief §18): an
unsupported `schema_version` is refused outright with a clear error,
never guessed at or partially parsed. A differing *tool* version is not an
error — it's recorded in the comparison output so a reader can see both
versions (brief §18's second half).
"""

from __future__ import annotations

import json
from pathlib import Path

from universal_test.core.errors import RegressionError
from universal_test.regression.models import SCHEMA_VERSION, BaselineSnapshot

_SUPPORTED_SCHEMA_VERSIONS = {SCHEMA_VERSION}


def save_baseline(snapshot: BaselineSnapshot, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=False), encoding="utf-8")
    return path


def load_baseline(path: str | Path) -> BaselineSnapshot:
    baseline_path = Path(path)
    if not baseline_path.is_file():
        raise RegressionError(f"--baseline path does not exist or is not a file: {baseline_path}")

    try:
        raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegressionError(f"invalid JSON in baseline file {baseline_path}: {exc}") from exc

    if not isinstance(raw, dict) or "schema_version" not in raw:
        raise RegressionError(f"{baseline_path} does not look like a universal-test baseline file")

    schema_version = raw["schema_version"]
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise RegressionError(
            f"unsupported baseline schema version {schema_version!r} in {baseline_path}; "
            f"this build of universal-test supports {sorted(_SUPPORTED_SCHEMA_VERSIONS)} only "
            "(refusing to guess how to parse it)"
        )

    try:
        return BaselineSnapshot.from_dict(raw)
    except (KeyError, TypeError) as exc:
        raise RegressionError(f"malformed baseline file {baseline_path}: {exc}") from exc
