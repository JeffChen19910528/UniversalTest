"""Project discovery: filesystem/language/framework/service/api/database detection.

Read-only. See `discovery.engine.discover()` for the entry point and
`discovery.models.ProjectModel` for the normalized result (Phase 2).
"""

from universal_test.discovery.engine import discover
from universal_test.discovery.models import ProjectModel

__all__ = ["discover", "ProjectModel"]
