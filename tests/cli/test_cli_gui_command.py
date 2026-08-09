"""CLI wiring for `universal-test gui` (Post-V1 GUI brief §33 -- the GUI is
an additional interface, not a replacement; existing subcommands stay
untouched, and this one must never open a browser or block during tests).
"""

from universal_test.cli.main import build_parser, main


def test_gui_is_a_valid_subcommand():
    parser = build_parser()
    args = parser.parse_args(["gui", "--port", "0", "--no-browser"])
    assert args.command == "gui"
    assert args.port == 0
    assert args.no_browser is True


def test_gui_command_starts_and_returns_zero_without_opening_a_browser(monkeypatch):
    monkeypatch.setattr("webbrowser.open", lambda url: (_ for _ in ()).throw(AssertionError("must not be called")))

    started = {}

    def fake_launch(port, open_browser):
        started["port"] = port
        started["open_browser"] = open_browser
        return object()

    monkeypatch.setattr("universal_test.gui.launcher.launch", fake_launch)

    exit_code = main(["gui", "--port", "0", "--no-browser"])
    assert exit_code == 0
    assert started == {"port": 0, "open_browser": False}
