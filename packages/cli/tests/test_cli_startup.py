# SPDX-License-Identifier: MIT
"""Cold-start import budget for parser-only CLI paths."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from textwrap import dedent
from typing import get_type_hints

_MAX_PYTHON_STARTUP_MULTIPLIER = 15
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUBPROCESS_TIMEOUT_SECONDS = 10
_TIMING_ROUNDS = 7
_SUBPROCESS_ENV = dict(os.environ)
_SUBPROCESS_ENV["PYTHONPATH"] = os.pathsep.join([
    str(_REPO_ROOT / "packages" / "cli"),
    str(_REPO_ROOT / "packages" / "client" / "src"),
    str(_REPO_ROOT / "packages" / "skillmap"),
])


def test_parser_build_does_not_load_runtime_dependencies() -> None:
    """Parser setup must not import SDK or validation dependencies."""
    probe = dedent(
        """
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
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        cwd=_REPO_ROOT,
        env=_SUBPROCESS_ENV,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )

    assert json.loads(result.stdout) == []


def test_client_factory_loads_sdk_only_when_called() -> None:
    """The lazy factory still constructs and closes the real SDK client."""
    probe = dedent(
        """
        import sys

        from cli._config import CliConfig
        from cli._context import make_client

        assert "logion" not in sys.modules
        client = make_client(
            CliConfig(
                api_key=None,
                base_url="http://127.0.0.1:1",
                json_output=False,
                timeout=0.1,
                max_retries=0,
            )
        )
        try:
            assert "logion" in sys.modules
        finally:
            client.close()
        """
    )
    subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        cwd=_REPO_ROOT,
        env=_SUBPROCESS_ENV,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def test_lazy_runtime_type_hints_remain_resolvable() -> None:
    """Lazy imports preserve runtime type-introspection behavior."""
    import httpx

    from cli._context import _LogionClientFactory, make_client
    from cli.commands.course_reviews._download_handler import _download_files
    from cli.commands.credits.handlers import _poll_top_up
    from logion import LogionClient

    assert get_type_hints(make_client)["return"] is LogionClient
    assert (
        get_type_hints(_LogionClientFactory.__call__)["return"] is LogionClient
    )
    assert get_type_hints(_download_files)["http"] is httpx.Client
    assert get_type_hints(_poll_top_up)["client"] is LogionClient


def _elapsed(command: list[str]) -> float:
    start = time.perf_counter()
    subprocess.run(
        command,
        check=True,
        cwd=_REPO_ROOT,
        env=_SUBPROCESS_ENV,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
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
