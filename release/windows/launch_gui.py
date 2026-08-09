"""Entry point for the packaged `UniversalTest.exe` (Post-V1 GUI brief §21-22).

Double-clicking the exe runs this script with no arguments -- it never
receives CLI flags, so it always uses safe defaults: auto-selected
localhost port, browser auto-opened. `universal-test gui --port/--no-browser`
remains the flag-driven equivalent for anyone launching from a terminal
instead of double-clicking.
"""

from universal_test.gui.launcher import launch


def main() -> None:
    launch(port=0, open_browser=True, block=True)


if __name__ == "__main__":
    main()
