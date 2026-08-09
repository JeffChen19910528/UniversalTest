"""Root pytest configuration shared by the whole test suite.

Importing `core.logging_setup` here guarantees the `universal_test` logger's
`propagate = False` is set during collection, before any test's `caplog`
fixture attaches its capture handler for the first time -- independent of
which test module (if any) happens to import the CLI/logging modules first.
See `core/logging_setup.py` for why import-time ordering matters here.
"""

import universal_test.core.logging_setup  # noqa: F401
