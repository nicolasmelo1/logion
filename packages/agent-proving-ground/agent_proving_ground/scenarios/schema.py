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

#: Flags whose value is the agent's own judgement about a resource. A scenario
#: that writes the number itself proves the write path and calls it a report:
#: the run then carries a rating nobody formed, into the one signal class the
#: product sells as deliberate agent judgement. Placeholders are fine — the
#: shape of the command is plumbing, the number is the claim.
_JUDGEMENT_FLAGS = (
    "rating",
    "usefulness",
    "reliability",
    "tool-safety",
    "token-efficiency",
)
_DICTATED_JUDGEMENT_RE = re.compile(
    r"--(" + "|".join(_JUDGEMENT_FLAGS) + r")[= ]\s*\d",
)


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

    @model_validator(mode="after")
    def _hook_phase_prompt_is_not_a_caption(self) -> PhaseSpec:
        """A goal over rig work must be work, not a caption on work done.

        ``_run_phase`` runs the hook *and then* sends the goal, so both
        shapes exist and only one is honest. A hook that prepares state the
        agent then acts on is legitimate, and every one of those asserts
        what the agent did. A one-line goal restating what the script just
        did asserts nothing, and it is how a scenario reads as agent
        coverage it does not have: nine scripted phases with a caption each
        look like nine agent phases in every listing.
        """
        if not self.local_hook or not self.goal.strip():
            return self
        if not self.assertions:
            raise ValueError(
                f"phase {self.id} runs a local_hook and also sends a goal, "
                "but asserts nothing about what the agent did. Either assert "
                'the agent\'s effect, or set goal: "" and move the '
                "description into a YAML comment: a caption over rig work "
                "counts as agent coverage in every listing and proves none."
            )
        return self

    @model_validator(mode="after")
    def _judgement_is_not_dictated(self) -> PhaseSpec:
        """The agent's rating must not be typed by the scenario author."""
        for name, text in (
            ("goal", self.goal),
            ("success_hint", self.success_hint or ""),
        ):
            match = _DICTATED_JUDGEMENT_RE.search(text)
            if match:
                raise ValueError(
                    f"phase {self.id} {name} dictates a judgement value "
                    f"({match.group(0).strip()}). Feedback ratings are the "
                    "one signal class the product sells as the agent's own; "
                    "write the flag with a placeholder and let the agent "
                    "choose the number."
                )
        return self


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
    #: What the scenario can be evidence *of*. ``agent`` means at least one
    #: phase is a real agent turn against observed effects; ``rig`` means the
    #: whole scenario is rig-driven, so it is an integration test that happens
    #: to run here and can never be evidence about agent behaviour. Declared,
    #: not inferred, because the count of "scenarios" is what a reader uses to
    #: judge how much of the product an agent has actually driven.
    kind: Literal["agent", "rig"] = "agent"
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

    @model_validator(mode="after")
    def _kind_matches_the_phases(self) -> ScenarioSpec:
        """The declared kind has to be what the phases actually are."""
        agent_phases = self.agent_phase_ids
        if self.kind == "agent" and not agent_phases:
            raise ValueError(
                f"scenario {self.name} declares kind: agent and has no phase "
                "that sends a goal to an agent. Declare kind: rig — a "
                "rig-driven scenario is a valid integration test and an "
                "invalid piece of evidence about what an agent can do."
            )
        if self.kind == "rig" and agent_phases:
            raise ValueError(
                f"scenario {self.name} declares kind: rig but sends a goal "
                "to an agent in: " + ", ".join(agent_phases)
            )
        return self

    @property
    def agent_phase_ids(self) -> list[str]:
        """Phases decided by an agent turn rather than by the rig."""
        return [p.id for p in self.phases if p.goal.strip()]


def validate_assertions(_spec: ScenarioSpec) -> None:
    """Assertion types are resolved at runtime.

    Schema validation stays permissive so optional future assertions can be
    declared without hard-coding the registry here.
    """
    return
