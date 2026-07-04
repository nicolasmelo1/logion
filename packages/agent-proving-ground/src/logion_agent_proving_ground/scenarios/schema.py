from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from logion_agent_proving_ground.config import SAFE_NAME_RE


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    driver: str | None = None
    workspace: str | None = None
    devrig_role: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    system_prompt: str | None = None
    max_turns: int = Field(default=40, ge=1)
    timeout_seconds: int = Field(default=900, ge=1)

    @field_validator("id", "workspace")
    @classmethod
    def _filesystem_safe(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.match(SAFE_NAME_RE, value):
            raise ValueError(f"must match {SAFE_NAME_RE}: {value}")
        return value

    @field_validator("devrig_role")
    @classmethod
    def _devrig_role_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"seller", "buyer", "admin"}
        if value not in allowed:
            raise ValueError(
                f"devrig_role must be one of {allowed}, got {value}"
            )
        return value


class AssertionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    params: dict = Field(default_factory=dict)
    optional: bool = False


class PhaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    actor: str
    goal: str
    timeout_seconds: int = Field(default=900, ge=1)
    success_hint: str | None = None
    assertions: list[AssertionSpec] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_safe(cls, value: str) -> str:
        if not re.match(SAFE_NAME_RE, value):
            raise ValueError(f"phase id must match {SAFE_NAME_RE}: {value}")
        return value


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    name: str
    description: str
    api_adapter: str = "mock"
    agents: list[AgentSpec]
    phases: list[PhaseSpec]
    final_assertions: list[AssertionSpec] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_safe(cls, value: str) -> str:
        if not re.match(SAFE_NAME_RE, value):
            raise ValueError(
                f"scenario name must match {SAFE_NAME_RE}: {value}"
            )
        return value

    @model_validator(mode="after")
    def _agents_and_phases(self) -> ScenarioSpec:
        agent_ids = {a.id for a in self.agents}
        if len(agent_ids) != len(self.agents):
            raise ValueError("agent ids must be unique")
        seen: set[str] = set()
        for phase in self.phases:
            if phase.actor not in agent_ids:
                raise ValueError(f"phase actor {phase.actor} is not an agent")
            if phase.id in seen:
                raise ValueError(f"duplicate phase id: {phase.id}")
            seen.add(phase.id)
        if not self.agents:
            raise ValueError("at least one agent is required")
        if not self.phases:
            raise ValueError("at least one phase is required")
        return self


def validate_assertions(_spec: ScenarioSpec) -> None:
    """Assertion types are resolved at runtime.

    Schema validation stays permissive so optional future assertions can be
    declared without hard-coding the registry here.
    """
    return
