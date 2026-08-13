"""Safe automatic smoke-test generation (spec §28-§29, §56-§57).

The auto-generated test performs only: navigate to the target, assert the
page loaded (body visible), assert a title exists. It never clicks,
submits, uploads, or requests a permission automatically -- even when
`FrontendInfo` evidence (forms, buttons, MediaRecorder/getUserMedia) is
available, that evidence is only ever used to describe capability, never
to justify auto-triggering it (spec §11, §23, §29).
"""

from __future__ import annotations

from universal_test.adapters.browser.models import BrowserStep
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget
from universal_test.discovery.models import FrontendInfo

SMOKE_TEST_ID = "browser-smoke-1"


def generate_smoke_test(target: str, frontend_info: FrontendInfo | None = None) -> TestCase:
    """Builds the one safe default smoke test (spec §56/§57): navigate,
    assert body visible, assert a non-empty title. `frontend_info` is
    accepted for future entry-point selection but never used to decide on
    additional actions -- see module docstring.
    """
    steps = [BrowserStep(action="navigate").to_dict()]
    assertions = [
        AssertionSpec("visible", {"selector": {"type": "css", "value": "body"}}),
        AssertionSpec("page_title", {}),
        AssertionSpec("console_summary", {}),
    ]
    return TestCase(
        id=SMOKE_TEST_ID,
        name="Browser smoke test",
        type="browser",
        target=TestTarget(adapter="browser", extra={"steps": steps}),
        assertions=assertions,
    )
