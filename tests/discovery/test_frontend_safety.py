"""Frontend discovery must never execute repository content (brief §25/§26/§29):
package.json `scripts` are untrusted data, not something discovery may invoke.
"""

import socket
import subprocess

import pytest

from universal_test.discovery.engine import discover


@pytest.fixture(autouse=True)
def _fail_on_process_or_network(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("discovery must never spawn a subprocess")

    def _boom_socket(*args, **kwargs):
        raise AssertionError("discovery must never open a network socket")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(socket, "socket", _boom_socket)


def test_discovery_never_executes_malicious_package_scripts(fixture_path):
    model = discover(fixture_path("frontend-malicious-scripts"))
    assert model.frontend.detected is True
    # the malicious commands are copied as inert strings, never run
    assert model.frontend.build_scripts.get("build") == "vite build"
    assert model.frontend.test_scripts.get("test") == "vitest run"


def test_discovery_never_executes_inline_html_script(fixture_path):
    model = discover(fixture_path("frontend-static-malicious-inline-script"))
    assert model.frontend.detected is True
    # the fetch()/document.write()/eval() calls inside <script> are only
    # ever matched as substrings for evidence - never parsed as JS, never run
    assert model.frontend.api_clients.status.value == "detected"


def test_discovery_of_every_frontend_fixture_never_executes_anything(fixture_path):
    for name in (
        "react-vite-vitest", "vue-app", "angular-app", "nextjs-app",
        "sveltekit-app", "frontend-no-tests", "frontend-malformed-package-json",
        "frontend-empty-dir", "frontend-malicious-scripts",
        "frontend-static-basic", "frontend-static-form", "frontend-static-api",
        "frontend-single-html", "frontend-docs-only", "frontend-coverage-only",
        "backend-html-template", "frontend-static-malicious-inline-script",
        "frontend-static-rich-spa",
    ):
        discover(fixture_path(name))
