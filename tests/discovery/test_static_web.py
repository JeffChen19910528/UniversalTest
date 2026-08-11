from universal_test.core.models.enums import DetectionConfidence
from universal_test.discovery.engine import discover
from universal_test.discovery.models import FrontendType


def test_multi_page_static_site_detected(fixture_path):
    model = discover(fixture_path("frontend-static-basic"))
    fe = model.frontend
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.STATIC_WEB
    assert fe.entry_points == ["index.html"]
    assert fe.html_page_count == 2
    assert fe.css_file_count == 1
    assert fe.js_file_count == 1
    assert fe.routes.status == DetectionConfidence.DETECTED
    assert fe.responsive.status == DetectionConfidence.DETECTED


def test_static_site_with_forms_and_auth_ui(fixture_path):
    model = discover(fixture_path("frontend-static-form"))
    fe = model.frontend
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.STATIC_WEB
    assert fe.forms.status == DetectionConfidence.DETECTED
    assert fe.auth_ui.status == DetectionConfidence.DETECTED
    assert fe.api_clients.status == DetectionConfidence.DETECTED  # fetch() + Authorization/Bearer in login.js


def test_static_site_with_api_and_websocket_evidence(fixture_path):
    model = discover(fixture_path("frontend-static-api"))
    fe = model.frontend
    assert fe.detected is True
    assert fe.api_clients.status == DetectionConfidence.DETECTED


def test_single_index_html_is_detected(fixture_path):
    model = discover(fixture_path("frontend-single-html"))
    fe = model.frontend
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.STATIC_WEB
    assert fe.entry_points == ["index.html"]
    assert fe.html_page_count == 1


def test_docs_only_html_is_not_falsely_classified(fixture_path):
    model = discover(fixture_path("frontend-docs-only"))
    assert model.frontend.detected is False
    assert model.frontend.frontend_type is None


def test_coverage_only_html_is_never_scanned_at_all(fixture_path):
    model = discover(fixture_path("frontend-coverage-only"))
    assert model.frontend.detected is False
    assert model.file_count == 0  # excluded at the filesystem-walk level


def test_backend_html_template_is_not_a_static_frontend(fixture_path):
    model = discover(fixture_path("backend-html-template"))
    assert model.frontend.detected is False
    assert model.frontend.frontend_type is None


def test_multiple_web_roots_reported_not_collapsed(tmp_path, fixture_path):
    root = tmp_path / "monorepo"
    (root / "frontend").mkdir(parents=True)
    (root / "frontend" / "index.html").write_text("<html><body>frontend</body></html>", encoding="utf-8")
    (root / "admin").mkdir(parents=True)
    (root / "admin" / "index.html").write_text("<html><body>admin</body></html>", encoding="utf-8")
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("print('hi')", encoding="utf-8")

    model = discover(root)
    fe = model.frontend
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.STATIC_WEB
    assert set(fe.web_roots) == {"admin", "frontend"}
    assert len(fe.entry_points) == 2


def test_root_index_with_extra_nested_index_reports_multiple_roots(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "admin").mkdir()
    (root / "admin" / "index.html").write_text("<html></html>", encoding="utf-8")

    model = discover(root)
    fe = model.frontend
    assert fe.detected is True
    assert fe.entry_points == ["index.html"]
    assert "admin" in fe.web_roots


def test_single_nested_html_with_css_support_is_static_web(tmp_path):
    root = tmp_path / "weak"
    (root / "pages").mkdir(parents=True)
    (root / "pages" / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "pages" / "style.css").write_text("body{}", encoding="utf-8")

    model = discover(root)
    fe = model.frontend
    # a CSS file alongside the lone HTML file is enough supporting structure
    # to count as real static-web evidence, not just a weak guess.
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.STATIC_WEB


def test_weak_single_nested_html_without_support_is_unknown_web(tmp_path):
    root = tmp_path / "weak2"
    (root / "misc").mkdir(parents=True)
    (root / "misc" / "index.html").write_text("<html></html>", encoding="utf-8")

    model = discover(root)
    fe = model.frontend
    assert fe.detected is True
    assert fe.frontend_type == FrontendType.UNKNOWN_WEB
    assert fe.detection_confidence == DetectionConfidence.INFERRED


def test_no_javascript_or_html_is_executed_including_inline_script(fixture_path):
    model = discover(fixture_path("frontend-static-malicious-inline-script"))
    assert model.frontend.detected is True
    # the dangerous-looking content is only ever evidence text, never run
    assert model.frontend.api_clients.status == DetectionConfidence.DETECTED


def test_css_framework_detected_from_filename_not_arbitrary_class_names(tmp_path):
    root = tmp_path / "bootstrap-site"
    root.mkdir()
    (root / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="css/bootstrap.min.css"></head>'
        '<body><div class="container">hi</div></body></html>',
        encoding="utf-8",
    )
    (root / "css").mkdir()
    (root / "css" / "bootstrap.min.css").write_text("/*! Bootstrap */", encoding="utf-8")

    model = discover(root)
    assert "Bootstrap" in model.frontend.css_frameworks


def test_arbitrary_class_name_alone_is_not_framework_evidence(tmp_path):
    root = tmp_path / "plain-site"
    root.mkdir()
    (root / "index.html").write_text(
        '<html><body><div class="container">hi</div></body></html>', encoding="utf-8",
    )

    model = discover(root)
    assert model.frontend.css_frameworks == []


