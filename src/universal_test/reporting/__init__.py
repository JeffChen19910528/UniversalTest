"""Unified report generators: json/markdown/html (Phase 5).

Each takes an `AssessReportBundle` (assessment + the raw per-phase results
it was built from). Offline-safe: the HTML report has no CDN dependency and
no external JavaScript; nothing here ever includes a secret value.
"""

from universal_test.reporting.html_report import to_html
from universal_test.reporting.json_report import to_dict, to_json
from universal_test.reporting.markdown_report import to_markdown
from universal_test.reporting.report_bundle import AssessReportBundle

__all__ = ["to_html", "to_dict", "to_json", "to_markdown", "AssessReportBundle"]
