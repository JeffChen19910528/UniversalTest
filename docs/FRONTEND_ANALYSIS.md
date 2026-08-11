# Frontend / Web Application Analysis

Universal Test supports analysis of both **framework-based frontend
applications** (React, Vue, Angular, Next.js, Nuxt, Svelte/SvelteKit,
Solid, Astro) **and plain static HTML/CSS/JavaScript websites** — a
project needs neither a `package.json` nor any build tooling to be
recognized as a frontend. Static analysis does not execute the website
and does not constitute browser/UI functional testing.

## What this is — and isn't

Universal Test can now answer three questions about an unfamiliar project:

1. **Does it have a frontend?**
2. **What frontend technology does it use?**
3. **What frontend testability evidence exists (test frameworks, test
   directories, build/test scripts)?**

It does **not** open a browser, click through the UI, or execute any
frontend test. That is a distinct, unimplemented future capability (a
Browser/UI Adapter). Every surface in the tool — CLI, GUI, JSON/Markdown/
HTML reports — reports **Browser/UI Execution: NOT_ASSESSED** whenever a
frontend is detected, specifically so "frontend detected" is never mistaken
for "frontend tested."

## Supported frameworks

Detected via `package.json` dependency or a framework-specific config file
(never from prose mentions in a README or comment):

| Framework | Dependency evidence | Config-file evidence |
|---|---|---|
| React | `react` | — |
| Next.js | `next` | `next.config.{js,ts,mjs}` |
| Vue | `vue` | — |
| Nuxt | `nuxt` | `nuxt.config.{js,ts}` |
| Angular | `@angular/core` | `angular.json` |
| Svelte | `svelte` | — |
| SvelteKit | `@sveltejs/kit` | `svelte.config.{js,ts}` |
| Solid | `solid-js` | — |
| Astro | `astro` | `astro.config.{js,ts,mjs}` |

Build tools/bundlers (Vite, Webpack, Rollup, Turbopack, Angular CLI) and
package managers (npm, yarn, pnpm, bun) are detected and reported
separately from frameworks — a framework and its build tool are different
facts and are never conflated (e.g. "React" and "Vite" are two separate
detections, not one).

## Supported test frameworks

| Category | Frameworks |
|---|---|
| Unit/component | Jest, Vitest, Mocha, Karma, Jasmine, Testing Library |
| Browser/UI automation | Playwright, Cypress, WebdriverIO, Puppeteer |

The distinction matters: a project can have solid unit-test coverage
(Vitest + Testing Library) and still have **no** browser automation
framework. That's reported as an informational testability limitation
(`FRONTEND-NO-BROWSER-TEST`, severity `INFO`), never as evidence the UI is
broken.

## Frontend classification (`FrontendType`)

A project is classified into exactly one of four types, computed with
**framework evidence taking precedence over static-HTML evidence** (a
React project is never misclassified as Static Web just because it also
has an `index.html`):

| Type | Meaning |
|---|---|
| `framework_web` | A recognized frontend framework (React, Vue, Angular, ...) was detected. |
| `static_web` | Plain HTML/CSS/JavaScript with no frontend framework — a real, first-class frontend type, not a fallback. |
| `full_stack_web` | Frontend evidence (framework **or** static) *and* a recognized backend web framework (FastAPI, Django, Flask, Express, ASP.NET Core, Spring Boot, Laravel, Node.js) both detected. |
| `unknown_web` | Weak/ambiguous HTML evidence exists (e.g. a single non-root HTML page with no supporting CSS/JS) — credible but not confidently classifiable. |

### Static website detection

A project does **not** need a `package.json`, lockfile, or any config file
to be recognized as a frontend — see [`discovery/frontend.py`](../src/universal_test/discovery/frontend.py)'s
`_detect_static_web`. Rules, in order:

1. An `index.html`/`index.htm` at the **scan root** is always strong
   evidence on its own — even a single page (`frontend-single-html`
   fixture) is detected as `static_web`.
2. Multiple directories each containing their own `index.html` (a
   monorepo — `frontend/index.html` + `admin/index.html`) are reported as
   **multiple web roots**, never silently collapsed into one application.
3. A single non-root `index.html` needs supporting structure (an
   accompanying CSS/JS file in the same directory, or a second HTML page
   nearby) to count as `static_web`; without support it's `unknown_web`
   (weak, `INFERRED` confidence).
4. A lone HTML file under a directory that looks generated or
   server-rendered (`docs/`, `doc/`, `templates/`, `_build/`, `site/`)
   with **no** supporting CSS/JS is **not** detected as a frontend at
   all — this is what keeps generated documentation, code-coverage
   reports, and backend template files (Flask/Django/Jinja `templates/`)
   from being misclassified as a standalone static website. `coverage/`
   and `htmlcov/` directories are excluded from discovery entirely (same
   mechanism as `node_modules`/`dist`/`build`), so generated coverage
   HTML never even reaches this logic.

### HTML/CSS/JS structural evidence

