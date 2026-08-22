"""Argument parsing for the `universal-test` CLI (skill.md §17).

Split out of `cli.main` so argparse wiring (this module) stays independent
of command execution logic (`cli.main`'s `_run_*` handlers) -- the two
change for different reasons and are each easier to read and test alone.
"""

from __future__ import annotations

import argparse

from universal_test import __version__


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
