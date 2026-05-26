"""Logion Marketplace Companion eval harness.

Deterministic harness for grading whether the bootstrap skill routes,
searches, inspects, installs, and refuses actions correctly.
"""

from evals.harness.schema import Catalog, Scenario, ToolCall, Trace

__all__ = ["Catalog", "Scenario", "ToolCall", "Trace"]
