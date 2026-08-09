"""Read-only database discovery adapter (Phase 6).

Supports SQL Server, PostgreSQL, MySQL (each via an optional driver
dependency, lazily imported) and SQLite (stdlib `sqlite3`, always
available). Only ever connects when the caller supplies an explicit
`DatabaseProfile` (`--database-profile <path>`) — discovering database
*evidence* in a project (Phase 2) never implies permission to connect to
it. No method anywhere in this package can execute arbitrary SQL or mutate
data — see `base.py`'s `DatabaseDriver` contract.
"""

from universal_test.adapters.database.adapter import DatabaseDiscoveryResult, discover
from universal_test.adapters.database.models import DatabaseEngine, DatabaseInfo
from universal_test.adapters.database.profile import DatabaseProfile, load_database_profile

__all__ = [
    "DatabaseDiscoveryResult",
    "discover",
    "DatabaseEngine",
    "DatabaseInfo",
    "DatabaseProfile",
    "load_database_profile",
]
