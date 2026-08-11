"""Frontend/web-application discovery (Frontend Adapter brief §4-§20;
Static Web Analysis brief §3-§20).

Read-only, offline, bounded: this module only reads file contents already
collected by `filesystem.walk` — it never runs `npm`/`node`/a package
manager, never launches a browser, never opens a socket, never executes
HTML/CSS/JavaScript (brief §22/§25/§26/§29). Route/component/form/
API-client/responsive/auth-UI evidence comes from a *bounded* substring
scan of a capped number of files — never presented as exhaustive
(`FrontendSignal.note` always states the cap), matching skill.md §4.1's
"never overclaim" rule.

Framework/language/build-system/test-framework facts are read from the
`ProjectModel` lists other detectors already populate
(`framework.py`/`language.py`/`project_type.py`/`test_framework.py`) rather
than re-detected here — see `FrontendInfo`'s docstring in `models.py`. A
project can also have **no** manifest/framework at all and still be a
frontend: a plain static HTML/CSS/JS website (Static Web Analysis brief
§3/§4) — `detect_frontend`'s two detection paths (`_detect_frontend_flag`
for manifest/config-driven projects, `detect_static_web` for plain HTML
sites) are independent and either one alone is sufficient.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile, read_text_safe
from universal_test.discovery.manifests import ManifestBundle
from universal_test.discovery.models import FrontendInfo, FrontendSignal, FrontendType

FRONTEND_FRAMEWORK_NAMES = {
    "React", "Next.js", "Vue", "Nuxt", "Angular", "Svelte", "SvelteKit", "Solid", "Astro",
}

# Recognized backend *web* frameworks — used only to decide FULL_STACK_WEB
# vs. FRAMEWORK_WEB/STATIC_WEB (Static Web Analysis brief §3, "Full-stack
# Web"). Deliberately narrower than "everything in model.frameworks that
# isn't a frontend name" (e.g. WinForms/Hardhat aren't a "web backend").
BACKEND_WEB_FRAMEWORK_NAMES = {
    "FastAPI", "Django", "Flask", "Express", "ASP.NET Core", "Spring Boot", "Laravel", "Node.js",
}

# Shared with `project_type.py`'s "frontend" `ProjectTypeDetection" — defined
# once here so both stay in sync rather than duplicating the literal lists.
FRONTEND_PACKAGE_HINTS = {
    "react", "react-dom", "vue", "@angular/core", "svelte", "@sveltejs/kit",
    "solid-js", "astro", "next", "nuxt", "vite",
}

FRONTEND_CONFIG_MARKERS = (
    "vite.config.js", "vite.config.ts", "angular.json", "svelte.config.js",
    "svelte.config.ts", "astro.config.js", "astro.config.ts", "astro.config.mjs",
    "next.config.js", "next.config.ts", "next.config.mjs", "nuxt.config.js", "nuxt.config.ts",
)

FRONTEND_TEST_FRAMEWORK_NAMES = {
    "Jest", "Vitest", "Mocha", "Karma", "Jasmine",
    "Playwright", "Cypress", "WebdriverIO", "Puppeteer", "Testing Library",
}

BROWSER_AUTOMATION_TEST_FRAMEWORK_NAMES = {"Playwright", "Cypress", "WebdriverIO", "Puppeteer"}

_FRONTEND_SOURCE_ROOTS = ("src/", "app/", "pages/", "components/", "routes/", "views/")
_FRONTEND_SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".htm"}
_MAX_SCANNED_FILES = 300

_ROUTE_MARKERS = (
    "react-router", "createBrowserRouter", "<Route", "vue-router", "RouterModule",
    "app-routing", "createRouter(", "<a href=",
)
_COMPONENT_DIR_HINTS = ("components/", "src/components/")
_FORM_MARKERS = (
    "<form", "<input", "<select", "<textarea", "react-hook-form", "Formik", "ReactiveFormsModule",
)
_API_CLIENT_MARKERS = (
    "fetch(", "axios", "XMLHttpRequest", "@apollo/client", "graphql-request",
    "useQuery", "useMutation", "swr", "HttpClient", "WebSocket(",
)
_RESPONSIVE_MARKERS = ('name="viewport"', "name='viewport'", "@media")

# Auth-UI evidence is tiered (Static Web Analysis & Assessment Semantics
# Hardening brief §20): a real password field is strong, structural
# evidence on its own (DETECTED); generic storage/header markers
# (`localStorage`, `Authorization`, ...) are common in code that has
# nothing to do with a login form, so they only count as weaker evidence
# (INFERRED) and only when co-occurring with an actual `<form>` in the
# same file. Bare prose mentions of "login"/"password"/"authentication"
# were never markers here at all (no word-based marker exists), so a
# README/comment mentioning those words was already never sufficient -
# this tiering makes the *storage/header* markers conservative too.
_AUTH_UI_STRONG_MARKERS = ('type="password"', "type='password'")
_AUTH_UI_WEAK_MARKERS = ("sessionStorage", "localStorage", "Authorization", "Bearer")
_AUTH_UI_FILENAME_HINTS = ("login", "signin", "sign-in", "logon")

_INTERACTIVE_UI_MARKERS = (
    "<button", "<a ", "<a>", "<input", "<select", "<textarea",
    "video controls", "audio controls", "onclick=", "addEventListener(",
)

_BROWSER_API_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Microphone (getUserMedia)", ("getUserMedia", "navigator.mediaDevices")),
    ("MediaRecorder", ("MediaRecorder",)),
    ("Speech synthesis", ("speechSynthesis", "SpeechSynthesisUtterance")),
    ("Audio processing (AudioContext)", ("AudioContext",)),
    ("Local storage", ("localStorage",)),
    ("Session storage", ("sessionStorage",)),
    ("Notifications", ("Notification(", "new Notification")),
    ("Geolocation", ("navigator.geolocation",)),
    ("Clipboard", ("navigator.clipboard",)),
    ("File reading (FileReader)", ("FileReader",)),
    ("IndexedDB", ("indexedDB",)),
)

_CSP_MARKERS = ("Content-Security-Policy", "content-security-policy")

_EXTERNAL_RESOURCE_HOST_LABELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("fonts.googleapis.com", "fonts.gstatic.com"), "Google Fonts"),
    (("cdn.jsdelivr.net",), "jsDelivr CDN"),
    (("unpkg.com",), "unpkg CDN"),
    (("cdnjs.cloudflare.com",), "cdnjs CDN"),
)

_SUSPICIOUS_HTML_DIRS = {"templates", "docs", "doc", "_build", "site"}
_WEB_ASSET_EXTENSIONS = {".css", ".js"}

_CSS_FRAMEWORK_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Bootstrap", ("bootstrap",)),
    ("Tailwind CSS", ("tailwind",)),
    ("Bulma", ("bulma",)),
    ("Foundation", ("foundation.css", "foundation.min.css", "zurb")),
)

_BUILD_SCRIPT_NAMES = {"build", "dev", "start", "preview"}
_TEST_SCRIPT_NAMES = {"test", "test:unit", "test:e2e", "e2e", "lint", "typecheck", "type-check", "coverage"}


def _frontend_source_files(files: list[ScannedFile]) -> list[ScannedFile]:
    candidates = [
        f for f in files
        if f.extension in _FRONTEND_SOURCE_EXTENSIONS
        and any(f.relative.startswith(root) or f"/{root}" in f.relative for root in _FRONTEND_SOURCE_ROOTS)
    ]
    if not candidates:
        candidates = [f for f in files if f.extension in _FRONTEND_SOURCE_EXTENSIONS]
    return candidates[:_MAX_SCANNED_FILES]


def _scan_signal(scanned: list[ScannedFile], markers: tuple[str, ...], label: str) -> FrontendSignal:
    matches: list[str] = []
    for f in scanned:
        text = read_text_safe(f.path)
        if text is None:
            continue
        if any(marker in text for marker in markers):
            matches.append(f.relative)
    note = f"heuristic, bounded scan of up to {len(scanned)} frontend source file(s)"
    if matches:
        return FrontendSignal(
            status=DetectionConfidence.DETECTED, count=len(matches),
            evidence=[Evidence(label, {"files": matches[:20], "truncated": len(matches) > 20})],
            note=note,
        )
    return FrontendSignal(status=DetectionConfidence.NOT_APPLICABLE, count=0, evidence=[], note=note)


def _detect_frontend_flag(files: list[ScannedFile], manifests: ManifestBundle) -> tuple[bool, DetectionConfidence, list[Evidence]]:
    """Manifest/config-driven frontend presence signal — mirrors
    `project_type.py`'s "frontend" `ProjectTypeDetection`, kept in sync
    deliberately rather than imported from it (that detector returns a list
    of unrelated project types; this needs just the boolean + its evidence).
    Independent of `detect_static_web` below — a plain static site has
    neither a `package.json` nor a framework config file, and must still be
    detected (Static Web Analysis brief §3/§4).
    """
    evidence: list[Evidence] = []
    deps: set[str] = set()
    if manifests.package_json is not None:
        deps = set(manifests.package_json.get("dependencies", {}) or {})
        deps |= set(manifests.package_json.get("devDependencies", {}) or {})
    matched_deps = deps & FRONTEND_PACKAGE_HINTS
    matched_config = manifests.by_name(*FRONTEND_CONFIG_MARKERS)
    if matched_deps:
        evidence.append(Evidence("dependency", {"matched": sorted(matched_deps)}))
    if matched_config:
        evidence.append(Evidence("config_file", {"matched": sorted(f.relative for f in matched_config)}))
    if evidence:
        return True, DetectionConfidence.DETECTED, evidence
    return False, DetectionConfidence.NOT_APPLICABLE, []


@dataclass
class _StaticWebResult:
    detected: bool
    frontend_type: FrontendType | None
    confidence: DetectionConfidence
    evidence: list[Evidence]
    entry_points: list[str]
    web_roots: list[str]


def _dirname(relative: str) -> str:
    return relative.rsplit("/", 1)[0] if "/" in relative else ""


def _has_asset_support(files: list[ScannedFile], dir_prefix: str) -> bool:
    prefix = f"{dir_prefix}/" if dir_prefix else ""
    return any(f.extension in _WEB_ASSET_EXTENSIONS and f.relative.startswith(prefix) for f in files)


def detect_static_web(files: list[ScannedFile]) -> _StaticWebResult:
    """Static-site entry-point detection with conservative false-positive
    guards (Static Web Analysis brief §4/§10/§20). `coverage`/`htmlcov`
    directories are already excluded by `filesystem.walk` itself; a lone
    HTML file under a generated-docs- or server-template-like directory
    (`docs/`, `templates/`, ...) with no accompanying CSS/JS is treated as
    insufficient evidence rather than "frontend detected" — never silently
    assumed to be the application's real frontend (brief §20.A/§20.C).
    """
    html_files = [f for f in files if f.extension in (".html", ".htm")]
    if not html_files:
        return _StaticWebResult(False, None, DetectionConfidence.NOT_APPLICABLE, [], [], [])

    index_files = [f for f in html_files if f.relative.rsplit("/", 1)[-1].lower() in ("index.html", "index.htm")]
    index_dirs = sorted({_dirname(f.relative) for f in index_files})

    root_index = [f for f in index_files if _dirname(f.relative) == ""]
    if root_index:
        other_dirs = [d for d in index_dirs if d != ""]
        evidence = [Evidence("entry_point", {"file": root_index[0].relative})]
        if other_dirs:
            evidence.append(Evidence("multiple_web_roots", {
                "roots": other_dirs,
                "note": "multiple HTML entry points detected - not silently collapsed into one application",
            }))
        return _StaticWebResult(
            True, FrontendType.STATIC_WEB, DetectionConfidence.DETECTED, evidence,
            entry_points=[root_index[0].relative], web_roots=(["."] + other_dirs),
        )

    if len(index_dirs) > 1:
        # Monorepo-style: several independent app roots, none at the scan
        # root itself (brief §21) - report bounded evidence rather than
        # guessing which one is "the" frontend.
        entry_points = sorted(f.relative for f in index_files)
        evidence = [Evidence("multiple_web_roots", {
            "roots": index_dirs,
            "note": "multiple HTML entry points detected across separate directories",
        })]
        return _StaticWebResult(
            True, FrontendType.STATIC_WEB, DetectionConfidence.DETECTED, evidence,
            entry_points=entry_points, web_roots=index_dirs,
        )

    if len(index_dirs) == 1:
        candidate_dir = index_dirs[0]
        dir_name = candidate_dir.split("/")[-1]
        entry = next(f.relative for f in index_files)
        if dir_name in _SUSPICIOUS_HTML_DIRS:
            return _StaticWebResult(
                False, None, DetectionConfidence.NOT_APPLICABLE,
                [Evidence("excluded_html", {
                    "reason": f"HTML found only under a generated/template-like directory ({candidate_dir!r}) "
                              "with no supporting structure",
                })],
                [], [],
            )
        has_support = _has_asset_support(files, candidate_dir)
        multi_page = len([f for f in html_files if _dirname(f.relative) == candidate_dir]) >= 2
        if has_support or multi_page:
            return _StaticWebResult(
                True, FrontendType.STATIC_WEB, DetectionConfidence.DETECTED,
                [Evidence("entry_point", {"file": entry})],
                entry_points=[entry], web_roots=[candidate_dir],
            )
        return _StaticWebResult(
            True, FrontendType.UNKNOWN_WEB, DetectionConfidence.INFERRED,
            [Evidence("weak_entry_point", {
                "file": entry, "reason": "no accompanying CSS/JS and only one HTML page found",
            })],
            entry_points=[entry], web_roots=[candidate_dir],
        )

    # No index.html anywhere, but other HTML pages exist.
    common_dirs = sorted({_dirname(f.relative) for f in html_files})
    non_suspicious = [d for d in common_dirs if d.split("/")[-1] not in _SUSPICIOUS_HTML_DIRS]
    if len(html_files) >= 2 and non_suspicious and any(_has_asset_support(files, d) for d in non_suspicious):
        return _StaticWebResult(
            True, FrontendType.STATIC_WEB, DetectionConfidence.INFERRED,
            [Evidence("html_pages", {"count": len(html_files), "dirs": common_dirs})],
            entry_points=[], web_roots=non_suspicious,
        )
    return _StaticWebResult(
        False, None, DetectionConfidence.NOT_APPLICABLE,
        [Evidence("insufficient_html_evidence", {"count": len(html_files), "dirs": common_dirs})],
        [], [],
    )


def _detect_css_frameworks(files: list[ScannedFile]) -> list[str]:
    """Filename/href evidence only - never inferred from arbitrary class
    names like `class="container"` (brief §8's explicit caution).
    """
    found: set[str] = set()
    candidates = [f for f in files if f.extension in (".css", ".html", ".htm")][:_MAX_SCANNED_FILES]
    for f in candidates:
        haystack_parts = [f.relative.lower()]
        text = read_text_safe(f.path)
        if text is not None and f.extension in (".html", ".htm"):
            haystack_parts.append(text.lower())
        haystack = " ".join(haystack_parts)
        for name, markers in _CSS_FRAMEWORK_MARKERS:
            if name not in found and any(marker in haystack for marker in markers):
                found.add(name)
        if len(found) == len(_CSS_FRAMEWORK_MARKERS):
            break
    return sorted(found)


_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style\b[^>]*>", re.IGNORECASE)
_SRC_ATTR_RE = re.compile(r"\bsrc\s*=", re.IGNORECASE)
_EXTERNAL_STYLESHEET_RE = re.compile(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?://', re.IGNORECASE)
_EXTERNAL_SCRIPT_RE = re.compile(r'<script[^>]+src=["\']https?://', re.IGNORECASE)
_EXTERNAL_IMAGE_RE = re.compile(r'<img[^>]+src=["\']https?://', re.IGNORECASE)


def _count_inline_markup(files: list[ScannedFile]) -> tuple[int, int]:
    """Counts `<style>...</style>` blocks and `<script>` blocks *without* a
    `src=` attribute across HTML files - no HTML parser, just tag matching
    (brief §6/§14: stdlib-only, never a DOM parse). Deliberately separate
    from `css_file_count`/`js_file_count` (external files) so a single-file
    app with substantial inline CSS/JS is never misreported as "CSS: 0,
    JavaScript: 0" (the SpeakFlow real-world case this brief exists for).
    """
    html_files = [f for f in files if f.extension in (".html", ".htm")][:_MAX_SCANNED_FILES]
    inline_css = 0
    inline_js = 0
    for f in html_files:
        text = read_text_safe(f.path)
        if text is None:
            continue
        inline_css += len(_STYLE_TAG_RE.findall(text))
        for tag in _SCRIPT_TAG_RE.findall(text):
            if not _SRC_ATTR_RE.search(tag):
                inline_js += 1
    return inline_css, inline_js


def _detect_browser_apis(scanned: list[ScannedFile]) -> list[str]:
    """Bounded marker scan for common browser (not backend) APIs - kept
    structurally separate from `_API_CLIENT_MARKERS` (brief §21: a
    microphone/storage/speech API is not a "backend API client"). Always
    reported as "detected," never "working" - static text matching cannot
    prove the API call actually succeeds at runtime (brief §16).
    """
    found: set[str] = set()
    for f in scanned:
        text = read_text_safe(f.path)
        if text is None:
            continue
        for label, markers in _BROWSER_API_MARKERS:
            if label not in found and any(marker in text for marker in markers):
                found.add(label)
        if len(found) == len(_BROWSER_API_MARKERS):
            break
    return sorted(found)


def _detect_external_resources(scanned: list[ScannedFile]) -> list[str]:
    """Bounded evidence of externally-hosted CSS/JS/images (brief §18) -
    never fetched, never treated as a vulnerability, just a few well-known
    hosts normalized to a friendly label plus generic external-resource
    categories.
    """
    found: set[str] = set()
    html_files = [f for f in scanned if f.extension in (".html", ".htm")]
    for f in html_files:
        text = read_text_safe(f.path)
        if text is None:
            continue
        for hosts, label in _EXTERNAL_RESOURCE_HOST_LABELS:
            if label not in found and any(host in text for host in hosts):
                found.add(label)
        if "External stylesheet" not in found and _EXTERNAL_STYLESHEET_RE.search(text):
            found.add("External stylesheet")
        if "External script" not in found and _EXTERNAL_SCRIPT_RE.search(text):
            found.add("External script")
        if "External image" not in found and _EXTERNAL_IMAGE_RE.search(text):
            found.add("External image")
    return sorted(found)


def _scan_auth_ui(scanned: list[ScannedFile]) -> FrontendSignal:
    """Tiered auth-UI evidence (brief §20): a real password field is strong
    structural evidence on its own; generic storage/header markers
    (`localStorage`, `Authorization`, ...) are common in unrelated code, so
    they only count when a `<form>` is also present in the same file, and
    only ever reach `INFERRED`, never `DETECTED`. No marker here is a bare
    prose word ("login"/"password"/"authentication") - a README or comment
    mentioning those words was never sufficient and still isn't.
    """
    note = f"heuristic, bounded scan of up to {len(scanned)} frontend source file(s)"
    strong_files: list[str] = []
    weak_files: list[str] = []
    for f in scanned:
        text = read_text_safe(f.path)
        if text is None:
            continue
        if any(marker in text for marker in _AUTH_UI_STRONG_MARKERS):
            strong_files.append(f.relative)
        elif "<form" in text and any(marker in text for marker in _AUTH_UI_WEAK_MARKERS):
            weak_files.append(f.relative)
    if strong_files:
        return FrontendSignal(
            status=DetectionConfidence.DETECTED, count=len(strong_files),
            evidence=[Evidence("auth_ui_marker", {"files": strong_files[:20]})], note=note,
        )
    if weak_files:
        return FrontendSignal(
            status=DetectionConfidence.INFERRED, count=len(weak_files),
            evidence=[Evidence("auth_ui_weak_marker", {"files": weak_files[:20]})], note=note,
        )
    return FrontendSignal(status=DetectionConfidence.NOT_APPLICABLE, count=0, evidence=[], note=note)


def _detect_application_pattern(
    html_page_count: int, inline_js_count: int, interactive_ui: FrontendSignal,
    api_clients: FrontendSignal, browser_apis: list[str],
) -> str | None:
    """Bounded heuristic (brief §17) - never asserted with unwarranted
    confidence: multi-page evidence is direct; a single page is only ever
    called a "single-page application" when there's real supporting
    behavioral evidence (inline JS + interactivity/API/browser-API usage),
    otherwise it's left as a plain static document.
    """
    if html_page_count >= 2:
        return "static_multi_page"
    if html_page_count == 1:
        has_rich_behavior = (
            inline_js_count > 0
            and (
                interactive_ui.status == DetectionConfidence.DETECTED
                or api_clients.status == DetectionConfidence.DETECTED
                or bool(browser_apis)
            )
        )
        return "single_page_application" if has_rich_behavior else "static_document"
    return None


def _extract_scripts(manifests: ManifestBundle) -> tuple[dict[str, str], dict[str, str]]:
    """Copy script name/command pairs only — never execute them (brief §25/§26)."""
    build_scripts: dict[str, str] = {}
    test_scripts: dict[str, str] = {}
    if not manifests.package_json:
        return build_scripts, test_scripts
    scripts = manifests.package_json.get("scripts")
    if not isinstance(scripts, dict):
        return build_scripts, test_scripts
    for name, command in scripts.items():
        if not isinstance(command, str):
            continue
        if name in _BUILD_SCRIPT_NAMES:
            build_scripts[name] = command
        elif name in _TEST_SCRIPT_NAMES:
            test_scripts[name] = command
    return build_scripts, test_scripts


def _extract_env_public_keys(files: list[ScannedFile]) -> list[str]:
    """Key names only from `.env.example`/`.env.template` — values are never
    read into the returned list (brief §16: never report secret values).
    """
    keys: list[str] = []
    for f in files:
        name = f.relative.rsplit("/", 1)[-1]
        if name not in (".env.example", ".env.template"):
            continue
        text = read_text_safe(f.path)
        if text is None:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def detect_frontend(files: list[ScannedFile], manifests: ManifestBundle, frameworks=None) -> FrontendInfo:
    """`frameworks` is `ProjectModel.frameworks` (already populated by the
    time this step runs in `discovery/engine.py`'s step loop) - used only to
    give manifest/config-driven framework evidence precedence over a
    static-HTML guess (Static Web Analysis brief §26: a React project must
    never be misclassified as Static Web just because it also has an
    `index.html`).
    """
    fw_names = {f.name for f in (frameworks or [])}
    has_frontend_framework = bool(fw_names & FRONTEND_FRAMEWORK_NAMES)
    has_backend_framework = bool(fw_names & BACKEND_WEB_FRAMEWORK_NAMES)

    manifest_detected, manifest_confidence, manifest_evidence = _detect_frontend_flag(files, manifests)
    static = detect_static_web(files)

    detected = manifest_detected or static.detected or has_frontend_framework
    if not detected:
        return FrontendInfo(detected=False, detection_confidence=DetectionConfidence.NOT_APPLICABLE, detection_evidence=[])

    if has_frontend_framework:
        frontend_type = FrontendType.FULL_STACK_WEB if has_backend_framework else FrontendType.FRAMEWORK_WEB
        confidence, evidence = manifest_confidence, manifest_evidence
    elif static.detected:
        frontend_type = FrontendType.FULL_STACK_WEB if has_backend_framework else static.frontend_type
        confidence, evidence = static.confidence, static.evidence
    else:
        frontend_type = FrontendType.UNKNOWN_WEB
        confidence, evidence = manifest_confidence, manifest_evidence

    scanned = _frontend_source_files(files)
    routes = _scan_signal(scanned, _ROUTE_MARKERS, "route_marker")
    if not routes.count:
        # directory-based routing (Next.js `app/`/`pages/`, SvelteKit `src/routes/`)
        route_dirs = sorted({
            f.relative.split("/")[0] + "/" for f in files
            if f.relative.startswith(("app/", "pages/", "src/routes/"))
        })
        if route_dirs:
            routes = FrontendSignal(
                status=DetectionConfidence.DETECTED, count=len(route_dirs),
                evidence=[Evidence("route_directory", {"matched": route_dirs})],
                note=routes.note,
            )
    components = _scan_signal(scanned, (), "component_marker")
    component_dirs = sorted({
        part for f in files for part in [f.relative] if any(hint in part for hint in _COMPONENT_DIR_HINTS)
    })
    if component_dirs:
        components = FrontendSignal(
            status=DetectionConfidence.DETECTED, count=len(component_dirs),
            evidence=[Evidence("component_directory", {"count": len(component_dirs)})],
            note=f"heuristic, bounded scan of up to {len(scanned)} frontend source file(s)",
        )
    forms = _scan_signal(scanned, _FORM_MARKERS, "form_marker")
    api_clients = _scan_signal(scanned, _API_CLIENT_MARKERS, "api_client_marker")
    responsive = _scan_signal(scanned, _RESPONSIVE_MARKERS, "responsive_marker")
    interactive_ui = _scan_signal(scanned, _INTERACTIVE_UI_MARKERS, "interactive_ui_marker")
    csp = _scan_signal(scanned, _CSP_MARKERS, "csp_marker")

    auth_ui = _scan_auth_ui(scanned)
    if auth_ui.status == DetectionConfidence.NOT_APPLICABLE:
        auth_filenames = [
            f.relative for f in scanned
            if any(hint in f.relative.rsplit("/", 1)[-1].lower() for hint in _AUTH_UI_FILENAME_HINTS)
        ]
        if auth_filenames:
            auth_ui = FrontendSignal(
                status=DetectionConfidence.DETECTED, count=len(auth_filenames),
                evidence=[Evidence("auth_ui_filename", {"files": auth_filenames})],
                note=auth_ui.note,
            )

    build_scripts, test_scripts = _extract_scripts(manifests)
    frontend_test_dirs = sorted({
        f.relative.split("/")[0] if "/" not in f.relative[:-1] else "/".join(f.relative.split("/")[:-1])
        for f in files
        if any(f.relative.startswith(root) for root in _FRONTEND_SOURCE_ROOTS)
        and ("__tests__" in f.relative or "/test" in f.relative.lower() or "/spec" in f.relative.lower())
    })
    env_public_keys = _extract_env_public_keys(files)
    css_frameworks = _detect_css_frameworks(files)
    html_page_count = sum(1 for f in files if f.extension in (".html", ".htm"))
    css_file_count = sum(1 for f in files if f.extension == ".css")
    js_file_count = sum(1 for f in files if f.extension in (".js", ".mjs", ".cjs"))
    inline_css_count, inline_js_count = _count_inline_markup(files)
    browser_apis = _detect_browser_apis(scanned)
    external_resources = _detect_external_resources(scanned)
    application_pattern = _detect_application_pattern(
        html_page_count, inline_js_count, interactive_ui, api_clients, browser_apis,
    )

    return FrontendInfo(
        detected=True,
        detection_confidence=confidence,
        detection_evidence=evidence,
        frontend_type=frontend_type,
        entry_points=static.entry_points,
        web_roots=static.web_roots,
        html_page_count=html_page_count,
        css_file_count=css_file_count,
        js_file_count=js_file_count,
        css_frameworks=css_frameworks,
        routes=routes,
        components=components,
        forms=forms,
        api_clients=api_clients,
        responsive=responsive,
        auth_ui=auth_ui,
        inline_css_count=inline_css_count,
        inline_js_count=inline_js_count,
        interactive_ui=interactive_ui,
        browser_apis=browser_apis,
        application_pattern=application_pattern,
        external_resources=external_resources,
        csp=csp,
        build_scripts=build_scripts,
        test_scripts=test_scripts,
        frontend_test_directories=frontend_test_dirs,
        env_public_keys=env_public_keys,
    )
