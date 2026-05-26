"""Pluggable provider interface for the eval harness.

Providers translate a (scenario, catalog) pair into a concrete Trace.
The default ``fake`` provider replays the scenario's embedded fake_trace,
which keeps the harness deterministic and CI-friendly. Real LLM providers
can be added later by implementing the same ``run`` signature.
"""

from evals.harness.providers.fake import FakeProvider

__all__ = ["FakeProvider"]
