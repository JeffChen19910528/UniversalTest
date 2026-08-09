"""One-click startup (Post-V1 GUI brief §18-20).

`launch()` is the single entry point both `universal-test gui` (CLI
subcommand) and the packaged `UniversalTest.exe` launcher call. It never
requires administrator privileges, never touches firewall/system
configuration, never binds beyond loopback, and never crashes the server
just because the browser failed to open automatically.
"""

from __future__ import annotations

import sys
import threading
import webbrowser

from universal_test.core.logging_setup import get_logger
from universal_test.gui.server import LOOPBACK_HOST, find_free_port, make_server

logger = get_logger("gui")


def _print_started(url: str) -> None:
    # A windowed (console=False) PyInstaller build has `sys.stdout is None`
    # -- printing to it would raise and take the whole launch down right
    # when a fallback message matters most (Final QA Known Issue K).
    if sys.stdout is not None:
        print(f"Universal Test has started. Please open: {url}")


def _show_fallback_address(url: str) -> None:
    """Makes the localhost address impossible to miss even when auto-open
    fails and no console window exists to print to (Final QA Known Issue K:
    the packaged one-click .exe runs windowed/no-console for a non-technical
    double-click experience, so `print()` alone would be silently lost).
    """
    logger.warning("Could not auto-open a browser. Please open: %s", url)
    _print_started(url)
    if not getattr(sys, "frozen", False):
        return  # running from source with a real terminal -- the print above is enough
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo("Universal Test", f"Please open this address in your browser:\n\n{url}")
        root.destroy()
    except Exception:  # noqa: BLE001 - a fallback dialog failing must never take the server down
        pass


def launch(port: int = 0, open_browser: bool = True, block: bool = True):
    """Starts the local GUI server and (optionally) opens the default
    browser to it. Returns the running server; callers that pass
    `block=False` (e.g. tests) are responsible for calling
    `server.shutdown()` themselves.
    """
    actual_port = port or find_free_port()
    server = make_server(host=LOOPBACK_HOST, port=actual_port)
    url = f"http://{LOOPBACK_HOST}:{server.server_port}"

    if open_browser:
        opened = False
        try:
            opened = webbrowser.open(url)
        except Exception:  # noqa: BLE001 - a browser launch failure must never take the server down (brief §20)
            opened = False
        if not opened:
            _show_fallback_address(url)
    else:
        _print_started(url)

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
            server.server_close()
    else:
        # Callers with block=False (tests, embedders) own the server's
        # lifecycle and are expected to call `server.shutdown()` themselves --
        # but the serving loop still has to actually be running somewhere, or
        # that later `shutdown()` call blocks forever waiting for a loop that
        # never started.
        threading.Thread(target=server.serve_forever, name="universal-test-gui", daemon=True).start()

    return server
