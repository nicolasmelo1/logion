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

from agent_proving_ground.config import SAFE_NAME_RE


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    driver: str | None = None
    workspace: str | None = None
    devrig_role: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    system_prompt: str | None = None
    timeout_seconds: int = Field(default=900, ge=1)
    command: list[str] | None = None
    #: Whether the rig puts the Logion CLI on this agent's PATH. The rig
    #: provisions one for every agent with a devrig role, so a scenario whose
    #: premise is "this actor never installed Logion" cannot state that in
    #: prose alone — the agent can still reach the CLI and the run proves
    #: something other than what it claims.
    logion_cli: bool = True

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
    capture: dict[str, str] = Field(default_factory=dict)

    @field_validator("capture")
    @classmethod
    def _capture_names_are_valid(cls, value: dict[str, str]) -> dict[str, str]:
        invalid = [
            name
            for name in value
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name)
        ]
        if invalid:
            raise ValueError(
                "capture names must use uppercase "
                "environment-variable syntax: " + ", ".join(sorted(invalid))
            )
        return value


class PhaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    actor: str
    goal: str
    timeout_seconds: int = Field(default=900, ge=1)
    success_hint: str | None = None
    local_hook: str | None = None
    local_hook_args: list[str] = Field(default_factory=list)
    local_hook_capture_json: dict[str, str] = Field(default_factory=dict)
    assertions: list[AssertionSpec] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_safe(cls, value: str) -> str:
        if not re.match(SAFE_NAME_RE, value):
            raise ValueError(f"phase id must match {SAFE_NAME_RE}: {value}")
        return value

    @field_validator("local_hook_capture_json")
    @classmethod
    def _capture_names_are_valid(cls, value: dict[str, str]) -> dict[str, str]:
        invalid = [
            name
            for name in value
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name)
        ]
        if invalid:
            raise ValueError(
                "local_hook_capture_json names must use uppercase "
                "environment-variable syntax: " + ", ".join(sorted(invalid))
            )
        return value


class ExecutionRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_adapters: list[str] = Field(default_factory=list)
    agent_drivers: list[str] = Field(default_factory=list)
    driver_models: dict[str, list[str]] = Field(default_factory=dict)


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    name: str
    description: str
    api_adapter: str = "mock"
    driver_config: dict = Field(default_factory=dict)
    execution_requirements: ExecutionRequirements = Field(
        default_factory=ExecutionRequirements
    )
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
