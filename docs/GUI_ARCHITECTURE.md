# GUI Architecture (Post-V1 Phase 1)

## Goal

Let a non-technical user run a first-pass project health check without
knowing Python, the CLI, terminals, pytest, OpenAPI, HTTP, database
drivers, baselines, or regression testing.

## Layering

```
                 Universal Test
                       |
          +------------+------------+
          v                         v
        CLI                       GUI
   (cli/main.py)          (gui/server.py + static/*)
          |                         |
          +------------+------------+
                       v
              Application Service Layer
              (application/service.py)
                       |
                       v
                 Existing Core
                       |
       +---------------+----------------+
       v               v                v
   Discovery         Testing        Assessment
```

The GUI **never** reimplements discovery, functional testing, performance
testing, database assessment, regression comparison, quality gate
evaluation, or report rendering. It calls
`universal_test.application.service.run_assessment()`, which is the exact
same sequence of Core/adapter calls `cli/main.py`'s `_run_pipeline`/
`_run_assess` already make (same `discover()`, `rest_run()`,
`PerformanceRunner`, `db_discover()`, `build_assessment()`,
`regression_compare()`, `qg_evaluate()`, and the three report renderers in
`universal_test.reporting`).

## Application Service Layer (`src/universal_test/application/`)

- `service.py::AssessmentRequest` — one GUI "開始專案健檢" click's input.
  Every field defaults to the safest value (functional analysis on,
  performance/database off, no guessed target).
- `service.py::run_assessment(request, on_event, config)` — runs the
  pipeline, calling `on_event(ProgressEvent)` at each stage boundary, and
  returns an `AssessmentOutcome` (assessment + regression + quality gate +
  report file paths).
- `events.py::ProgressEvent` — `{stage, phase, message, detail}`, where
  `phase` is one of `started/completed/skipped/failed`. Stage names match
  the GUI brief §11 catalog: `project_scan`, `functional_test`,
  `performance_test`, `database_assessment`, `assessment`,
  `report_generation` (plus `regression` when a baseline is supplied).

Nothing in Core imports from `application/` or `gui/` — the dependency
direction is strictly GUI → Application → Core.

## GUI (`src/universal_test/gui/`)

- `server.py` — a `http.server.ThreadingHTTPServer` bound to
  `127.0.0.1` only. No web framework dependency was added; the API
  surface is small enough that the stdlib is sufficient and keeps the
  packaged exe lean.
  - `GET /` , `GET /static/*` — serves `gui/static/index.html` and its
    plain HTML/CSS/JS (no build step, no Node.js, no bundler).
  - `POST /api/pick-folder`, `POST /api/pick-file` — opens a native
    Tkinter folder/file dialog on the same machine the server runs on
    (this is a localhost desktop tool, not a remote web app).
  - `POST /api/validate-project` — folder-exists / non-empty checks.
  - `POST /api/assess` — starts one `Run` (see `runs.py`) in a background
    thread and returns a `run_id`.
  - `GET /api/assess/<run_id>/stream` — Server-Sent Events stream of
    `ProgressEvent`s for that run.
  - `GET /api/assess/<run_id>/result` — the finished `AssessmentOutcome`
    as JSON (reusing each domain model's existing `to_dict()`).
  - `POST /api/open/report`, `POST /api/open/folder` — opens a generated
    report / its folder via `os.startfile` (Windows) or the platform
    equivalent.
- `runs.py::RunRegistry` — in-memory `run_id -> Run` map; each `Run` owns
  a `queue.Queue` the background worker thread pushes `ProgressEvent`s
  into and the SSE handler drains. Bounded: only the most recent N
  *completed* runs are retained (an active run is never evicted), and
  starting a second run while one is active raises `RunAlreadyActiveError`
  (surfaced as HTTP 409) — see `docs/GUI_SAFETY.md`.
- `launcher.py::launch()` — picks a free loopback port, starts the
  server, opens the default browser, and optionally blocks
  (`server.serve_forever()`). If auto-open fails, it logs the URL and
  prints it when a console is attached; in the packaged windowed (no
  console) `.exe`, it instead shows a native Tk message box with the URL.
- `static/` — `index.html` + `style.css` + `i18n.js` + `app.js`. Plain
  vanilla JS single-page app; internal enum values (`pass`/`warning`/
  `fail`/`unknown`/`not_assessed`, stage names) stay in English and are
  translated to Traditional Chinese / English only at render time.

## CLI integration

`universal-test gui [--port N] [--no-browser] [--verbose]` is one more
subcommand in `cli/main.py`, dispatched before the existing
`--target`/`load_config` logic (which assumes a `path` positional the
`gui` subcommand doesn't take). Every other subcommand
(`scan`/`assess`/`test`/`performance`/`database`/`baseline`) is
byte-for-byte unchanged.

## Packaging

`release/windows/launch_gui.py` is the PyInstaller entry point;
`release/windows/UniversalTest.spec` bundles `gui/static/*` as data and
excludes the optional database drivers (they're adapter-local, lazily
imported, and already degrade to a `NOT_ASSESSED` finding rather than an
`ImportError` when absent). `release/windows/build.ps1` drives the build.
See `docs/GUI_SAFETY.md` for the startup/network safety contract and
`docs/GUI_USER_GUIDE.md` for the end-user walkthrough.
