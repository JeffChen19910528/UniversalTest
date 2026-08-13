"""`universal-test` CLI skeleton (skill.md §17).

Phase 1 wires argument parsing and command routing only. Each subcommand
handler reports which future phase implements its behavior instead of doing
nothing silently or crashing — the tool must stay honest about its own
limitations at every phase (skill.md §4.1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from universal_test import __version__
from universal_test.core.configuration import load_config
from universal_test.core.errors import ConfigurationError, DiscoveryError, OpenApiError
from universal_test.core.logging_setup import configure_logging, get_logger
from universal_test.discovery import discover
from universal_test.discovery.serializers import to_json, to_markdown, to_text
from universal_test.adapters.rest.adapter import run as rest_run
from universal_test.adapters.rest.auth import resolve_auth_from_env
from universal_test.adapters.rest.discovery_bridge import MultipleSpecsFoundError
from universal_test.adapters.rest.performance import resolve_auth_headers, resolve_performance_target
from universal_test.adapters.rest.performance_executor import make_performance_executor
from universal_test.adapters.rest.serializers import (
    dry_run_to_json,
    dry_run_to_markdown,
    dry_run_to_text,
    run_to_json,
    run_to_markdown,
    run_to_text,
)
from universal_test.testing.performance import (
    PerformanceRunner,
    build_load_profile,
    plan_to_text,
    result_to_json,
    result_to_markdown,
    result_to_text,
)
from universal_test.assessment import build_assessment
from universal_test.reporting import AssessReportBundle
from universal_test.reporting import to_html as report_to_html
from universal_test.reporting import to_json as report_to_json
from universal_test.reporting import to_markdown as report_to_markdown
from universal_test.core.errors import DatabaseError
from universal_test.adapters.database import discover as db_discover
from universal_test.adapters.database import load_database_profile
from universal_test.adapters.database.serializers import (
    plan_to_text as db_plan_to_text,
    result_to_json as db_result_to_json,
    result_to_markdown as db_result_to_markdown,
    result_to_text as db_result_to_text,
)
from universal_test.core.errors import RegressionError
from universal_test.regression import build_snapshot, compare as regression_compare, load_baseline, save_baseline
from universal_test.regression.serializers import (
    result_to_json as regression_result_to_json,
    result_to_markdown as regression_result_to_markdown,
    result_to_text as regression_result_to_text,
)
from universal_test.quality_gate import ExitCode, QualityGatePolicy, detect_ci_environment
from universal_test.quality_gate import evaluate as qg_evaluate
from universal_test.quality_gate.serializers import result_to_text as qg_result_to_text
from universal_test.adapters.browser.serializers import (
    dry_run_to_json as browser_dry_run_to_json,
    dry_run_to_text as browser_dry_run_to_text,
    run_to_json as browser_run_to_json,
    run_to_markdown as browser_run_to_markdown,
    run_to_text as browser_run_to_text,
)

# command -> phase that implements its real behavior (scan/test/performance/assess/database/baseline implemented as of Phase 2-7)
_NOT_YET_IMPLEMENTED = {
    "report": "Phase 5 (Reports) - use 'assess' for the unified report",
    "run": "Phase 3-5 (combined pipeline)",
}

_DB_RESULT_SERIALIZERS = {"text": db_result_to_text, "json": db_result_to_json, "markdown": db_result_to_markdown}
_REGRESSION_RESULT_SERIALIZERS = {
    "text": regression_result_to_text, "json": regression_result_to_json, "markdown": regression_result_to_markdown,
}

_SCAN_SERIALIZERS = {"text": (to_text, "txt"), "json": (to_json, "json"), "markdown": (to_markdown, "md")}
_TEST_DRY_RUN_SERIALIZERS = {"text": dry_run_to_text, "json": dry_run_to_json, "markdown": dry_run_to_markdown}
_TEST_RUN_SERIALIZERS = {"text": run_to_text, "json": run_to_json, "markdown": run_to_markdown}
_PERF_RESULT_SERIALIZERS = {"text": result_to_text, "json": result_to_json, "markdown": result_to_markdown}
_FORMAT_EXTENSION = {"text": "txt", "json": "json", "markdown": "md"}


def _add_common_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("path", help="Path to the project to inspect")
    subparser.add_argument("--config", help="Path to a universal-test.yaml config file")
    subparser.add_argument("--output", help="Directory to write output/reports to")
    subparser.add_argument(
        "--format", choices=["text", "json", "markdown", "html", "all"], default="text",
        help="Output format. 'scan' supports text/json/markdown today; "
             "html/all are reserved for the Phase 5 report generators.",
    )
    subparser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    subparser.add_argument(
        "--adapter", action="append", default=None,
        help="Restrict to specific adapter(s); may be passed multiple times",
    )
    subparser.add_argument(
        "--target", help="Explicit target URL, required for performance testing",
    )
    subparser.add_argument(
        "--dry-run", action="store_true",
        help="Describe what would run without executing anything",
    )
    subparser.add_argument(
        "--safe-mode", action="store_true", default=True,
        help="Run with conservative defaults only (default: on)",
    )


def _add_auth_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--bearer-token-env", help="Name of an environment variable holding a bearer token "
                                    "(the token itself is never passed on the command line)",
    )
    subparser.add_argument("--api-key-env", help="Name of an environment variable holding an API key")
    subparser.add_argument(
        "--api-key-header", help="Header name to send the API key in (defaults to the OpenAPI-declared name)",
    )
    subparser.add_argument("--basic-auth-user-env", help="Name of an environment variable holding a basic-auth username")
    subparser.add_argument("--basic-auth-pass-env", help="Name of an environment variable holding a basic-auth password")


def _add_test_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--openapi", help="Explicit path to an OpenAPI/Swagger document; required if the "
                           "project contains more than one candidate spec file",
    )
    subparser.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds (default: 10)",
    )
    _add_auth_args(subparser)


def _add_performance_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--openapi", help="Explicit path to an OpenAPI/Swagger document (same selection rules as 'test')",
    )
    subparser.add_argument("--endpoint", help="Path to load-test, e.g. /api/users (required if no OpenAPI spec, "
                                                "or if the spec has more than one endpoint)")
    subparser.add_argument("--method", help="HTTP method for --endpoint (default: GET)")
    subparser.add_argument(
        "--profile", choices=["baseline", "load", "stress", "custom"], default="load",
        help="Load profile (default: load). baseline forces concurrency=1.",
    )
    subparser.add_argument(
        "--concurrency", help="Comma-separated concurrency levels, e.g. 1,10,50 "
                               "(required for --profile custom)",
    )
    subparser.add_argument("--max-concurrency", type=int, help="Cap for auto-generated stress-profile levels")
    subparser.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds (default: 10)",
    )
    subparser.add_argument("--requests", type=int, help="Requests per concurrency level")
    subparser.add_argument("--duration", type=float, help="Seconds to run per concurrency level (alternative to --requests)")
    subparser.add_argument("--stop-error-rate", type=float, help="Stress profile: stop if error rate exceeds this percent")
    subparser.add_argument("--stop-p95-ms", type=float, help="Stress profile: stop if P95 latency exceeds this many ms")
    subparser.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation prompt (for CI/non-interactive use)",
    )
    _add_auth_args(subparser)


def _add_database_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--database-profile",
        help="Path to a database profile YAML (engine/host/database/credentials/readonly). "
             "Required to assess a database - discovering database evidence in a project "
             "never implies permission to connect to it (Phase 6 brief section 4).",
    )


def _add_baseline_args(subparser: argparse.ArgumentParser, *, required: bool) -> None:
    subparser.add_argument(
        "--baseline", required=required,
        help="Path to a previously saved baseline.json (from 'baseline save') to compare the "
             "current run against. Read-only - comparison never modifies the baseline file "
             "(Phase 7 brief section 4).",
    )


def _add_pipeline_args(subparser: argparse.ArgumentParser) -> None:
    """Flags shared by every command that runs the full discovery + functional +
    performance + database pipeline: 'assess', 'baseline save', 'baseline compare'."""
    _add_performance_args(subparser)  # openapi/endpoint/method/profile/concurrency/.../auth flags
    subparser.add_argument(
        "--performance", action="store_true",
        help="Also run a small performance test against --target. Opt-in: never sends "
             "load traffic unless this flag is passed (Phase 5 brief section 20).",
    )
    _add_database_args(subparser)
    subparser.add_argument(
        "--browser", action="store_true",
        help="Also run browser/UI functional testing against --target. Opt-in: never launches "
             "a browser unless this flag AND --target AND (--yes or interactive confirmation) "
             "are all given (Phase 9 spec section 34-35).",
    )
    subparser.add_argument(
        "--allow-external", action="store_true",
        help="Allow browser navigation to targets other than localhost/127.0.0.1/::1/file:// (spec section 7)",
    )
    subparser.add_argument("--screenshots", action="store_true", help="Capture browser-test screenshot evidence")
    subparser.add_argument(
        "--scenario", action="append", default=None,
        help="Also execute an explicit Web Scenario by id against --target (Phase 11). May be "
             "passed multiple times. Opt-in, same confirmation gate as --browser.",
    )
    subparser.add_argument(
        "--scenario-file", help="Path to the scenario YAML file (default: <path>/universal-test-web.yaml)",
    )


def _add_assess_args(subparser: argparse.ArgumentParser) -> None:
    _add_pipeline_args(subparser)
    _add_baseline_args(subparser, required=False)
    subparser.add_argument(
        "--ci", action="store_true",
        help="CI mode: forces non-interactive behavior (no confirmation prompt, even on a "
             "pseudo-tty) and prints a machine-friendly Quality Gate summary. Does NOT imply "
             "--yes -- traffic-sending confirmations still require it explicitly "
             "(Phase 8 brief section 7).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="universal-test",
        description="Universal, project-agnostic discovery, testing, and initial quality assessment.",
    )
    parser.add_argument("--version", action="version", version=f"universal-test {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "assess", "test", "performance", "database", "baseline", "browser", "web", "report", "run", "gui"):
        help_text = "launch the local browser-based GUI" if name == "gui" else f"{name} a project"
        subparser = subparsers.add_parser(name, help=help_text)
        if name == "gui":
            subparser.description = (
                "Launch the local, browser-based GUI (Post-V1 Phase 1). "
                "Binds to 127.0.0.1 only; never exposes the tool to the network."
            )
            subparser.add_argument("--port", type=int, default=0, help="Port to bind (default: auto-select)")
            subparser.add_argument(
                "--no-browser", action="store_true", help="Do not automatically open the default browser",
            )
            subparser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
            continue
        if name == "baseline":
            baseline_sub = subparser.add_subparsers(dest="baseline_command", required=True)

            save_parser = baseline_sub.add_parser("save", help="Save a baseline snapshot for later comparison")
            _add_common_args(save_parser)
            _add_pipeline_args(save_parser)

            compare_parser = baseline_sub.add_parser("compare", help="Compare the current project against a saved baseline")
            _add_common_args(compare_parser)
            _add_pipeline_args(compare_parser)
            _add_baseline_args(compare_parser, required=True)
            continue

        if name == "browser":
            browser_sub = subparser.add_subparsers(dest="browser_command", required=True)

            install_parser = browser_sub.add_parser(
                "install", help="Download a Playwright browser binary (explicit, never automatic)",
            )
            install_parser.add_argument(
                "--engine", default="chromium", choices=["chromium", "firefox", "webkit"],
                help="Which browser binary to install (default: chromium)",
            )
            install_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

            test_parser = browser_sub.add_parser(
                "test", help="Run browser/UI functional tests against an explicit target",
            )
            test_parser.add_argument("path", help="Path to the project to inspect")
            test_parser.add_argument("--config", help="Path to a universal-test.yaml config file")
            test_parser.add_argument("--output", help="Directory to write output/reports to")
            test_parser.add_argument(
                "--format", choices=["text", "json", "markdown"], default="text",
                help="Output format (default: text)",
            )
            test_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
            test_parser.add_argument(
                "--target", required=False,
                help="Explicit target URL/file:// path (required unless --dry-run); browser testing "
                     "never guesses or scans for a target (spec section 6)",
            )
            test_parser.add_argument(
                "--engine", default="chromium", choices=["chromium", "firefox", "webkit"],
                help="Browser engine to use (default: chromium)",
            )
            test_parser.add_argument(
                "--allow-external", action="store_true",
                help="Allow navigation to targets other than localhost/127.0.0.1/::1/file:// (spec section 7)",
            )
            test_parser.add_argument("--screenshots", action="store_true", help="Capture screenshot evidence")
            test_parser.add_argument(
                "--dry-run", action="store_true", help="Show the test plan without launching a browser",
            )
            test_parser.add_argument(
                "--yes", action="store_true", help="Skip the interactive safety confirmation (for CI/non-interactive use)",
            )

            scenario_parser = browser_sub.add_parser(
                "scenario", help="Define and repeatedly execute an explicit, multi-step Web test workflow (Phase 11)",
            )
            scenario_sub = scenario_parser.add_subparsers(dest="scenario_command", required=True)

            def _add_scenario_file_args(p: argparse.ArgumentParser) -> None:
                p.add_argument("path", help="Path to the project to inspect")
                p.add_argument("--config", help="Path to a universal-test.yaml config file")
                p.add_argument(
                    "--scenario-file",
                    help="Path to the scenario YAML file (default: <path>/universal-test-web.yaml)",
                )
                p.add_argument("--verbose", action="store_true", help="Enable verbose logging")

            list_parser = scenario_sub.add_parser("list", help="List available scenarios without executing them")
            _add_scenario_file_args(list_parser)
            list_parser.add_argument("--format", choices=["text", "json"], default="text")

            validate_parser = scenario_sub.add_parser(
                "validate", help="Validate scenario file(s) without launching a browser",
            )
            _add_scenario_file_args(validate_parser)

            run_parser = scenario_sub.add_parser("run", help="Execute one explicit scenario")
            _add_scenario_file_args(run_parser)
            run_parser.add_argument("--scenario", help="Scenario id to run (required unless --all)")
            run_parser.add_argument("--all", action="store_true", help="Run every scenario in the file")
            run_parser.add_argument(
                "--target",
                help="Explicit target URL/file:// path (required unless --dry-run); never guessed (spec section 16)",
            )
            run_parser.add_argument(
                "--engine", default="chromium", choices=["chromium", "firefox", "webkit"],
                help="Browser engine to use (default: chromium)",
            )
            run_parser.add_argument(
                "--allow-external", action="store_true",
                help="Allow navigation to targets other than localhost/127.0.0.1/::1/file:// (spec section 17)",
            )
            run_parser.add_argument("--screenshots", action="store_true", help="Capture screenshot evidence")
            run_parser.add_argument("--output", help="Directory to write output to")
            run_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
            run_parser.add_argument(
                "--dry-run", action="store_true", help="Show the scenario plan without launching a browser",
            )
            run_parser.add_argument(
                "--yes", action="store_true", help="Skip the interactive safety confirmation (for CI/non-interactive use)",
            )
            continue

        if name == "web":
            web_sub = subparser.add_subparsers(dest="web_command", required=True)

            web_assess_parser = web_sub.add_parser(
                "assess",
                help="Guided, non-programmer-friendly Web Assessment: static analysis + "
                     "browser smoke test + report, in one command (Phase 10)",
            )
            web_assess_parser.add_argument("path", help="Path to the project to inspect")
            web_assess_parser.add_argument("--config", help="Path to a universal-test.yaml config file")
            web_assess_parser.add_argument("--output", help="Directory to write output/reports to")
            web_assess_parser.add_argument(
                "--format", choices=["json", "markdown", "html", "all"], default="all",
                help="Report format(s) to write (default: all)",
            )
            web_assess_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
            web_assess_parser.add_argument(
                "--target",
                help="Explicit browser target URL/file:// path. Without it, static analysis "
                     "still runs but Browser Testing reports NOT_ASSESSED (spec section 14) -- "
                     "never guessed, never scanned for.",
            )
            web_assess_parser.add_argument(
                "--allow-external", action="store_true",
                help="Allow browser navigation to targets other than localhost/127.0.0.1/::1/file:// (spec section 15)",
            )
            web_assess_parser.add_argument("--screenshots", action="store_true", help="Capture browser-test screenshot evidence")
            web_assess_parser.add_argument(
                "--dry-run", action="store_true",
                help="Show the Web Assessment plan (discovery + intended browser actions) without "
                     "launching a browser or sending any traffic (spec section 43)",
            )
            web_assess_parser.add_argument(
                "--yes", action="store_true",
                help="Skip the interactive browser-testing safety confirmation (for CI/non-interactive use)",
            )
            web_assess_parser.add_argument(
                "--baseline", help="Optional path to a previously saved baseline.json to compare against",
            )
            web_assess_parser.add_argument(
                "--ci", action="store_true",
                help="CI mode: non-interactive behavior + machine-friendly Quality Gate summary. "
                     "Does NOT imply --yes.",
            )
            # Web Assessment is deliberately scoped to static analysis + browser testing only
            # (spec section 1/7) -- performance/database/REST-auth flags are not exposed on this
            # command's surface; these are the safe, inert defaults `_run_pipeline` needs to exist.
            web_assess_parser.set_defaults(
                performance=False, database_profile=None, openapi=None, timeout=10.0,
                concurrency=None, max_concurrency=None, requests=None, duration=None,
                stop_error_rate=None, stop_p95_ms=None, profile="load", method=None, endpoint=None,
                bearer_token_env=None, api_key_env=None, api_key_header=None,
                basic_auth_user_env=None, basic_auth_pass_env=None, browser=True,
            )
            continue

        _add_common_args(subparser)
        if name == "test":
            _add_test_args(subparser)
        elif name == "performance":
            _add_performance_args(subparser)
        elif name == "assess":
            _add_assess_args(subparser)
            subparser.set_defaults(format="all")
        elif name == "database":
            _add_database_args(subparser)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = configure_logging(verbose=args.verbose)
    command_logger = get_logger("cli")

    if args.command == "gui":
        from universal_test.gui.launcher import launch

        launch(port=args.port, open_browser=not args.no_browser)
        return 0

    if args.command == "browser" and args.browser_command == "install":
        return _run_browser_install(args, command_logger)

    if args.command == "browser" and args.browser_command == "test" and not args.target and not args.dry_run:
        command_logger.error(
            "browser testing requires an explicit --target (spec section 6); "
            "refusing to guess or scan for a target, even for a smoke test"
        )
        return 2

    if args.command == "browser" and args.browser_command == "scenario" and args.scenario_command == "run":
        if not args.target and not args.dry_run:
            command_logger.error(
                "scenario execution requires an explicit --target (spec section 16); "
                "refusing to guess or scan for a target, even for a dry run"
            )
            return 2
        if not args.scenario and not args.all:
            command_logger.error(
                "specify which scenario to run: --scenario <id> (or --all to run every scenario); "
                "Universal Test never surprises you by executing every scenario implicitly (spec section 28)"
            )
            return 2

    if args.command == "performance" and not args.target:
        command_logger.error(
            "performance testing requires an explicit --target (skill.md section 4.2); "
            "refusing to guess or attack an undeclared host, even for --dry-run"
        )
        return 2

    try:
        config = load_config(project_path=args.path, config_path=args.config)
    except ConfigurationError as exc:
        command_logger.error(str(exc))
        return 2

    if args.command == "scan":
        return _run_scan(args, command_logger)
    if args.command == "test":
        return _run_test(args, command_logger)
    if args.command == "performance":
        return _run_performance(args, config, command_logger)
    if args.command == "assess":
        return _run_assess(args, config, command_logger)
    if args.command == "database":
        return _run_database(args, command_logger)
    if args.command == "baseline":
        if args.baseline_command == "save":
            return _run_baseline_save(args, config, command_logger)
        return _run_baseline_compare(args, config, command_logger)
    if args.command == "browser" and args.browser_command == "test":
        return _run_browser_test(args, config, command_logger)
    if args.command == "browser" and args.browser_command == "scenario":
        if args.scenario_command == "list":
            return _run_scenario_list(args, command_logger)
        if args.scenario_command == "validate":
            return _run_scenario_validate(args, command_logger)
        return _run_scenario_run(args, config, command_logger)
    if args.command == "web" and args.web_command == "assess":
        return _run_web_assess(args, config, command_logger)

    phase = _NOT_YET_IMPLEMENTED[args.command]
    logger.info(
        "'%s' is not yet implemented; it is delivered in %s. "
        "This Phase 1 skeleton only validates arguments and configuration.",
        args.command, phase,
    )
    return 0


def _run_scan(args: argparse.Namespace, logger) -> int:
    if args.format not in _SCAN_SERIALIZERS:
        logger.error(
            "'scan' does not yet support --format %s (that's a Phase 5 report format); "
            "use text, json, or markdown", args.format,
        )
        return 2

    try:
        model = discover(args.path)
    except DiscoveryError as exc:
        logger.error(str(exc))
        return 2

    serialize, extension = _SCAN_SERIALIZERS[args.format]
    rendered = serialize(model)

    if args.output:
        output_path = Path(args.output)
        if output_path.is_dir() or output_path.suffix == "":
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / f"discovery.{extension}"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        logger.info("discovery report written to %s", output_path)
    else:
        print(rendered)

    return 0


def _confirm(prompt: str) -> bool:
    """Reads a y/N confirmation, treating a closed/exhausted stdin (`EOFError`
    -- observed on Windows even when `sys.stdin.isatty()` reported `True` for
    a redirected/NUL stdin in some subprocess configurations) the same as a
    "no" answer rather than letting a raw traceback escape a safety prompt.
    """
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def _write_or_print(rendered: str, output: str | None, extension: str, logger, default_name: str) -> None:
    if output:
        output_path = Path(output)
        if output_path.is_dir() or output_path.suffix == "":
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / f"{default_name}.{extension}"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        logger.info("report written to %s", output_path)
    else:
        print(rendered)


def _run_test(args: argparse.Namespace, logger) -> int:
    format_extension = _FORMAT_EXTENSION
    if args.format not in format_extension:
        logger.error(
            "'test' does not yet support --format %s (that's a Phase 5 report format); "
            "use text, json, or markdown", args.format,
        )
        return 2

    auth_config, auth_warnings = resolve_auth_from_env(
        bearer_token_env=args.bearer_token_env,
        api_key_env=args.api_key_env,
        api_key_header=args.api_key_header,
        basic_user_env=args.basic_auth_user_env,
        basic_pass_env=args.basic_auth_pass_env,
    )
    for w in auth_warnings:
        logger.warning(w)

    try:
        result = rest_run(
            args.path,
            openapi_override=args.openapi,
            target=args.target,
            auth_config=auth_config,
            timeout_seconds=args.timeout,
            dry_run=args.dry_run,
        )
    except MultipleSpecsFoundError as exc:
        logger.error(str(exc))
        return 2
    except (OpenApiError, DiscoveryError) as exc:
        logger.error(str(exc))
        return 2

    if args.dry_run:
        rendered = _TEST_DRY_RUN_SERIALIZERS[args.format](result)
        _write_or_print(rendered, args.output, format_extension[args.format], logger, "dry_run")
        return 0

    if not result.executed:
        # discovery/generation succeeded; execution was withheld because no target was given
        # (skill.md §4.2 — the tool never invents a target to test against)
        rendered = _TEST_RUN_SERIALIZERS[args.format](result)
        print(rendered)
        return 2

    rendered = _TEST_RUN_SERIALIZERS[args.format](result)
    _write_or_print(rendered, args.output, format_extension[args.format], logger, "test_run")
    return 0


def _parse_concurrency_arg(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    try:
        return [int(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise ConfigurationError(f"--concurrency must be a comma-separated list of integers, got {raw!r}") from exc


def _run_performance(args: argparse.Namespace, config, logger) -> int:
    if args.format not in _PERF_RESULT_SERIALIZERS:
        logger.error(
            "'performance' does not yet support --format %s (that's a Phase 5 report format); "
            "use text, json, or markdown", args.format,
        )
        return 2

    try:
        concurrency = _parse_concurrency_arg(args.concurrency)
        spec, endpoint, request, gen_warnings = resolve_performance_target(
            args.path, openapi_override=args.openapi, endpoint_path=args.endpoint, method=args.method,
        )
        profile, plan_warnings = build_load_profile(
            args.profile,
            concurrency=concurrency,
            requests=args.requests,
            duration=args.duration,
            max_concurrency=args.max_concurrency,
            stop_on_error_rate_percent=args.stop_error_rate,
            stop_on_p95_ms=args.stop_p95_ms,
        )
    except MultipleSpecsFoundError as exc:
        logger.error(str(exc))
        return 2
    except (OpenApiError, DiscoveryError, ConfigurationError) as exc:
        logger.error(str(exc))
        return 2

    for w in gen_warnings + plan_warnings:
        logger.warning(w)

    thresholds = dict(config.performance.thresholds) if config.performance.thresholds else {}
    endpoint_label = f"{request.method} {request.path}"
    plan_text = plan_to_text(args.target, endpoint_label, profile, thresholds)

    if args.dry_run:
        print(plan_text)
        print("No requests executed.")
        return 0

    if not args.yes:
        print(plan_text)
        estimated = profile.estimated_total_requests()
        if estimated is not None:
            print(f"This test will generate approximately {estimated} requests.")
        print()
        if not sys.stdin.isatty():
            logger.error(
                "non-interactive session with no --yes flag; refusing to run without confirmation "
                "(pass --yes for CI/non-interactive use)"
            )
            return 2
        if not _confirm("Proceed? [y/N] "):
            logger.info("performance test cancelled by user")
            return 2

    auth_config, auth_warnings = resolve_auth_from_env(
        bearer_token_env=args.bearer_token_env,
        api_key_env=args.api_key_env,
        api_key_header=args.api_key_header,
        basic_user_env=args.basic_auth_user_env,
        basic_pass_env=args.basic_auth_pass_env,
    )
    for w in auth_warnings:
        logger.warning(w)
    auth_headers, auth_query = resolve_auth_headers(spec, endpoint, auth_config)

    executor, close = make_performance_executor(args.target, args.timeout, auth_headers, auth_query)
    try:
        runner = PerformanceRunner(executor)
        result = runner.run(args.target, endpoint_label, request, profile, thresholds=thresholds)
    finally:
        close()

    result.warnings = gen_warnings + plan_warnings + result.warnings
    rendered = _PERF_RESULT_SERIALIZERS[args.format](result)
    _write_or_print(rendered, args.output, _FORMAT_EXTENSION[args.format], logger, "performance_run")
    return 0


_ASSESS_RENDERERS = {"json": report_to_json, "markdown": report_to_markdown, "html": report_to_html}
_ASSESS_EXTENSIONS = {"json": "json", "markdown": "md", "html": "html"}


def _is_total_transport_failure(run_result) -> bool:
    """True only when *every* executed functional test errored at the
    transport layer (connection refused/timeout/etc.) -- the same condition
    `assessment/rules.py::execution_health_status()` maps to `FAIL`. Used to
    gate the bounded CI retry (Phase 8 brief section 19) so a real assertion
    failure or partial failure is never retried, only a total wipeout that
    looks like network instability rather than a genuine regression.
    """
    if run_result is None:
        return False
    counts = run_result.summary
    executed = counts.get("passed", 0) + counts.get("failed", 0) + counts.get("error", 0)
    return executed > 0 and counts.get("error", 0) == executed


def _run_pipeline(args: argparse.Namespace, config, model, logger):
    """Runs the functional + performance + database pipeline shared by
    'assess', 'baseline save', and 'baseline compare' against an
    already-discovered `model`. Never re-discovers the project itself —
    callers each run `discover()` once and pass the result in.
    """
    has_confirmed_openapi = any(a.kind == "openapi" and a.confidence.value == "detected" for a in model.apis)

    auth_config, auth_warnings = resolve_auth_from_env(
        bearer_token_env=args.bearer_token_env,
        api_key_env=args.api_key_env,
        api_key_header=args.api_key_header,
        basic_user_env=args.basic_auth_user_env,
        basic_pass_env=args.basic_auth_pass_env,
    )
    for w in auth_warnings:
        logger.warning(w)

    generated_count = 0
    run_result = None
    functional_not_run_reason = None
    try:
        rest_result = rest_run(
            args.path, openapi_override=args.openapi, target=args.target,
            auth_config=auth_config, timeout_seconds=args.timeout, dry_run=args.dry_run,
        )
        generated_count = len(rest_result.test_cases)
        if rest_result.executed:
            run_result = rest_result.run_result
            retries_left = config.ci.retry.count
            while retries_left > 0 and _is_total_transport_failure(run_result):
                logger.warning(
                    "functional execution failed at the transport layer for every request; "
                    "retrying (%d attempt(s) remaining) - a genuine assertion/threshold "
                    "failure is never retried, only a total transport wipeout",
                    retries_left,
                )
                retries_left -= 1
                retry_result = rest_run(
                    args.path, openapi_override=args.openapi, target=args.target,
                    auth_config=auth_config, timeout_seconds=args.timeout, dry_run=args.dry_run,
                )
                run_result = retry_result.run_result
        else:
            functional_not_run_reason = rest_result.no_target_reason or "generation-only (--dry-run was specified)"
    except MultipleSpecsFoundError as exc:
        functional_not_run_reason = str(exc)
    except (OpenApiError, DiscoveryError) as exc:
        functional_not_run_reason = str(exc)

    perf_result, performance_not_run_reason = _maybe_run_assess_performance(args, config, auth_config, logger)
    database_result = _maybe_run_assess_database(args, logger)
    browser_result, browser_not_run_reason = _maybe_run_assess_browser(args, config, logger)
    scenario_results, scenario_not_run_reason = _maybe_run_assess_scenario(args, config, logger)

    return (
        has_confirmed_openapi, generated_count, run_result, functional_not_run_reason,
        perf_result, performance_not_run_reason, database_result,
        browser_result, browser_not_run_reason,
        scenario_results, scenario_not_run_reason,
    )


def _run_assess(args: argparse.Namespace, config, logger) -> int:
    formats = ["json", "markdown", "html"] if args.format == "all" else [args.format]
    for f in formats:
        if f not in _ASSESS_RENDERERS:
            logger.error("'assess' does not support --format %s; use json, markdown, html, or all", f)
            return int(ExitCode.CONFIGURATION_ERROR)

    ci_environment = detect_ci_environment()
    if ci_environment:
        # Informational only -- never changes safety behavior (Phase 8 brief section 6:
        # "不要因為偵測到 CI 就自動放寬 safety"). Improves messaging only.
        logger.info("Detected CI environment: %s", ci_environment)

    try:
        model = discover(args.path)
    except DiscoveryError as exc:
        logger.error(str(exc))
        return int(ExitCode.CONFIGURATION_ERROR)

    (
        has_confirmed_openapi, generated_count, run_result, functional_not_run_reason,
        perf_result, performance_not_run_reason, database_result,
        browser_result, browser_not_run_reason,
        scenario_results, scenario_not_run_reason,
    ) = _run_pipeline(args, config, model, logger)

    assessment = build_assessment(
        project_path=args.path, target=args.target, model=model, generated_count=generated_count,
        run_result=run_result, functional_not_run_reason=functional_not_run_reason,
        perf_result=perf_result, performance_not_run_reason=performance_not_run_reason,
        has_confirmed_openapi=has_confirmed_openapi, database_result=database_result,
        browser_result=browser_result, browser_not_run_reason=browser_not_run_reason,
        scenario_results=scenario_results, scenario_not_run_reason=scenario_not_run_reason,
    )

    regression = None
    baseline_config_error = False
    baseline_path = getattr(args, "baseline", None)
    if baseline_path:
        try:
            baseline_snapshot = load_baseline(baseline_path)
        except RegressionError as exc:
            # A --baseline the user explicitly asked for that can't be loaded is a
            # configuration mistake, not something to silently paper over in a CI
            # pipeline (Phase 8's whole point is reliable, non-ambiguous exit codes).
            logger.error("invalid --baseline: %s", exc)
            baseline_config_error = True
        else:
            current_snapshot = build_snapshot(
                project_path=args.path, target=args.target, model=model, generated_count=generated_count,
                run_result=run_result, perf_result=perf_result, database_result=database_result,
                assessment=assessment, browser_result=browser_result, scenario_results=scenario_results,
            )
            thresholds = dict(config.regression.performance) if config.regression.performance else {}
            regression = regression_compare(baseline_snapshot, current_snapshot, performance_thresholds=thresholds)

    policy = QualityGatePolicy(fail_on=config.quality_gate.fail_on, warn_on=config.quality_gate.warn_on)
    quality_gate_result = qg_evaluate(assessment, regression, policy)

    bundle = AssessReportBundle(
        assessment=assessment, model=model, run_result=run_result,
        generated_count=generated_count, perf_result=perf_result, database_result=database_result,
        regression=regression, quality_gate=quality_gate_result, browser_result=browser_result,
        scenario_results=scenario_results,
    )

    output_dir = args.output or ("reports" if args.format == "all" else None)
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        for f in formats:
            rendered = _ASSESS_RENDERERS[f](bundle)
            file_path = output_path / f"report.{_ASSESS_EXTENSIONS[f]}"
            file_path.write_text(rendered, encoding="utf-8")
            logger.info("assessment report written to %s", file_path)
    else:
        print(_ASSESS_RENDERERS[formats[0]](bundle))

    print(f"Overall Status: {assessment.overall_status.value.upper()}")
    health_suffix = " (no confirmed defect found)" if assessment.application_health.value == "pass" else ""
    print(f"Application Health: {assessment.application_health.value.upper()}{health_suffix}")
    if regression is not None:
        print(f"Regression Status: {regression.status.value.upper()}")

    if args.ci:
        print()
        print(qg_result_to_text(quality_gate_result))
    else:
        print(f"Quality Gate: {quality_gate_result.status.value.upper()}")
        print(f"Exit code: {quality_gate_result.exit_code}")

    if baseline_config_error:
        return int(ExitCode.CONFIGURATION_ERROR)
    return quality_gate_result.exit_code


def _maybe_run_assess_performance(args: argparse.Namespace, config, auth_config, logger):
    """Returns `(perf_result, not_run_reason)`. Opt-in via `--performance`; never sends traffic
    otherwise (Phase 5 brief §20 — 'assess' must not hide a large performance test in defaults).
    """
    if not args.performance:
        return None, "performance execution was not enabled (pass --performance)"
    if not args.target:
        return None, "no execution target was provided"
    if args.dry_run:
        return None, "generation-only (--dry-run was specified)"

    try:
        concurrency = _parse_concurrency_arg(args.concurrency)
        spec, endpoint, perf_request, gen_warnings = resolve_performance_target(
            args.path, openapi_override=args.openapi, endpoint_path=args.endpoint, method=args.method,
        )
        profile, plan_warnings = build_load_profile(
            args.profile, concurrency=concurrency, requests=args.requests, duration=args.duration,
            max_concurrency=args.max_concurrency, stop_on_error_rate_percent=args.stop_error_rate,
            stop_on_p95_ms=args.stop_p95_ms,
        )
    except MultipleSpecsFoundError as exc:
        return None, str(exc)
    except (OpenApiError, DiscoveryError, ConfigurationError) as exc:
        return None, str(exc)

    for w in gen_warnings + plan_warnings:
        logger.warning(w)

    thresholds = dict(config.performance.thresholds) if config.performance.thresholds else {}
    endpoint_label = f"{perf_request.method} {perf_request.path}"

    if not args.yes:
        print(plan_to_text(args.target, endpoint_label, profile, thresholds))
        estimated = profile.estimated_total_requests()
        if estimated is not None:
            print(f"This test will generate approximately {estimated} requests.")
        print()
        # --ci forces non-interactive behavior even if stdin happens to report a TTY
        # (some CI runners attach a pseudo-tty) -- but --ci never implies --yes itself
        # (Phase 8 brief section 7: "--ci 不得等於 --yes").
        if getattr(args, "ci", False) or not sys.stdin.isatty():
            logger.error(
                "Interactive confirmation required. Use --yes in CI/non-interactive "
                "environments (skipping --performance for this run)."
            )
            return None, "confirmation was required but not given (non-interactive session)"
        if not _confirm("Proceed with performance testing? [y/N] "):
            logger.info("performance test cancelled by user")
            return None, "performance test was cancelled by the user"

    auth_headers, auth_query = resolve_auth_headers(spec, endpoint, auth_config)
    executor, close = make_performance_executor(args.target, args.timeout, auth_headers, auth_query)
    try:
        perf_result = PerformanceRunner(executor).run(
            args.target, endpoint_label, perf_request, profile, thresholds=thresholds,
        )
    finally:
        close()
    return perf_result, None


def _maybe_run_assess_database(args: argparse.Namespace, logger):
    """Returns `DatabaseDiscoveryResult | None`. `None` means "no
    --database-profile was given" (Database Health -> NOT_ASSESSED,
    "not explicitly configured"). Never connects unless a profile was
    explicitly supplied (Phase 6 brief §4).
    """
    if not getattr(args, "database_profile", None):
        return None
    try:
        profile = load_database_profile(args.database_profile)
    except ConfigurationError as exc:
        logger.error("invalid --database-profile: %s", exc)
        return None
    return db_discover(profile)


def _maybe_run_assess_browser(args: argparse.Namespace, config, logger):
    """Returns `(browser_result, not_run_reason)`. Opt-in via `--browser`; never
    launches a browser otherwise (spec section 34-35). Mirrors
    `_maybe_run_assess_performance`'s confirmation-gate shape (spec section 30).
    """
    if not getattr(args, "browser", False):
        return None, "browser testing was not enabled (pass --browser)"
    if not args.target:
        return None, "no execution target was provided"
    if args.dry_run:
        return None, "generation-only (--dry-run was specified)"

    if not args.yes:
        print("This test will open the target in a browser and execute UI actions.")
        print(f"Target: {args.target}")
        print("No credentials will be guessed.")
        print()
        if getattr(args, "ci", False) or not sys.stdin.isatty():
            logger.error(
                "Interactive confirmation required. Use --yes in CI/non-interactive "
                "environments (skipping --browser for this run)."
            )
            return None, "confirmation was required but not given (non-interactive session)"
        if not _confirm("Continue? [y/N] "):
            logger.info("browser test cancelled by user")
            return None, "browser test was cancelled by the user"

    from universal_test.adapters.browser.adapter import run as browser_run

    result = browser_run(
        args.path, target=args.target, allow_external=getattr(args, "allow_external", False),
        browser=config.browser.browser, headless=config.browser.headless,
        navigation_timeout_seconds=config.browser.navigation_timeout_seconds,
        action_timeout_seconds=config.browser.action_timeout_seconds,
        test_timeout_seconds=config.browser.test_timeout_seconds,
        screenshots=getattr(args, "screenshots", False),
        screenshot_dir=(Path(args.output) / "screenshots") if args.output else None,
    )
    if result.not_assessed_reason:
        return None, result.not_assessed_reason
    return result, None


def _maybe_run_assess_scenario(args: argparse.Namespace, config, logger):
    """Returns `(scenario_results, not_run_reason)`. Opt-in via one or more
    `--scenario <id>`; never launches a browser otherwise (Phase 11 spec
    section 37-38). Mirrors `_maybe_run_assess_browser()`'s confirmation-gate
    shape exactly -- "one-click does not mean no safety" applies here too.
    """
    scenario_ids = getattr(args, "scenario", None)
    if not scenario_ids:
        return None, "no Web Scenario was requested (pass --scenario <id>)"
    if not args.target:
        return None, "no execution target was provided"
    if args.dry_run:
        return None, "generation-only (--dry-run was specified)"

    from universal_test.adapters.browser.scenario_loader import (
        load_scenario_file,
        resolve_scenario_path,
        validate_scenarios,
    )

    try:
        path = resolve_scenario_path(args.path, getattr(args, "scenario_file", None))
        collection = load_scenario_file(path)
    except ConfigurationError as exc:
        return None, str(exc)

    issues = validate_scenarios(collection)
    if issues:
        for issue in issues:
            logger.error(str(issue))
        return None, f"scenario file failed validation ({len(issues)} issue(s))"

    selected = []
    for scenario_id in scenario_ids:
        scenario = collection.get(scenario_id)
        if scenario is None:
            return None, f"scenario {scenario_id!r} not found in {collection.source_path}"
        selected.append(scenario)

    if not args.yes:
        print(f"This will run {len(selected)} Web Scenario(s) in Chromium and execute the defined steps.")
        print(f"Target: {args.target}")
        print("No credentials will be guessed.")
        print()
        if getattr(args, "ci", False) or not sys.stdin.isatty():
            logger.error(
                "Interactive confirmation required. Use --yes in CI/non-interactive "
                "environments (skipping --scenario for this run)."
            )
            return None, "confirmation was required but not given (non-interactive session)"
        if not _confirm("Continue? [y/N] "):
            logger.info("scenario run cancelled by user")
            return None, "scenario run was cancelled by the user"

    from universal_test.adapters.browser.scenario_runner import run_scenario

    results = [
        run_scenario(
            scenario, target=args.target, headless=config.browser.headless,
            navigation_timeout_seconds=config.browser.navigation_timeout_seconds,
            action_timeout_seconds=config.browser.action_timeout_seconds,
            allow_external=getattr(args, "allow_external", False),
            screenshot_dir=(Path(args.output) / "screenshots") if args.output and getattr(args, "screenshots", False) else None,
        )
        for scenario in selected
    ]
    return results, None


def _run_browser_install(args: argparse.Namespace, logger) -> int:
    import subprocess

    logger.info(
        "Downloading a Playwright browser binary (%s) -- this is an explicit, user-initiated "
        "download and never happens automatically elsewhere (spec section 5).", args.engine,
    )
    try:
        completed = subprocess.run([sys.executable, "-m", "playwright", "install", args.engine], check=False)
    except FileNotFoundError:
        logger.error(
            "Playwright is not installed. Install it first with: pip install universal-test[browser]"
        )
        return 2
    if completed.returncode != 0:
        logger.error("browser install failed for %s (exit code %d)", args.engine, completed.returncode)
        return 2
    print(f"Browser installed: {args.engine}")
    return 0


def _run_browser_test(args: argparse.Namespace, config, logger) -> int:
    from universal_test.adapters.browser.adapter import run as browser_run

    result = browser_run(
        args.path, target=args.target, allow_external=args.allow_external, browser=args.engine,
        headless=config.browser.headless, navigation_timeout_seconds=config.browser.navigation_timeout_seconds,
        action_timeout_seconds=config.browser.action_timeout_seconds,
        test_timeout_seconds=config.browser.test_timeout_seconds, screenshots=args.screenshots,
        screenshot_dir=(Path(args.output) / "screenshots") if args.output else None, dry_run=args.dry_run,
    )

    if args.dry_run:
        rendered = browser_dry_run_to_json(result) if args.format == "json" else browser_dry_run_to_text(result, allow_external=args.allow_external)
        _write_or_print(rendered, args.output, _FORMAT_EXTENSION.get(args.format, "txt"), logger, "browser_dry_run")
        return 0

    if not result.executed:
        reason = result.not_assessed_reason or result.no_target_reason
        logger.info("Browser testing NOT_ASSESSED: %s", reason)
        print(f"NOT ASSESSED: {reason}")
        return 0 if result.not_assessed_reason else 2

    renderers = {"text": browser_run_to_text, "json": browser_run_to_json, "markdown": browser_run_to_markdown}
    rendered = renderers[args.format](result)
    _write_or_print(rendered, args.output, _FORMAT_EXTENSION.get(args.format, "txt"), logger, "browser_test_run")

    summary = result.run_result.summary
    print(f"Browser tests: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, "
          f"{summary.get('error', 0)} error, {summary.get('skipped', 0)} skipped")
    return 0 if summary.get("failed", 0) == 0 and summary.get("error", 0) == 0 else 1


def _load_scenario_collection_or_none(args: argparse.Namespace, logger):
    from universal_test.adapters.browser.scenario_loader import load_scenario_file, resolve_scenario_path

    path = resolve_scenario_path(args.path, getattr(args, "scenario_file", None))
    try:
        return load_scenario_file(path)
    except ConfigurationError as exc:
        logger.error(str(exc))
        return None


def _run_scenario_list(args: argparse.Namespace, logger) -> int:
    from universal_test.adapters.browser.scenario_serializers import list_to_json, list_to_text

    collection = _load_scenario_collection_or_none(args, logger)
    if collection is None:
        return 2
    rendered = list_to_json(collection) if args.format == "json" else list_to_text(collection)
    print(rendered)
    return 0


def _run_scenario_validate(args: argparse.Namespace, logger) -> int:
    from universal_test.adapters.browser.scenario_loader import validate_scenarios
    from universal_test.adapters.browser.scenario_serializers import validation_to_text

    collection = _load_scenario_collection_or_none(args, logger)
    if collection is None:
        return 2
    issues = validate_scenarios(collection)
    print(validation_to_text(issues))
    return 0 if not issues else 2


def _run_scenario_run(args: argparse.Namespace, config, logger) -> int:
    from universal_test.adapters.browser.scenario_loader import validate_scenarios
    from universal_test.adapters.browser.scenario_runner import run_scenario
    from universal_test.adapters.browser.scenario_serializers import (
        plan_to_text,
        result_to_json,
        result_to_markdown,
        result_to_text,
    )

    collection = _load_scenario_collection_or_none(args, logger)
    if collection is None:
        return 2
    issues = validate_scenarios(collection)
    if issues:
        # Configuration errors must never result in browser execution (spec section 13).
        for issue in issues:
            logger.error(str(issue))
        return 2

    if args.all:
        selected = collection.scenarios
    else:
        scenario = collection.get(args.scenario)
        if scenario is None:
            logger.error(
                "scenario %r not found in %s; run `browser scenario list` to see available scenarios",
                args.scenario, collection.source_path,
            )
            return 2
        selected = [scenario]

    if args.dry_run:
        for scenario in selected:
            print(plan_to_text(scenario, target=args.target, allow_external=args.allow_external))
            print()
        return 0

    # Real browser execution remains subject to the same explicit-confirmation
    # gate every other browser-launching command already enforces (spec section
    # 15/18/46: "one-click does not mean no safety") -- never bypassed just
    # because a scenario file exists.
    if not args.yes:
        for scenario in selected:
            print(plan_to_text(scenario, target=args.target, allow_external=args.allow_external))
            print()
        if not sys.stdin.isatty():
            logger.error(
                "non-interactive session with no --yes flag; refusing to run without confirmation "
                "(pass --yes for CI/non-interactive use)"
            )
            return 2
        if not _confirm("Proceed? [y/N] "):
            logger.info("scenario run cancelled by user")
            return 2

    renderers = {"text": result_to_text, "json": result_to_json, "markdown": result_to_markdown}
    worst_exit = 0
    for scenario in selected:
        result = run_scenario(
            scenario, target=args.target, browser=args.engine, headless=config.browser.headless,
            navigation_timeout_seconds=config.browser.navigation_timeout_seconds,
            action_timeout_seconds=config.browser.action_timeout_seconds,
            allow_external=args.allow_external,
            screenshot_dir=(Path(args.output) / "screenshots") if args.output and args.screenshots else None,
        )
        rendered = renderers[args.format](result)
        _write_or_print(
            rendered, args.output, _FORMAT_EXTENSION.get(args.format, "txt"), logger,
            f"scenario_{scenario.id}",
        )
        print(f"Scenario {scenario.id}: {result.status.upper()} "
              f"({result.passed_steps} passed, {result.failed_steps} failed, "
              f"{result.error_steps} error, {result.skipped_steps} skipped)")
        if result.status in ("fail", "error"):
            worst_exit = max(worst_exit, 1)
    return worst_exit


def _run_web_assess(args: argparse.Namespace, config, logger) -> int:
    """Guided, one-command Web Assessment (Phase 10): static analysis +
    browser smoke test + report, without requiring the user to understand
    `scan`/`assess`/`browser test` as separate concepts. Reuses `_run_assess`
    unmodified for real execution -- this function only pre-sets
    `args.browser = True` (already done in `set_defaults`) and, for
    `--dry-run`, prints a human-readable plan the existing `assess --dry-run`
    path doesn't otherwise surface for browser testing (spec section 43).
    """
    if args.dry_run:
        from universal_test.adapters.browser.adapter import run as browser_run
        from universal_test.adapters.browser.serializers import plan_to_text

        plan = browser_run(args.path, target=args.target, dry_run=True)
        lines = [
            "Web Assessment Plan", "====================", "",
            f"Project: {args.path}",
            f"Target: {args.target or '(none provided)'}", "",
            "Planned checks:",
            "  - Project structure discovery",
            "  - Static frontend analysis",
        ]
        if args.target:
            lines.append("  - Browser page-load smoke test")
        else:
            lines.append("  - Browser page-load smoke test: SKIPPED (no --target provided)")
        lines += [
            "",
            "Not included: login workflow, microphone/camera verification, file upload/download,",
            "visual regression, security testing, accessibility audit, performance testing.",
            "",
        ]
        if args.target:
            lines.append(plan_to_text(plan, allow_external=args.allow_external))
        lines.append("No browser was launched; no HTTP requests were sent (dry run).")
        print("\n".join(lines))
        return 0

    return _run_assess(args, config, logger)


def _run_database(args: argparse.Namespace, logger) -> int:
    if args.format not in _DB_RESULT_SERIALIZERS:
        logger.error(
            "'database' does not yet support --format %s (that's a Phase 5 report format); "
            "use text, json, or markdown", args.format,
        )
        return 2
    if not args.database_profile:
        logger.error(
            "'database' requires --database-profile <path>; discovering database evidence in a "
            "project never implies permission to connect to it (skill.md 4.2, Phase 6 brief 4)"
        )
        return 2

    try:
        profile = load_database_profile(args.database_profile)
    except ConfigurationError as exc:
        logger.error(str(exc))
        return 2

    if args.dry_run:
        print(db_plan_to_text(profile))
        print("No database queries executed.")
        return 0

    try:
        result = db_discover(profile)
    except DatabaseError as exc:  # pragma: no cover - db_discover() already catches its own errors
        logger.error(str(exc))
        return 2

    rendered = _DB_RESULT_SERIALIZERS[args.format](result)
    _write_or_print(rendered, args.output, _FORMAT_EXTENSION[args.format], logger, "database_assessment")
    return 0 if result.info is not None else 2


def _build_current_snapshot(args: argparse.Namespace, config, model, logger):
    (
        has_confirmed_openapi, generated_count, run_result, functional_not_run_reason,
        perf_result, performance_not_run_reason, database_result,
        browser_result, browser_not_run_reason,
        scenario_results, scenario_not_run_reason,
    ) = _run_pipeline(args, config, model, logger)

    assessment = build_assessment(
        project_path=args.path, target=args.target, model=model, generated_count=generated_count,
        run_result=run_result, functional_not_run_reason=functional_not_run_reason,
        perf_result=perf_result, performance_not_run_reason=performance_not_run_reason,
        has_confirmed_openapi=has_confirmed_openapi, database_result=database_result,
        browser_result=browser_result, browser_not_run_reason=browser_not_run_reason,
        scenario_results=scenario_results, scenario_not_run_reason=scenario_not_run_reason,
    )
    snapshot = build_snapshot(
        project_path=args.path, target=args.target, model=model, generated_count=generated_count,
        run_result=run_result, perf_result=perf_result, database_result=database_result, assessment=assessment,
        browser_result=browser_result, scenario_results=scenario_results,
    )
    return snapshot


def _run_baseline_save(args: argparse.Namespace, config, logger) -> int:
    if not args.output:
        logger.error(
            "'baseline save' requires --output <path> to write the baseline file to "
            "(Phase 7 brief section 3 - storage location is always explicit, never a hidden default)"
        )
        return 2

    try:
        model = discover(args.path)
    except DiscoveryError as exc:
        logger.error(str(exc))
        return 2

    snapshot = _build_current_snapshot(args, config, model, logger)
    output_path = save_baseline(snapshot, args.output)
    logger.info("baseline saved to %s", output_path)
    print(f"Baseline saved: {output_path}")
    return 0


def _run_baseline_compare(args: argparse.Namespace, config, logger) -> int:
    if args.format not in _REGRESSION_RESULT_SERIALIZERS:
        logger.error(
            "'baseline compare' does not support --format %s; use text, json, or markdown", args.format,
        )
        return 2

    try:
        baseline_snapshot = load_baseline(args.baseline)
    except RegressionError as exc:
        logger.error(str(exc))
        return 2

    try:
        model = discover(args.path)
    except DiscoveryError as exc:
        logger.error(str(exc))
        return 2

    current_snapshot = _build_current_snapshot(args, config, model, logger)
    thresholds = dict(config.regression.performance) if config.regression.performance else {}
    regression = regression_compare(baseline_snapshot, current_snapshot, performance_thresholds=thresholds)

    rendered = _REGRESSION_RESULT_SERIALIZERS[args.format](regression)
    _write_or_print(rendered, args.output, _FORMAT_EXTENSION[args.format], logger, "regression_comparison")
    print(f"Regression Status: {regression.status.value.upper()}")
    return 0


def run() -> None:  # console-script entry point
    raise SystemExit(main())


if __name__ == "__main__":
    run()
