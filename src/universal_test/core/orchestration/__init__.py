"""Run coordination. Phase 1 only wires "run these test cases"; discovery/adapters/
assessment/reporting stages are added to the pipeline in later phases.
"""

from universal_test.core.orchestration.orchestrator import Orchestrator, RunResult

__all__ = ["Orchestrator", "RunResult"]
