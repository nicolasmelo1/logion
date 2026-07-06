from __future__ import annotations

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.files import FileExistsAssertion
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


async def test_files_exists_rejects_absolute_path(tmp_path) -> None:
    assertion = FileExistsAssertion()
    timeline_path = tmp_path / "timeline.jsonl"
    ctx = AssertionContext(
        scenario_name="test",
        phase_id=None,
        world=World(run_id="r1", base_url="http://mock", root_dir=tmp_path),
        api=MockApiAdapter(),
        artifacts_dir=tmp_path,
        timeline=Timeline(timeline_path),
    )

    outcome = await assertion.evaluate(ctx, {"path": "/tmp/escape.txt"})

    assert outcome.status == "failed"
    assert "path traversal rejected" in outcome.message
    ctx.timeline.close()
