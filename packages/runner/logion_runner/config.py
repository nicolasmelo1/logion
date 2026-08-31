"""Runner node configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_URL_ENV = "LOGION_NODE_BASE_URL"
STATE_DIR_ENV = "LOGION_NODE_STATE_DIR"
RUNNER_NAME_ENV = "LOGION_NODE_RUNNER_NAME"
BACKEND_ENV = "LOGION_NODE_BACKEND"
IMAGE_ENV = "LOGION_NODE_IMAGE"

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_STATE_DIRNAME = ".logion-node"


def default_state_dir() -> Path:
    """Return the default state directory: ``$HOME/.logion-node``."""
    return Path.home() / DEFAULT_STATE_DIRNAME


@dataclass(frozen=True)
class RunnerConfig:
    """Where the runner finds its coordinator and its local state.

    Values come from the environment (``LOGION_NODE_*``) with defaults
    suitable for a local developer node talking to a dev coordinator on
    the same machine.
    """

    base_url: str = DEFAULT_BASE_URL
    state_dir: Path = field(default_factory=default_state_dir)
    runner_name: str = ""
    backend: str = "docker"
    image: str = ""

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> RunnerConfig:
        """Build a config from *env* (default: the process environment)."""
        source = os.environ if env is None else env
        base_url = source.get(BASE_URL_ENV, DEFAULT_BASE_URL).strip()
        state_raw = source.get(STATE_DIR_ENV, "").strip()
        state_dir = (
            Path(state_raw).expanduser() if state_raw else default_state_dir()
        )
        name = source.get(RUNNER_NAME_ENV, "").strip()
        backend = source.get(BACKEND_ENV, "docker").strip().lower()
        if backend not in {"docker", "local-test"}:
            raise ValueError(
                "LOGION_NODE_BACKEND must be docker or local-test"
            )
        return cls(
            base_url=base_url,
            state_dir=state_dir,
            runner_name=name,
            backend=backend,
            image=source.get(IMAGE_ENV, "").strip(),
        )


def job_history_path(state_dir: Path) -> Path:
    """Path of the local run-history file inside *state_dir*."""
    return state_dir / "jobs.jsonl"
