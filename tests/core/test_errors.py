from universal_test.core.errors import (
    AdapterError,
    AssertionEngineError,
    ConfigurationError,
    DiscoveryError,
    ExecutionError,
    UniversalTestError,
)


def test_all_errors_derive_from_universal_test_error():
    for exc_type in (
        ConfigurationError,
        DiscoveryError,
        AdapterError,
        ExecutionError,
        AssertionEngineError,
    ):
        assert issubclass(exc_type, UniversalTestError)
