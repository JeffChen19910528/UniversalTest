"""Discovery-specific output serializers (text/JSON/Markdown).

Phase 5 will introduce the general JSON/HTML/Markdown report generators
covering the full assessment pipeline (skill.md §19); until then, discovery
needs its own lightweight renderers so `universal-test scan` is actually
useful today. These live in `discovery/` rather than `reporting/` because
they only know about `ProjectModel`, not the report shape Phase 5 defines —
`reporting/` stays empty until that phase, keeping the architecture boundary
intact.
"""

from __future__ import annotations

import json

from universal_test.discovery.models import ProjectModel


def to_json(model: ProjectModel) -> str:
    return json.dumps(model.to_dict(), indent=2, sort_keys=False)


def _fmt_confidence(confidence_value: str) -> str:
    return confidence_value.upper()


def to_text(model: ProjectModel) -> str:
    lines: list[str] = []
    lines.append("Universal Test Framework")
    lines.append("=" * 25)
    lines.append("")
    lines.append(f"Path: {model.root_path}")
    lines.append(f"Scanned: {model.scanned_at}")
    lines.append("")

    lines.append("Repository")
    lines.append("-" * 10)
    repo = model.repository
    if repo.is_git:
        lines.append("[OK] Git repository detected")
        lines.append(f"     branch: {repo.branch or 'UNKNOWN'}")
        lines.append(f"     commit: {repo.commit or 'UNKNOWN'}")
        dirty = "UNKNOWN" if repo.dirty is None else ("yes" if repo.dirty else "no")
        lines.append(f"     dirty working tree: {dirty}")
        if repo.note:
            lines.append(f"     note: {repo.note}")
    else:
        lines.append("[--] No git repository detected")
    lines.append(f"     files scanned: {model.file_count}")
    if model.test_directories:
        lines.append(f"     test directories: {', '.join(model.test_directories)}")
    lines.append("")

    def _section(title: str, items, formatter) -> None:
        lines.append(title)
        lines.append("-" * len(title))
        if not items:
            lines.append("(none detected)")
        for item in items:
            lines.append(formatter(item))
        lines.append("")

    _section("Languages", model.languages, lambda d: (
        f"[{_fmt_confidence(d.confidence.value)}] {d.name} ({d.file_count} files)"
    ))
    lines.append(f"Primary language: {model.primary_language or 'UNKNOWN'}")
    lines.append("")

    _section("Project Types", model.project_types, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")
    _section("Build Systems", model.build_systems, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")
    _section("Frameworks", model.frameworks, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")
    _section("Infrastructure", model.infrastructure, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")
    _section("Databases", model.databases, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")
    _section("API / Service Evidence", model.apis, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name} ({d.kind})")
    _section("Test Frameworks", model.test_frameworks, lambda d: f"[{_fmt_confidence(d.confidence.value)}] {d.name}")

    lines.append("Frontend / Web Application")
    lines.append("-" * 26)
    fe = model.frontend
    if not fe.detected:
        lines.append("(no frontend detected)")
    else:
        lines.append(f"[{_fmt_confidence(fe.detection_confidence.value)}] Frontend detected")
        if fe.frontend_type:
            lines.append(f"     Type: {fe.frontend_type.value}")
        if fe.entry_points:
            lines.append(f"     Entry point(s): {', '.join(fe.entry_points)}")
        if len(fe.web_roots) > 1:
            lines.append(f"     Multiple web roots detected: {', '.join(fe.web_roots)}")
        if fe.html_page_count or fe.css_file_count or fe.js_file_count:
            lines.append(
                f"     HTML pages: {fe.html_page_count}  CSS files: {fe.css_file_count}  "
                f"JS files: {fe.js_file_count}  (inline CSS blocks: {fe.inline_css_count}, "
                f"inline JS blocks: {fe.inline_js_count})"
            )
        if fe.application_pattern:
            lines.append(f"     Application pattern: {fe.application_pattern} (evidence suggests, not confirmed)")
        if fe.css_frameworks:
            lines.append(f"     CSS frameworks: {', '.join(fe.css_frameworks)}")
        lines.append(f"     Routes: {fe.routes.status.value} (evidence in {fe.routes.count} file(s))")
        lines.append(f"     Components: {fe.components.status.value}")
        lines.append(f"     Forms: {fe.forms.status.value}")
        lines.append(f"     Interactive UI evidence: {fe.interactive_ui.status.value}")
        lines.append(f"     API clients: {fe.api_clients.status.value}")
        if fe.browser_apis:
            lines.append(f"     Browser APIs detected: {', '.join(fe.browser_apis)}")
        if fe.external_resources:
            lines.append(f"     External resources: {', '.join(fe.external_resources)}")
        lines.append(f"     Content-Security-Policy evidence: {fe.csp.status.value}")
        lines.append(f"     Responsive design evidence: {fe.responsive.status.value}")
        lines.append(f"     Authentication UI evidence: {fe.auth_ui.status.value}")
        if fe.build_scripts:
            lines.append(f"     Build scripts: {', '.join(fe.build_scripts)}")
        if fe.test_scripts:
            lines.append(f"     Test scripts: {', '.join(fe.test_scripts)}")
        if fe.frontend_test_directories:
            lines.append(f"     Test directories: {', '.join(fe.frontend_test_directories)}")
        lines.append("     Browser/UI Execution: NOT_ASSESSED (browser automation adapter not enabled)")
    lines.append("")

    lines.append("Potential Secrets")
    lines.append("-" * 17)
    if not model.secrets:
        lines.append("(none detected)")
    else:
        for finding in model.secrets:
            lines.append("Potential secret detected")
            lines.append(f"  File: {finding.file}")
            lines.append(f"  Line: {finding.line}")
            lines.append(f"  Type: {finding.pattern_type}")
            lines.append("  Value: [REDACTED]")
        lines.append("")
        lines.append(
            "NOTE: a pattern match is not a confirmed secret and not a vulnerability finding."
        )
    lines.append("")

    if model.warnings:
        lines.append("Warnings")
        lines.append("-" * 8)
        for warning in model.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append(
        "This is an initial, evidence-based discovery result. It is not a security "
        "audit and does not prove correctness."
    )
    return "\n".join(lines)


def to_markdown(model: ProjectModel) -> str:
    lines: list[str] = []
    lines.append(f"# Discovery Report: {model.root_path}")
    lines.append("")
    lines.append(f"- Scanned: {model.scanned_at}")
    lines.append(f"- Tool version: {model.tool_version}")
    lines.append(f"- Files scanned: {model.file_count}")
    lines.append(f"- Primary language: {model.primary_language or 'UNKNOWN'}")
    lines.append("")

    lines.append("## Repository")
    lines.append("")
    repo = model.repository
    if repo.is_git:
        lines.append("- Git: yes")
        lines.append(f"- Branch: {repo.branch or 'UNKNOWN'}")
        lines.append(f"- Commit: {repo.commit or 'UNKNOWN'}")
        dirty = "UNKNOWN" if repo.dirty is None else str(repo.dirty)
        lines.append(f"- Dirty working tree: {dirty}")
        if repo.note:
            lines.append(f"- Note: {repo.note}")
    else:
        lines.append("- Git: no")
    if model.test_directories:
        lines.append(f"- Test directories: {', '.join(f'`{d}`' for d in model.test_directories)}")
    lines.append("")

    def _table(title: str, items, columns) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("_None detected._")
            lines.append("")
            return
        header, rows = columns(items)
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    _table("Languages", model.languages, lambda items: (
        ["Language", "Confidence", "Files"],
        [[d.name, d.confidence.value, str(d.file_count)] for d in items],
    ))
    _table("Project Types", model.project_types, lambda items: (
        ["Type", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))
    _table("Build Systems", model.build_systems, lambda items: (
        ["Build System", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))
    _table("Frameworks", model.frameworks, lambda items: (
        ["Framework", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))
    _table("Infrastructure", model.infrastructure, lambda items: (
        ["Infrastructure", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))
    _table("Databases", model.databases, lambda items: (
        ["Database", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))
    _table("API / Service Evidence", model.apis, lambda items: (
        ["Name", "Kind", "Confidence"], [[d.name, d.kind, d.confidence.value] for d in items],
    ))
    _table("Test Frameworks", model.test_frameworks, lambda items: (
        ["Test Framework", "Confidence"], [[d.name, d.confidence.value] for d in items],
    ))

    lines.append("## Frontend / Web Application")
    lines.append("")
    fe = model.frontend
    if not fe.detected:
        lines.append("_No frontend detected._")
        lines.append("")
    else:
        lines.append(f"- Detected: {fe.detection_confidence.value}")
        if fe.frontend_type:
            lines.append(f"- Type: `{fe.frontend_type.value}`")
        if fe.entry_points:
            lines.append(f"- Entry point(s): {', '.join(f'`{e}`' for e in fe.entry_points)}")
        if len(fe.web_roots) > 1:
            lines.append(f"- Multiple web roots detected: {', '.join(f'`{r}`' for r in fe.web_roots)}")
        if fe.html_page_count or fe.css_file_count or fe.js_file_count:
            lines.append(
                f"- HTML pages: {fe.html_page_count} · CSS files: {fe.css_file_count} · "
                f"JS files: {fe.js_file_count} (inline CSS blocks: {fe.inline_css_count}, "
                f"inline JS blocks: {fe.inline_js_count})"
            )
        if fe.application_pattern:
            lines.append(f"- Application pattern: `{fe.application_pattern}` _(evidence suggests, not confirmed)_")
        if fe.css_frameworks:
            lines.append(f"- CSS frameworks: {', '.join(fe.css_frameworks)}")
        lines.append(f"- Routes evidence: {fe.routes.status.value}")
        lines.append(f"- Components evidence: {fe.components.status.value}")
        lines.append(f"- Forms evidence: {fe.forms.status.value}")
        lines.append(f"- Interactive UI evidence: {fe.interactive_ui.status.value}")
        lines.append(f"- API client evidence: {fe.api_clients.status.value}")
        if fe.browser_apis:
            lines.append(f"- Browser APIs detected: {', '.join(fe.browser_apis)}")
        if fe.external_resources:
            lines.append(f"- External resources: {', '.join(fe.external_resources)}")
        lines.append(f"- Content-Security-Policy evidence: {fe.csp.status.value}")
        lines.append(f"- Responsive design evidence: {fe.responsive.status.value}")
        lines.append(f"- Authentication UI evidence: {fe.auth_ui.status.value}")
        if fe.build_scripts:
            lines.append(f"- Build scripts: {', '.join(f'`{k}`' for k in fe.build_scripts)}")
        if fe.test_scripts:
            lines.append(f"- Test scripts: {', '.join(f'`{k}`' for k in fe.test_scripts)}")
        if fe.frontend_test_directories:
            lines.append(f"- Test directories: {', '.join(f'`{d}`' for d in fe.frontend_test_directories)}")
        lines.append("- **Browser/UI Execution: NOT_ASSESSED** - browser automation adapter is not enabled in this version.")
        lines.append("")

    lines.append("## Potential Secrets")
    lines.append("")
    if not model.secrets:
        lines.append("_None detected._")
    else:
        lines.append("| File | Line | Type | Value |")
        lines.append("|---|---|---|---|")
        for finding in model.secrets:
            lines.append(f"| `{finding.file}` | {finding.line} | {finding.pattern_type} | [REDACTED] |")
        lines.append("")
        lines.append(
            "> A pattern match is not a confirmed secret and not a vulnerability finding."
        )
    lines.append("")

    if model.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in model.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append(
        "_This is an initial, evidence-based discovery result. It is not a security "
        "audit and does not prove correctness._"
    )
    return "\n".join(lines)
