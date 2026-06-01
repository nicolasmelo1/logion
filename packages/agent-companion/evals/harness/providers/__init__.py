# SPDX-License-Identifier: MIT
"""Pluggable provider interface for the eval harness.

Providers translate a (scenario, catalog) pair into a concrete Trace.
The default ``fake`` provider replays the scenario's embedded fake_trace,
which keeps the harness deterministic and CI-friendly. The llama.cpp
provider targets a local OpenAI-compatible ``llama-server`` for opt-in live
Apple Silicon eval runs.
"""

from evals.harness.providers.fake import FakeProvider
from evals.harness.providers.llama_cpp import (
    LlamaCppProvider,
    LlamaCppProviderError,
    load_llama_cpp_provider,
)

__all__ = [
    "FakeProvider",
    "LlamaCppProvider",
    "LlamaCppProviderError",
    "load_llama_cpp_provider",
]
