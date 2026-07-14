# SPDX-License-Identifier: MIT
"""Cold-start import budget for parser-only CLI paths."""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time

_MAX_PYTHON_STARTUP_MULTIPLIER = 15
_TIMING_ROUNDS = 7


def test_parser_build_does_not_load_runtime_dependencies() -> None:
    """Parser setup must not import SDK or validation dependencies."""
    probe = """
import json
import sys

from cli._parser import build_parser

build_parser()
forbidden_roots = {
    "anyio",
    "httpcore",
    "httpx",
    "logion",
    "pydantic",
    "pydantic_core",
}
loaded = sorted(
    name
    for name in sys.modules
    if name.split(".", 1)[0] in forbidden_roots
)
print(json.dumps(loaded))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def _elapsed(command: list[str]) -> float:
    start = time.perf_counter()
    subprocess.run(
        command,
        check=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    return time.perf_counter() - start


def test_help_cold_start_stays_within_relative_budget() -> None:
    """Cold help stays below the baseline-relative startup budget."""
    python = [sys.executable, "-c", "pass"]
    help_command = [sys.executable, "-m", "cli.main", "--help"]
    _elapsed(python)
    _elapsed(help_command)

    python_samples: list[float] = []
    help_samples: list[float] = []
    for _ in range(_TIMING_ROUNDS):
        python_samples.append(_elapsed(python))
        help_samples.append(_elapsed(help_command))

    python_median = statistics.median(python_samples)
    help_median = statistics.median(help_samples)
    assert help_median < python_median * _MAX_PYTHON_STARTUP_MULTIPLIER, (
        f"help startup {help_median:.3f}s exceeded "
        f"{_MAX_PYTHON_STARTUP_MULTIPLIER}x Python startup "
        f"({python_median:.3f}s)"
    )
