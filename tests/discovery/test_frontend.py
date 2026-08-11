from universal_test.core.models.enums import DetectionConfidence
from universal_test.discovery.engine import discover


def test_react_vite_vitest_fully_detected(fixture_path):
    model = discover(fixture_path("react-vite-vitest"))
    framework_names = {d.name for d in model.frameworks}
    build_names = {d.name for d in model.build_systems}
    test_names = {d.name for d in model.test_frameworks}

    assert "React" in framework_names
    assert "Vite" in build_names
    assert {"Vitest", "Playwright", "Testing Library"} <= test_names

    assert model.frontend.detected is True
    assert model.frontend.detection_confidence == DetectionConfidence.DETECTED
    assert model.frontend.routes.status == DetectionConfidence.DETECTED
    assert model.frontend.forms.status == DetectionConfidence.DETECTED
    assert model.frontend.api_clients.status == DetectionConfidence.DETECTED
    assert "build" in model.frontend.build_scripts
    assert "test" in model.frontend.test_scripts
    assert model.frontend.frontend_test_directories
    # env values must never leak, only key names
    assert model.frontend.env_public_keys == ["VITE_API_BASE_URL", "VITE_FEATURE_FLAG_NEW_UI"]


def test_vue_app_detected(fixture_path):
    model = discover(fixture_path("vue-app"))
    framework_names = {d.name for d in model.frameworks}
    build_names = {d.name for d in model.build_systems}

    assert "Vue" in framework_names
    assert "Vite" in build_names
    assert model.frontend.detected is True
    assert model.frontend.routes.status == DetectionConfidence.DETECTED
    assert model.frontend.forms.status == DetectionConfidence.DETECTED


def test_angular_app_detected(fixture_path):
    model = discover(fixture_path("angular-app"))
    framework_names = {d.name for d in model.frameworks}
    build_names = {d.name for d in model.build_systems}
    test_names = {d.name for d in model.test_frameworks}

    assert "Angular" in framework_names
    assert "Angular CLI" in build_names
    assert {"Karma", "Jasmine"} <= test_names
    assert model.frontend.detected is True
    assert model.frontend.forms.status == DetectionConfidence.DETECTED
    assert model.frontend.api_clients.status == DetectionConfidence.DETECTED


def test_nextjs_app_detected_as_meta_framework_distinct_from_react(fixture_path):
    model = discover(fixture_path("nextjs-app"))
    framework_names = {d.name for d in model.frameworks}

    # React (framework) and Next.js (meta-framework) are distinct facts (brief §7)
    assert "React" in framework_names
    assert "Next.js" in framework_names
    assert model.frontend.detected is True
    # directory-based routing evidence (app/) must be picked up even with no <Route> markers
    assert model.frontend.routes.status == DetectionConfidence.DETECTED


def test_sveltekit_app_detects_svelte_and_sveltekit_separately(fixture_path):
    model = discover(fixture_path("sveltekit-app"))
    framework_names = {d.name for d in model.frameworks}

    assert "Svelte" in framework_names
    assert "SvelteKit" in framework_names
    assert model.frontend.detected is True


def test_frontend_no_tests_reports_no_test_framework_without_claiming_broken(fixture_path):
    model = discover(fixture_path("frontend-no-tests"))
    assert model.frontend.detected is True
    assert model.test_frameworks == []
    # discovery itself makes no health judgement - that's the assessment layer's job
    assert model.frontend.routes.status != DetectionConfidence.DETECTED


def test_malformed_package_json_does_not_crash_discovery(fixture_path):
    model = discover(fixture_path("frontend-malformed-package-json"))
    assert any("package.json" in w for w in model.warnings)
    # config-file evidence (vite.config.js) still lets frontend be detected
    # even though the manifest itself failed to parse
    assert model.frontend.detected is True


def test_frontend_empty_dir_no_false_signals(fixture_path):
    model = discover(fixture_path("frontend-empty-dir"))
    assert model.frontend.detected is True
    assert model.frontend.routes.count == 0
    assert model.frontend.forms.count == 0


def test_backend_readme_mentioning_react_is_not_a_false_positive(fixture_path):
    model = discover(fixture_path("backend-mentions-react"))
    framework_names = {d.name for d in model.frameworks}
    assert "React" not in framework_names
    assert "Vue" not in framework_names
    assert model.frontend.detected is False


def test_frontend_signal_notes_state_the_scan_bound(fixture_path):
    model = discover(fixture_path("react-vite-vitest"))
    assert "bounded scan" in model.frontend.routes.note
    assert "bounded scan" in model.frontend.forms.note
