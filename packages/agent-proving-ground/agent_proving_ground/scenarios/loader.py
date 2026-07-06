from __future__ import annotations

from pathlib import Path

import yaml

from agent_proving_ground.config import BUILTIN_SCENARIOS_ROOT
from agent_proving_ground.scenarios.schema import (
    ScenarioSpec,
    validate_assertions,
)

BUILTIN_PREFIX = "builtin:"


def load_scenario(source: str) -> ScenarioSpec:
    if source.startswith(BUILTIN_PREFIX):
        name = source[len(BUILTIN_PREFIX) :]
        path = BUILTIN_SCENARIOS_ROOT / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"builtin scenario not found: {name}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"scenario file not found: {source}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec = ScenarioSpec.model_validate(raw)
    validate_assertions(spec)
    return spec


def list_builtin_scenarios() -> list[str]:
    names: list[str] = []
    if not BUILTIN_SCENARIOS_ROOT.exists():
        return names
    for path in sorted(BUILTIN_SCENARIOS_ROOT.iterdir()):
        if path.suffix == ".yaml":
            names.append(path.stem)
    return names
