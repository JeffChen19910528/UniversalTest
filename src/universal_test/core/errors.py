"""Exception hierarchy shared across Core and all adapters."""

from __future__ import annotations


class UniversalTestError(Exception):
    """Base class for all errors raised by universal-test."""


class ConfigurationError(UniversalTestError):
    """Raised when `universal-test.yaml` or CLI configuration is invalid."""


class DiscoveryError(UniversalTestError):
    """Raised when project discovery fails in an unrecoverable way."""


class AdapterError(UniversalTestError):
    """Raised by adapter implementations for adapter-specific failures."""


class ExecutionError(UniversalTestError):
    """Raised when executing a test case fails outside of assertion evaluation."""


class AssertionEngineError(UniversalTestError):
    """Raised for assertion-engine problems (e.g. unknown assertion type).

    Named to avoid shadowing the builtin ``AssertionError``.
    """


class OpenApiError(UniversalTestError):
    """Raised when an OpenAPI/Swagger document cannot be found or parsed,
    or when the project has multiple candidate specs and none was selected
    (skill.md-derived Phase 3 rule: never silently pick one)."""


class TargetError(ExecutionError):
    """Raised when a configured execution target is invalid or unreachable
    for reasons other than a network-level failure (e.g. malformed URL)."""


class NetworkError(ExecutionError):
    """Raised when a request to the execution target fails at the network
    layer (connection refused, DNS failure, etc.) — distinct from an
    assertion failure: the target was unreachable, not "the API is broken".
    """


class RequestTimeoutError(ExecutionError):
    """Raised when a request to the execution target exceeds its timeout.

    Named to avoid shadowing the builtin ``TimeoutError``.
    """


class DatabaseError(AdapterError):
    """Base class for database-adapter errors (Phase 6)."""


class DatabaseDriverUnavailableError(DatabaseError):
    """Raised when the Python driver for a database engine isn't installed.

    Never triggers an automatic install (skill.md §4.2) — callers should
    catch this and report a `NOT_ASSESSED` finding with the missing driver
    named, not attempt to work around it.
    """


class DatabaseConnectionError(DatabaseError):
    """Raised when connecting to a database fails (refused, auth failure,
    unreachable host, etc.) — never treated as "the database is broken",
    only as "we could not assess it" (Phase 6 brief §16)."""


class DatabaseTimeoutError(DatabaseError):
    """Raised when a database connection or metadata query exceeds its
    configured timeout. Named to avoid shadowing the builtin ``TimeoutError``.
    """


class RegressionError(UniversalTestError):
    """Raised for baseline/regression problems: an unsupported baseline
    schema version, a malformed baseline file, or a missing baseline path
    (Phase 7). Never guessed around — an incompatible baseline is refused
    outright rather than partially parsed."""
