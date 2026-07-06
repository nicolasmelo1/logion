from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_proving_ground.config import InconclusiveRun


class DevrigEnvError(InconclusiveRun):
    """Raised when the local-devrig adapter cannot read devrig.env."""


def parse_export_env_file(path: Path) -> dict[str, str]:
    """Parse a shell-style env file that uses `export KEY=value` lines.

    Values may be quoted with single or double quotes. Blank lines and
    lines starting with `#` are ignored. The result is a plain string
    mapping with unquoted values.
    """
    if not path.is_file():
        raise DevrigEnvError(f"devrig env file not found: {path}")

    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def build_devrig_env_for_agent(
    base_env: dict[str, str],
    agent_id: str,
    devrig_role: str | None,
    run_id: str,
) -> dict[str, str]:
    """Materialize per-agent environment from a shared devrig env.

    The shared LOGION_DEVRIG_ROLE is overridden with the agent's declared
    role, and proving-ground metadata is added. All other values are
    copied unchanged.
    """
    agent_env = dict(base_env)
    if devrig_role:
        agent_env["LOGION_DEVRIG_ROLE"] = devrig_role
    agent_env.setdefault("LOGION_DEVRIG_ROLE", "seller")
    agent_env["LOGION_PROVING_GROUND_RUN_ID"] = run_id
    agent_env["LOGION_PROVING_GROUND_AGENT_ID"] = agent_id
    return agent_env


def validate_devrig_env(env: dict[str, str], *, label: str = "devrig") -> None:
    """Ensure the env contains the minimal devrig contract keys."""
    required = [
        "LOGION_DEVRIG_MODE",
        "LOGION_BASE_URL",
        "LOGION_API_BASE_URL",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise DevrigEnvError(
            f"{label} env is missing required keys: {', '.join(missing)}"
        )
    if env["LOGION_DEVRIG_MODE"] not in {"mock", "prod"}:
        raise DevrigEnvError(
            f"{label} env has invalid LOGION_DEVRIG_MODE: "
            f"{env['LOGION_DEVRIG_MODE']}"
        )


def env_file_description(env: dict[str, str]) -> dict[str, Any]:
    """Return a redaction-safe summary of devrig env for artifacts."""
    return {
        "mode": env.get("LOGION_DEVRIG_MODE"),
        "base_url": env.get("LOGION_BASE_URL"),
        "api_base_url": env.get("LOGION_API_BASE_URL"),
        "companion_source": env.get("LOGION_COMPANION_BUNDLE_SOURCE"),
    }
