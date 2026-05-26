"""Compatibility wrapper for the llama.cpp live-eval provider.

The harness implementation lives under ``evals.harness.providers`` because the
runner imports providers as part of the harness package. This module keeps the
Phase 6.5 path shape (`evals/providers/llama_cpp.py`) available for humans and
future scripts without duplicating logic.
"""

from evals.harness.providers.llama_cpp import *  # noqa: F403
