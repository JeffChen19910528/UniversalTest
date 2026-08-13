"""Localization parity (Phase 10 spec section 37): every EN key must have a
zh-TW counterpart and vice versa -- no missing localization keys.

Uses Node (already relied on elsewhere in this project to validate GUI JS
syntax) to load the real `I18N` object rather than re-implementing a JS
object-literal parser in Python, which would be its own source of false
positives/negatives.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

I18N_PATH = Path(__file__).resolve().parents[2] / "src/universal_test/gui/static/i18n.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not available in this environment")


def _load_i18n_keys() -> dict[str, list[str]]:
    script = (
        f"const fs = require('fs');"
        f"const code = fs.readFileSync({json.dumps(str(I18N_PATH))}, 'utf8');"
        f"const I18N = new Function(code + '\\nreturn I18N;')();"
        f"console.log(JSON.stringify({{zh: Object.keys(I18N.zh), en: Object.keys(I18N.en)}}));"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10, check=True)
    return json.loads(result.stdout)


def test_en_and_zh_tw_have_identical_key_sets():
    keys = _load_i18n_keys()
    zh_keys, en_keys = set(keys["zh"]), set(keys["en"])
    missing_in_zh = en_keys - zh_keys
    missing_in_en = zh_keys - en_keys
    assert not missing_in_zh, f"keys present in EN but missing from zh-TW: {sorted(missing_in_zh)}"
    assert not missing_in_en, f"keys present in zh-TW but missing from EN: {sorted(missing_in_en)}"


def test_no_empty_translation_values():
    script = (
        f"const fs = require('fs');"
        f"const code = fs.readFileSync({json.dumps(str(I18N_PATH))}, 'utf8');"
        f"const I18N = new Function(code + '\\nreturn I18N;')();"
        f"const empties = [];"
        f"for (const lang of ['zh', 'en']) {{"
        f"  for (const [k, v] of Object.entries(I18N[lang])) {{"
        f"    if (typeof v !== 'string' || v.trim() === '') empties.push(lang + '.' + k);"
        f"  }}"
        f"}}"
        f"console.log(JSON.stringify(empties));"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10, check=True)
    empties = json.loads(result.stdout)
    assert empties == [], f"empty translation values: {empties}"


def test_web_assessment_keys_present_in_both_languages():
    keys = _load_i18n_keys()
    required = {
        "web_assess_title", "web_assess_intro", "web_assess_analyze_btn", "web_assess_not_web",
        "web_assess_planned_checks", "web_assess_not_included", "web_check_structure",
        "web_check_static_analysis", "web_check_browser_smoke", "web_check_console_errors",
        "web_not_included_login", "web_not_included_permissions", "web_not_included_visual",
        "web_not_included_security", "web_not_included_accessibility",
        "web_type_static_web", "web_type_framework_web", "web_type_full_stack_web", "web_type_unknown_web",
        "web_external_warning_title", "web_external_warning_confirm",
        "web_browser_confirm_intro", "web_browser_confirm_never_intro",
        "web_assess_start_btn", "web_assess_no_target_hint",
        "browser_testing_label", "browser_testing_hint", "browser_testing_not_assessed_hint",
        "full_assessment_title",
    }
    assert required.issubset(set(keys["zh"]))
    assert required.issubset(set(keys["en"]))
