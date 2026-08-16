# SPDX-License-Identifier: MIT
"""Channel adapter protocol for resource acquisition.

An adapter executes one acquisition against an already-validated server
plan and an already-resolved harness scope target. Adapters never invoke a
shell; user-controlled values are passed as argv elements only.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from cli._json import JsonObject


@dataclass
class AcquisitionOutcome:
    """Result of a single channel acquisition."""

    installed_paths: list[str]
    native_evidence: JsonObject | None
    verification: str  # exact | source_revision | unverified
    notes: list[str] = field(default_factory=list)
    projection_paths: list[str] = field(default_factory=list)


class ChannelAdapter:
    """Base adapter; subclasses implement ``acquire``."""

    channel: str = ""

    def acquire(
        self,
        *,
        plan: JsonObject,
        destination: Path,
        scope_root: Path,
    ) -> AcquisitionOutcome:
        raise NotImplementedError


def run_argv(
    argv: list[str],
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
    timeout_seconds: int = 600,
    output_cap_bytes: int = 1_048_576,
) -> subprocess.CompletedProcess[bytes]:
    """Run an external native manager without a shell.

    Environment is scrubbed of secret-looking variables before overrides
    are applied; output is capped to avoid unbounded transcript capture.
    """
    import os

    if not argv:
        raise ValueError("native argv must not be empty")
    env = {
        key: value
        for key, value in os.environ.items()
        if not any(
            marker in key.upper()
            for marker in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "AUTH")
        )
    }
    env.update(env_overrides or {})
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if len(completed.stdout or b"") > output_cap_bytes:
        raise RuntimeError("native manager output exceeded cap")
    return completed
