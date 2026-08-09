# PyInstaller spec for the portable one-click Windows GUI (Post-V1 GUI brief
# §21-22). Produces a `dist/UniversalTest/UniversalTest.exe` --onedir build
# (not --onefile): faster startup, and a portable folder matches the brief's
# "UniversalTest/ UniversalTest.exe ..." layout.
#
# Build with: pyinstaller release/windows/UniversalTest.spec --distpath dist/windows
#
# Optional database drivers (psycopg2/mysql-connector-python/pyodbc) are
# intentionally NOT bundled -- they are adapter-local, lazily imported, and
# already degrade to a NOT_ASSESSED finding rather than crashing when absent
# (see pyproject.toml's `database` extra and skill.md's adapter isolation
# rule). The GUI surfaces this as "資料庫檢查需要額外的資料庫驅動程式" rather
# than an unhandled ImportError (brief §22).

import pathlib

SPEC_DIR = pathlib.Path(SPECPATH)
REPO_ROOT = SPEC_DIR.parent.parent
STATIC_DIR = REPO_ROOT / "src" / "universal_test" / "gui" / "static"

a = Analysis(
    [str(SPEC_DIR / "launch_gui.py")],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=[(str(STATIC_DIR), "universal_test/gui/static")],
    hiddenimports=[],
    hookspath=[],
    excludes=["psycopg2", "mysql.connector", "pyodbc"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UniversalTest",
    # console=False (windowed): a non-technical user double-clicking
    # UniversalTest.exe should never see a black console window flash up
    # (Final QA Known Issue K). The browser-auto-open fallback no longer
    # depends on a console being present: `gui/launcher.py`'s
    # `_show_fallback_address()` detects `sys.frozen` and shows a native
    # Tk message box with the localhost URL instead, and always also logs
    # the URL through the normal (redacting) logger so it still ends up in
    # `--verbose`/log output for anyone running from a terminal instead.
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="UniversalTest",
)
