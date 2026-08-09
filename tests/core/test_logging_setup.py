"""Regression coverage for `core.logging_setup` (Final QA Known Issue A).

A logger with `propagate = False` is invisible to pytest's `caplog` fixture
for whatever test happens to be the *first* one in the process to trigger
`configure_logging()` -- pytest's `catching_logs` context manager only
auto-attaches its capture handler to loggers that are *already*
non-propagating when it enters, once per test. If `propagate` only becomes
False lazily, inside that same test, the attachment already happened too
early and the test's `caplog.records` stays empty even though the message
was genuinely logged (visible in captured stderr). See
`core/logging_setup.py` for the import-time fix.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from universal_test.core.logging_setup import LOGGER_NAME, configure_logging, get_logger


def test_logger_is_non_propagating_at_import_time():
    # Regardless of whether configure_logging() has ever been called in this
    # process, importing the module must already leave the shared logger
    # non-propagating -- this is what makes it visible to pytest's caplog
    # on the very first test that touches it (see module docstring).
    assert logging.getLogger(LOGGER_NAME).propagate is False


def test_configure_logging_does_not_duplicate_handlers():
    configure_logging()
    first_count = len(logging.getLogger(LOGGER_NAME).handlers)
    configure_logging()
    configure_logging()
    assert len(logging.getLogger(LOGGER_NAME).handlers) == first_count


def test_caplog_observes_records_even_as_the_first_test_to_log(caplog):
    # Regression test for the exact failure mode: run this assertion in a
    # brand-new subprocess so the shared `universal_test` logger has never
    # been touched by any earlier test in this process -- reproduces the
    # "first test in the session" ordering that broke caplog before the fix.
    script = (
        "import logging\n"
        "from universal_test.core.logging_setup import configure_logging, get_logger\n"
        "configure_logging()\n"
        "get_logger('cli').info('Detected CI environment: GitHub Actions')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).parent.parent.parent,
        capture_output=True, text=True, timeout=30,
    )
    assert "Detected CI environment: GitHub Actions" in result.stderr


def test_caplog_observes_cli_child_logger_records(caplog):
    caplog.set_level(logging.INFO, logger=f"{LOGGER_NAME}.cli")
    configure_logging()
    get_logger("cli").info("Detected CI environment: GitHub Actions")
    assert any("GitHub Actions" in r.message for r in caplog.records)