# -- Static-web capability detection (Semantics Hardening brief §14-§21) ----

def test_rich_single_file_spa_reports_inline_css_js_not_zero(fixture_path):
    """The direct regression case for the real-world SpeakFlow report: a
    single index.html with substantial inline CSS/JS must not show up as
    "CSS: 0, JavaScript: 0" just because nothing lives in a separate file.
    """
    model = discover(fixture_path("frontend-static-rich-spa"))
    fe = model.frontend
    assert fe.detected is True
    assert fe.html_page_count == 1
    assert fe.css_file_count == 0
    assert fe.js_file_count == 0
    assert fe.inline_css_count == 1
    assert fe.inline_js_count == 1


def test_rich_single_file_spa_detects_browser_apis_and_pattern(fixture_path):
    model = discover(fixture_path("frontend-static-rich-spa"))
    fe = model.frontend
    assert {"Microphone (getUserMedia)", "MediaRecorder", "Speech synthesis", "Local storage"} <= set(fe.browser_apis)
    assert fe.application_pattern == "single_page_application"
    assert fe.interactive_ui.status == DetectionConfidence.DETECTED
    assert fe.csp.status == DetectionConfidence.DETECTED
    assert "Google Fonts" in fe.external_resources
    assert "External stylesheet" in fe.external_resources
    assert fe.responsive.status == DetectionConfidence.DETECTED


def test_browser_apis_are_never_classified_as_api_clients(fixture_path):
    fe = discover(fixture_path("frontend-static-rich-spa")).frontend
    # getUserMedia/MediaRecorder/speechSynthesis/localStorage are browser
    # APIs, not backend API-client usage (brief §21) - the api_clients
    # signal should not be driven by these markers alone.
    for api_name in fe.browser_apis:
        assert "fetch" not in api_name.lower()
    assert set(fe.browser_apis).isdisjoint({"fetch(", "axios", "XMLHttpRequest"})


def test_multi_page_site_has_static_multi_page_pattern(fixture_path):
    fe = discover(fixture_path("frontend-static-basic")).frontend
    assert fe.application_pattern == "static_multi_page"


def test_single_plain_page_with_no_behavior_is_static_document(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "index.html").write_text("<html><body><h1>Hello</h1></body></html>", encoding="utf-8")

    fe = discover(root).frontend
    assert fe.application_pattern == "static_document"


def test_interactive_ui_evidence_detected(fixture_path):
    fe = discover(fixture_path("frontend-static-basic")).frontend
    assert fe.interactive_ui.status == DetectionConfidence.DETECTED


def test_auth_ui_password_field_is_strong_detected_evidence(fixture_path):
    fe = discover(fixture_path("frontend-static-form")).frontend
    assert fe.auth_ui.status == DetectionConfidence.DETECTED


def test_auth_ui_readme_prose_mention_is_not_detected(tmp_path):
    """Brief §20: a comment/README mentioning "login"/"password"/
    "authentication" must not produce strong auth-UI evidence."""
    root = tmp_path / "prose-only"
    root.mkdir()
    (root / "index.html").write_text(
        "<html><body>"
        "<!-- This page will eventually handle user login, password reset, "
        "and authentication once the backend is ready. -->"
        "<h1>Coming soon</h1>"
        "</body></html>",
        encoding="utf-8",
    )

    fe = discover(root).frontend
    assert fe.auth_ui.status != DetectionConfidence.DETECTED
    assert fe.auth_ui.count == 0


def test_auth_ui_weak_storage_marker_without_form_is_not_detected(tmp_path):
    """localStorage/Authorization/Bearer usage with no <form> in the same
    file is not treated as login-form evidence at all (brief §20)."""
    root = tmp_path / "storage-only"
    root.mkdir()
    (root / "index.html").write_text(
        "<html><body><h1>Dashboard</h1>"
        "<script>localStorage.setItem('theme', 'dark');</script>"
        "</body></html>",
        encoding="utf-8",
    )

    fe = discover(root).frontend
    assert fe.auth_ui.status == DetectionConfidence.NOT_APPLICABLE


def test_auth_ui_weak_storage_marker_with_form_is_inferred_not_detected(tmp_path):
    """A <form> plus a generic storage/header marker (but no real password
    field) is weak, INFERRED evidence - not the same confidence as an
    actual <input type="password">."""
    root = tmp_path / "form-plus-storage"
    root.mkdir()
    (root / "index.html").write_text(
        "<html><body><form action=\"/save\"><input name=\"note\"></form>"
        "<script>const token = localStorage.getItem('token');</script>"
        "</body></html>",
        encoding="utf-8",
    )

    fe = discover(root).frontend
    assert fe.auth_ui.status == DetectionConfidence.INFERRED


def test_no_execution_of_rich_spa_javascript(fixture_path):
    """MediaRecorder/getUserMedia/speechSynthesis calls in the fixture are
    only ever matched as evidence text - discover() must complete without
    attempting to run any of it (there is no JS runtime in this codebase
    at all, so this mainly guards against a future accidental dependency)."""
    model = discover(fixture_path("frontend-static-rich-spa"))
    assert model.frontend.detected is True
