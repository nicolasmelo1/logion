from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.files import UsagePendingEmptyAssertion
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _context(tmp_path: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="usage-isolation",
        phase_id="isolated-user",
        world=World(run_id="r1", base_url="http://mock", root_dir=tmp_path),
        api=MockApiAdapter(),
        artifacts_dir=tmp_path,
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


@pytest.mark.asyncio
async def test_usage_pending_empty_requires_an_empty_data_array(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "pending.json"
    artifact.write_text(json.dumps({"data": []}), encoding="utf-8")
    context = _context(tmp_path)

    outcome = await UsagePendingEmptyAssertion().evaluate(
        context, {"path": str(artifact)}
    )

    assert outcome.status == "passed"
    context.timeline.close()


@pytest.mark.asyncio
async def test_usage_pending_empty_rejects_nonempty_data(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "pending.json"
    artifact.write_text(json.dumps({"data": [{"observation_id": "x"}]}))
    context = _context(tmp_path)

    outcome = await UsagePendingEmptyAssertion().evaluate(
        context, {"path": str(artifact)}
    )

    assert outcome.status == "failed"
    context.timeline.close()
