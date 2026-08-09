"""Structured logging setup shared by the CLI and all modules.

Every log record's message is passed through `core.redaction.redact` before
formatting, so secrets accidentally logged by adapters cannot leak.
"""

from __future__ import annotations

import logging

from universal_test.core.redaction import redact

LOGGER_NAME = "universal_test"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        return super().format(record)


# `propagate` is set at import time, not lazily inside `configure_logging()`.
# pytest's `caplog` fixture only auto-attaches its capture handler to
# non-propagating loggers that already exist (with propagate=False) at the
# moment its context manager enters for a given test -- a logger that only
# *becomes* non-propagating later (e.g. on the first `configure_logging()`
# call made from inside that same test) is invisible to it for that test.
# Setting it here, at module import (which happens during test collection,
# before any test's setup phase runs), makes capture behavior independent of
# whether/when the CLI has already run in this process.
logging.getLogger(LOGGER_NAME).propagate = False


def configure_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the shared `universal_test` logger.

    Safe to call multiple times (e.g. from tests) — handlers are not duplicated.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)
