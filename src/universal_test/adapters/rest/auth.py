"""Authentication credential resolution.

Credentials are read from environment variables named on the CLI
(`--bearer-token-env NAME`, never the raw secret as a CLI argument — the
Phase 3 brief's own example uses this shape). Nothing here ever guesses a
credential, reads one out of the scanned repository, or attempts a login —
see skill.md §4.2/§26 and the Phase 3 brief §5.

Simplification (documented in ARCHITECTURE.md): OpenAPI's `security` list
technically allows AND-combinations within one requirement object and
OR-combinations across the list; this module treats it as "the endpoint
needs any one of these named schemes" (OR only), which covers the
overwhelming majority of real-world specs (single required scheme).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from universal_test.adapters.rest.models import SecurityScheme


@dataclass(frozen=True)
class AuthConfig:
    bearer_token: str | None = None
    api_key_value: str | None = None
    api_key_header_override: str | None = None
    basic_username: str | None = None
    basic_password: str | None = None


def resolve_auth_from_env(
    bearer_token_env: str | None = None,
    api_key_env: str | None = None,
    api_key_header: str | None = None,
    basic_user_env: str | None = None,
    basic_pass_env: str | None = None,
) -> tuple[AuthConfig, list[str]]:
    """Read credentials from the named environment variables.

    Returns `(config, warnings)` — a warning is added for every `--*-env`
    flag whose named variable was not actually set, so a user doesn't
    silently get every authenticated endpoint skipped without knowing why.
    """
    warnings: list[str] = []

    def _read(env_name: str | None) -> str | None:
        if not env_name:
            return None
        value = os.environ.get(env_name)
        if value is None:
            warnings.append(f"environment variable {env_name!r} is not set; the credential it names is unavailable")
        return value

    bearer_token = _read(bearer_token_env)
    api_key_value = _read(api_key_env)
    basic_username = _read(basic_user_env)
    basic_password = _read(basic_pass_env)

    return AuthConfig(
        bearer_token=bearer_token,
        api_key_value=api_key_value,
        api_key_header_override=api_key_header,
        basic_username=basic_username,
        basic_password=basic_password,
    ), warnings


def available_scheme_names(auth_config: AuthConfig, security_schemes: dict[str, SecurityScheme]) -> set[str]:
    available: set[str] = set()
    for name, scheme in security_schemes.items():
        if scheme.type == "http" and scheme.scheme == "bearer" and auth_config.bearer_token:
            available.add(name)
        elif scheme.type == "http" and scheme.scheme == "basic" and auth_config.basic_username and auth_config.basic_password:
            available.add(name)
        elif scheme.type == "apiKey" and auth_config.api_key_value:
            available.add(name)
        elif scheme.type in ("oauth2", "openIdConnect") and auth_config.bearer_token:
            # pragmatic simplification: reuse a supplied bearer token for oauth2/OIDC-protected
            # endpoints, since most such APIs accept "Authorization: Bearer <token>" regardless
            # of how the token was obtained. Documented in ARCHITECTURE.md.
            available.add(name)
    return available


def build_auth_headers(
    endpoint_security: list[str], security_schemes: dict[str, SecurityScheme], auth_config: AuthConfig,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return `(headers, query_params)` to merge into a request for the first
    scheme in `endpoint_security` we have a credential for. Both are empty
    if none apply.
    """
    for name in endpoint_security:
        scheme = security_schemes.get(name)
        if scheme is None:
            continue
        if scheme.type == "http" and scheme.scheme == "bearer" and auth_config.bearer_token:
            return {"Authorization": f"Bearer {auth_config.bearer_token}"}, {}
        if scheme.type == "http" and scheme.scheme == "basic" and auth_config.basic_username and auth_config.basic_password:
            import base64
            token = base64.b64encode(f"{auth_config.basic_username}:{auth_config.basic_password}".encode()).decode()
            return {"Authorization": f"Basic {token}"}, {}
        if scheme.type == "apiKey" and auth_config.api_key_value:
            header_name = auth_config.api_key_header_override or scheme.param_name or "X-API-Key"
            if scheme.location == "query":
                return {}, {(scheme.param_name or "api_key"): auth_config.api_key_value}
            return {header_name: auth_config.api_key_value}, {}
        if scheme.type in ("oauth2", "openIdConnect") and auth_config.bearer_token:
            return {"Authorization": f"Bearer {auth_config.bearer_token}"}, {}
    return {}, {}
