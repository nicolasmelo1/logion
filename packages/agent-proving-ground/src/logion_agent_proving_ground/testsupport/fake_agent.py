from __future__ import annotations

from logion_agent_proving_ground.drivers.scripted import (
    ScriptedDriver,
    ScriptedOperation,
)


def fake_scripted_driver(
    operations: dict[str, list[ScriptedOperation]] | None = None,
) -> ScriptedDriver:
    return ScriptedDriver(operations=operations)
