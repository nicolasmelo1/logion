from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class World(BaseModel):
    run_id: str
    base_url: str
    root_dir: Path
    agent_env: dict[str, dict[str, str]] = Field(default_factory=dict)
    handles: dict[str, str] = Field(default_factory=dict)
    data: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class AgentLaunch:
    run_id: str
    agent_id: str
    role: str
    workspace: Path
    env: dict[str, str]
    system_prompt: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class AgentTurnResult:
    status: Literal["completed", "failed", "inconclusive", "timed_out"]
    transcript_path: Path
    summary: str | None = None
    raw_exit_code: int | None = None


class AssertionOutcome(BaseModel):
    type: str
    status: Literal["passed", "failed", "unsupported"]
    message: str
    evidence: dict = Field(default_factory=dict)


class ScenarioResult(BaseModel):
    run_id: str
    scenario: str
    status: Literal["passed", "failed", "inconclusive"]
    api_adapter: str
    agent_drivers: dict[str, str]
    started_at: str
    finished_at: str
    phase_results: list[dict] = Field(default_factory=list)
    assertion_results: list[AssertionOutcome] = Field(default_factory=list)
    artifact_root: Path
    failure_message: str | None = None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
