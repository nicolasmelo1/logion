from __future__ import annotations

import json

from logion_agent_proving_ground.timeline import Timeline


def test_timeline_writes_valid_jsonl_in_order(tmp_path) -> None:
    path = tmp_path / "timeline.jsonl"
    timeline = Timeline(path)
    timeline.event("run.started", run_id="r1")
    timeline.event("agent.started", agent_id="a1")
    timeline.event("phase.started", phase_id="p1")
    timeline.close()

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    types = [json.loads(line)["type"] for line in lines]
    assert types == ["run.started", "agent.started", "phase.started"]