For a detected static site, discovery additionally reports (all bounded,
all read-only, all substring/filename-based — no HTML parsing library, no
JavaScript execution):

- **HTML/CSS/JS file counts** — exact counts over the whole (already
  excluded-directory-filtered) file list, not the 300-file scan cap.
- **Entry point(s)** and, when ambiguous, the full list of web roots.
- **Routes/navigation** — `<a href="...">` links, plus the same
  React/Vue/Angular route markers already used for framework apps.
- **Forms** — `<form>`/`<input>`/`<select>`/`<textarea>` presence (not a
  reliable per-control validation-attribute census — see Limitations).
- **API-client evidence** — `fetch()`, `axios`, `XMLHttpRequest`,
  `WebSocket(`, GraphQL/React-Query/SWR markers, found in `.html`/`.js`
  files alike.
- **Responsive design evidence** — `<meta name="viewport">` and `@media`
  queries.
- **Authentication UI evidence** — `login`/`signin` filenames,
  `type="password"`, `sessionStorage`/`localStorage`, `Authorization`/
  `Bearer` — structural evidence only; **never** implies the
  authentication is actually secure, and no credential value is ever
  inspected or reported.
- **CSS framework evidence** — Bootstrap/Tailwind CSS/Bulma/Foundation,
  matched only against filenames or `<link href>`/`@tailwind`-style
  content markers, **never** from an arbitrary class name like
  `class="container"` (that alone proves nothing about which framework,
  if any, is in use).

## Evidence and confidence rules

Every fact is one of `DETECTED` / `INFERRED` / `NOT_APPLICABLE` / `UNKNOWN`
(the project's existing `DetectionConfidence` vocabulary — no new levels
were invented). Framework/build-tool/test-framework detections require a
manifest dependency or a config file; a bare source-code import or a prose
mention is never sufficient on its own.

Routes, UI components, forms, and frontend-to-backend API-client usage are
reported as **bounded heuristic evidence** (`FrontendSignal`): a substring
scan of up to 300 files under recognized frontend source roots (`src/`,
`app/`, `pages/`, `components/`, `routes/`, `views/`). The scan bound is
always stated in the evidence (`note` field), and the language is always
"evidence detected" — never "all routes/components/forms found." This is
not AST parsing and does not claim complete coverage.

## Limitations (bounded-scan honesty)

- The 300-file cap means a very large frontend may have route/component/
  form/API-client evidence that exists but wasn't scanned. Detection is a
  lower bound, not a census.
- No AST parsing — markers are literal substrings (`<Route`,
  `createBrowserRouter`, `fetch(`, `<form`, etc.), so unusual code styles
  can be missed. This never produces a false "not detected" claim beyond
  what the tool honestly reports as its confidence.
- Directory-based routing (Next.js `app/`/`pages/`, SvelteKit
  `src/routes/`) is detected structurally even without any route-marker
  text match.
- Static-site routing/link evidence cannot distinguish a real navigation
  link from a dynamically generated one (`<a href="...">` written by
  JavaScript at runtime is invisible to a static text scan) — reported as
  "route/navigation evidence detected," never "the complete site map."
- The docs/templates/coverage false-positive guard is itself a heuristic:
  a real static site legitimately kept in a `docs/` directory (a common
  GitHub Pages convention) with **no** accompanying CSS/JS and only one
  page will not be detected. Adding a second page or a CSS/JS file next
  to it resolves this — see `_detect_static_web` for the exact rule.

## Security model

- **Read-only, offline.** Discovery only reads files already collected by
  the existing filesystem walk. It never runs `npm install`, `npm run
  build/test`, any other package-manager or lifecycle script, launches a
  browser, or opens a network connection.
- **`package.json` `scripts` are untrusted data.** Build/test script
  commands are copied as inert strings for display only — never executed.
  A malicious `"prepare"`/`"postinstall"` script in a scanned repository
  cannot run as a side effect of discovery (see
  `tests/discovery/test_frontend_safety.py`, which monkeypatches
  `subprocess`/`socket` to fail the test if discovery ever touches them).
