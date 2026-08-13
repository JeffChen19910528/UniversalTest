"""Target safety policy (spec §6-§9): explicit target only, localhost/127.0.0.1/
::1/file:// allowed by default, anything else requires an explicit opt-in.

Pure function, no Playwright dependency -- unit-testable without a browser.
Never attempts to infer "looks like production"; the only boundary is
explicit target + explicit `allow_external` authorization (spec §8).
"""

from __future__ import annotations

from urllib.parse import urlparse

from universal_test.adapters.browser.errors import BrowserTargetError

_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}


def validate_target(target: str, *, allow_external: bool = False) -> None:
    """Raise `BrowserTargetError` if `target` is not permitted by policy.

    Called before any navigation -- never after.
    """
    if not target or not isinstance(target, str):
        raise BrowserTargetError("no target was provided")

    parsed = urlparse(target)

    if parsed.scheme == "file":
        return  # static local files are always allowed (spec §6/§17)

    if parsed.scheme not in ("http", "https"):
        raise BrowserTargetError(
            f"unsupported target scheme {parsed.scheme!r}; only http, https, and file are supported"
        )

    hostname = (parsed.hostname or "").lower()
    if hostname in _LOCAL_HOSTNAMES:
        return

    if not allow_external:
        raise BrowserTargetError(
            f"target host {hostname!r} is not localhost/127.0.0.1/::1 -- external targets "
            "require an explicit --allow-external authorization (spec section 7)"
        )


def is_same_origin(target: str, candidate_url: str) -> bool:
    """Used by the executor to decide whether a navigation triggered *during*
    a test (e.g. clicking a link) stays within the authorized origin."""
    target_parsed = urlparse(target)
    candidate_parsed = urlparse(candidate_url)
    if candidate_parsed.scheme == "file" or target_parsed.scheme == "file":
        return target_parsed.path == candidate_parsed.path
    return (target_parsed.scheme, target_parsed.hostname, target_parsed.port) == (
        candidate_parsed.scheme, candidate_parsed.hostname, candidate_parsed.port,
    )
