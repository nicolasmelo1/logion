from __future__ import annotations

import pytest
from pydantic import ValidationError

from logion_agent_proving_ground.scenarios.schema import (
    ScenarioSpec,
    validate_assertions,
)


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError, match="Extra inputs are not permitted"
    ):
        ScenarioSpec.model_validate({
            "name": "bad",
            "description": "d",
            "agents": [{"id": "a", "role": "r"}],
            "phases": [{"id": "p", "actor": "a", "goal": "g"}],
            "unknown_field": True,
        })


def test_schema_rejects_duplicate_agent_ids() -> None:
    with pytest.raises(ValidationError, match="agent ids must be unique"):
        ScenarioSpec.model_validate({
            "name": "dup",
            "description": "d",
            "agents": [
                {"id": "a", "role": "r1"},
                {"id": "a", "role": "r2"},
            ],
            "phases": [{"id": "p", "actor": "a", "goal": "g"}],
        })


def test_schema_rejects_phase_actor_not_in_agents() -> None:
    with pytest.raises(
        ValidationError, match="phase actor missing is not an agent"
    ):
        ScenarioSpec.model_validate({
            "name": "bad_actor",
            "description": "d",
            "agents": [{"id": "a", "role": "r"}],
            "phases": [{"id": "p", "actor": "missing", "goal": "g"}],
        })


def test_validate_assertions_accepts_unsupported_required() -> None:
    spec = ScenarioSpec.model_validate({
        "name": "unknown_assertion",
        "description": "d",
        "agents": [{"id": "a", "role": "r"}],
        "phases": [
            {
                "id": "p",
                "actor": "a",
                "goal": "g",
                "assertions": [{"type": "api.unknown_assertion"}],
            }
        ],
    })
    # schema validation stays permissive; runtime assertion registry fails
    # unknown required assertions.
    assert validate_assertions(spec) is None