- **No secret leakage.** `.env.example`/`.env.template` contribute **key
  names only** — values are never read into any model, report, or log,
  mirroring the existing secret-redaction convention
  (`SecretFinding.to_dict()`'s `"value": "[REDACTED]"`).

## Discovery vs. execution — the explicit boundary

| | Implemented |
|---|---|
| A. Frontend discovery (is there a frontend, what tech) | ✅ |
| B. Frontend testability assessment (test tooling, evidence) | ✅ |
| C. Browser/UI execution (actually running the UI, clicking, screenshots) | ❌ — future Browser Adapter |

This boundary is enforced consistently:

- `assessment/frontend_assessment.py`'s "Frontend / Web Application Health"
  category caps out at `PASS`/`WARNING`/`NOT_ASSESSED` — it can never
  report `FAIL`, since discovery evidence alone cannot prove a frontend is
  broken.
- `assessment/engine.py` always adds a "Browser/UI Execution" entry to both
  `coverage` (pinned at 0%) and `unassessed` whenever a frontend is
  detected, with the reason "Browser automation adapter is not enabled in
  this version."
- `adapters/frontend/adapter.py`'s `execute()` raises an explicit
  `NotImplementedError` rather than silently doing nothing or returning a
  fake result.
- CLI (`scan`/`assess`), Markdown/HTML reports, and the GUI all show the
  same "Browser/UI Execution: NOT_ASSESSED" line next to any frontend
  results.

## Capability detection beyond framework/manifest evidence

A rich single-file application (substantial inline CSS/JS, browser API
usage — the shape of a typical small SPA shipped as one `index.html`) is
not misreported as having no CSS/JS just because nothing lives in a
separate file:

- **Inline vs. external CSS/JS.** `inline_css_count`/`inline_js_count`
  (regex-counted `<style>`/`<script>` blocks without a `src=` attribute)
  are reported *in addition to*, never instead of, `css_file_count`/
  `js_file_count` (separate `.css`/`.js` files).
- **Interactive UI evidence** — `<button>`, `<input>`, `<select>`,
  `onclick=`, `addEventListener(`, etc. Reported as "interactive element
  evidence detected," never as a count of "working" controls.
- **Browser APIs** — a name list (e.g. "Microphone (getUserMedia)",
  "MediaRecorder", "Speech synthesis", "Local storage", "WebSocket",
  "Notifications", "Geolocation", "Clipboard", "File reading (FileReader)",
  "IndexedDB"), matched by literal marker, always "detected," never
  "working." Kept structurally separate from `api_clients` (backend
  API-call evidence like `fetch`/`axios`) — a microphone API is not a
  backend API client.
- **Application pattern** — `static_multi_page` (≥2 HTML pages),
  `single_page_application` (one page with real supporting behavioral
  evidence: inline JS plus interactivity/API/browser-API usage), or
  `static_document` (one page, no such evidence). Always framed as
  "evidence suggests," never asserted as confirmed — static analysis
  cannot prove the page actually behaves as a SPA at runtime.
- **External resources** — a few well-known CDN/font hosts normalized to
  a friendly label (e.g. "Google Fonts"), plus generic external-stylesheet/
  script/image markers. Never fetched, never treated as a vulnerability.
- **Content-Security-Policy evidence** — presence of a CSP meta tag/header
  string. Structural evidence only, not a security audit.
- **Authentication UI (hardened)** — a real `<input type="password">` is
  strong evidence (`DETECTED`); generic storage/header markers
  (`localStorage`, `sessionStorage`, `Authorization`, `Bearer`) are common
  in code unrelated to a login form, so they only count as weak evidence
  (`INFERRED`), and only when a `<form>` is also present in the same file.
  A README or code comment merely mentioning "login"/"password"/
  "authentication" was never sufficient and still isn't — no marker is a
  bare prose word.

## Assessment status semantics

`PASS`/`WARNING`/`FAIL`/`UNKNOWN`/`NOT_ASSESSED` answer different
questions and are never collapsed into one meaning. A `WARNING` may
indicate a testability limitation or incomplete assessment and does not
necessarily indicate an application defect — static analysis can detect
capabilities and evidence but cannot prove runtime behavior.

- **`AssessmentFinding.classification`** — every finding is labeled
  `defect` / `testability_gap` / `not_assessed` / `informational` /
  `execution_failure`, so a report or the GUI can state plainly whether a
  `WARNING` reflects a real problem or a missing capability. For example,
  "no frontend test framework detected" is `testability_gap`, not
  `defect` — its description explicitly says this does not indicate the
  application has a defect.
- **`ProjectAssessment.application_health`** — a separate field from
  `overall_status` (which is unchanged and still drives Quality Gate/
  regression/CLI exit codes). `application_health` reads `PASS` ("no
  confirmed defects") unless a category whose status is driven by
  something that actually *executed* against the live project
  (`Functional Health` or `Performance`) reports `WARNING`/`FAIL`. A
  static site with several `WARNING` categories purely from missing test
  tooling still shows `application_health: PASS`.
- **`ProjectAssessment.assessment_completeness`** ("full"/"partial") —
  derived from the existing coverage/unassessed data; whether every
  assessable area was actually assessed this run, independent of whether
  anything failed.
- A static website with no package manager/build system is not treated as
  a build defect — `Build / Project Health` reads `PASS` with the reason
  "a package manager/build system is not required" for a genuine static
  site. A valid HTML/CSS/JS site with no recognized programming language
  no longer reads `UNKNOWN`/"0 languages" in `Project Discovery`.
- Quality Gate `PASS` means no configured gate rule failed — not that the
  entire application was verified correct; `FAIL` means a configured
  condition failed. Reports and the GUI state this explicitly next to the
  Quality Gate result.

No numeric quality score was introduced anywhere in this project, and none
of the above changes weaken or reinterpret `overall_status`, Quality Gate,
regression, baseline comparison, or CLI exit codes — they are unchanged.
