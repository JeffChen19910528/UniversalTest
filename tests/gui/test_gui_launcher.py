"""Tests for one-click startup safety (Post-V1 GUI brief §18-20/§32)."""

import sys
import threading

from universal_test.gui.launcher import launch
from universal_test.gui.server import LOOPBACK_HOST


def test_launch_binds_loopback_only_and_never_blocks_on_browser_failure(monkeypatch):
    opened_urls = []

    def fake_open(url):
        opened_urls.append(url)
        raise RuntimeError("no browser available in this environment")

    monkeypatch.setattr("webbrowser.open", fake_open)

    server = launch(port=0, open_browser=True, block=False)
    try:
        assert server.server_address[0] == LOOPBACK_HOST
        assert len(opened_urls) == 1
        assert opened_urls[0].startswith(f"http://{LOOPBACK_HOST}:")
    finally:
        server.shutdown()
        server.server_close()


def test_launch_with_browser_disabled_does_not_call_webbrowser(monkeypatch):
    called = []
    monkeypatch.setattr("webbrowser.open", lambda url: called.append(url) or True)

    server = launch(port=0, open_browser=False, block=False)
    try:
        assert called == []
    finally:
        server.shutdown()
        server.server_close()


def test_browser_open_failure_never_crashes_with_no_console_stdout(monkeypatch):
    # Simulates a windowed (console=False) packaged .exe, where PyInstaller
    # leaves sys.stdout/sys.stderr as None -- a bare print() would raise and
    # take the whole launch down right when the fallback message matters
    # most (Final QA Known Issue K).
    monkeypatch.setattr("webbrowser.open", lambda url: (_ for _ in ()).throw(RuntimeError("no browser")))
    monkeypatch.setattr(sys, "stdout", None)

    server = launch(port=0, open_browser=True, block=False)
    try:
        assert server.server_address[0] == LOOPBACK_HOST
    finally:
        server.shutdown()
        server.server_close()


def test_frozen_browser_open_failure_shows_a_native_dialog_not_a_crash(monkeypatch):
    # In the packaged .exe (`sys.frozen`), the fallback must reach for a
    # native message box instead of relying on a (nonexistent) console.
    # Stub out tkinter so no real window is created during the test.
    shown = []
    fake_tkinter = type(sys)("tkinter")
    fake_tkinter.Tk = lambda: type("Root", (), {
        "withdraw": lambda self: None,
        "attributes": lambda self, *a: None,
        "destroy": lambda self: None,
    })()
    fake_messagebox = type(sys)("tkinter.messagebox")
    fake_messagebox.showinfo = lambda title, message: shown.append((title, message))
    fake_tkinter.messagebox = fake_messagebox
    monkeypatch.setitem(sys.modules, "tkinter", fake_tkinter)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", fake_messagebox)

    monkeypatch.setattr("webbrowser.open", lambda url: (_ for _ in ()).throw(RuntimeError("no browser")))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    server = launch(port=0, open_browser=True, block=False)
    try:
        assert len(shown) == 1
        assert f"{LOOPBACK_HOST}:{server.server_port}" in shown[0][1]
    finally:
        server.shutdown()
        server.server_close()


def test_two_launches_get_different_ports_when_first_is_still_bound():
    server1 = launch(port=0, open_browser=False, block=False)
    try:
        server2 = launch(port=0, open_browser=False, block=False)
        try:
            assert server1.server_port != server2.server_port
        finally:
            server2.shutdown()
            server2.server_close()
    finally:
        server1.shutdown()
        server1.server_close()


def test_launch_configures_redacting_log_formatter_without_the_cli(monkeypatch):
    """Phase 12 QA regression: the packaged one-click `.exe`
    (`release/windows/launch_gui.py`) calls `launch()` directly and never
    goes through `cli/main.py::main()`'s `configure_logging()` call -- if
    `launch()` didn't configure it defensively, that packaged entry point's
    logger would have no `RedactingFormatter` attached, and an unhandled
    exception logged server-side (`gui/server.py::_internal_error()`) could
    write an unredacted secret to the log.
    """
    import logging

    from universal_test.core.logging_setup import LOGGER_NAME, RedactingFormatter

    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    for h in original_handlers:
        logger.removeHandler(h)
    try:
        server = launch(port=0, open_browser=False, block=False)
        try:
            assert logger.handlers, "launch() must configure logging even without the CLI"
            assert any(isinstance(h.formatter, RedactingFormatter) for h in logger.handlers)
        finally:
            server.shutdown()
            server.server_close()
    finally:
        for h in list(logger.handlers):
            logger.removeHandler(h)
        for h in original_handlers:
            logger.addHandler(h)
