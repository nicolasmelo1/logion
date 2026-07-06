from __future__ import annotations

from pathlib import Path

from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.db import (
    DbExactCreditLedgerAssertion,
    DbRowExistsAssertion,
    EventsOutboxContainsAssertion,
)
from agent_proving_ground.assertions.logs import (
    LogsContainsRequestAssertion,
    LogsNo500sAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


async def _ctx(tmp_path: Path, data: dict | None = None) -> AssertionContext:
    return AssertionContext(
        scenario_name="test",
        phase_id="p1",
        world=World(
            run_id="r1",
            base_url="http://example.test",
            root_dir=tmp_path,
            data=data or {},
        ),
        api=None,  # type: ignore[arg-type]
        artifacts_dir=tmp_path,
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


async def test_logs_no_500s_unsupported_without_log(tmp_path) -> None:
    ctx = await _ctx(tmp_path)
    result = await LogsNo500sAssertion().evaluate(ctx, {})
    assert result.status == "unsupported"


async def test_logs_no_500s_passes_when_clean(tmp_path) -> None:
    log = tmp_path / "services"
    log.mkdir()
    (log / "api.log").write_text("GET /v1/health 200 OK\n", encoding="utf-8")
    ctx = await _ctx(tmp_path)
    result = await LogsNo500sAssertion().evaluate(ctx, {})
    assert result.status == "passed"


async def test_logs_no_500s_fails_on_500(tmp_path) -> None:
    log = tmp_path / "services"
    log.mkdir()
    (log / "api.log").write_text(
        'GET /v1/health HTTP/1.1" 500\n', encoding="utf-8"
    )
    ctx = await _ctx(tmp_path)
    result = await LogsNo500sAssertion().evaluate(ctx, {})
    assert result.status == "failed"


async def test_logs_contains_request_passes_when_present(tmp_path) -> None:
    log = tmp_path / "services"
    log.mkdir()
    (log / "api.log").write_text("GET /v1/courses\n", encoding="utf-8")
    ctx = await _ctx(tmp_path)
    result = await LogsContainsRequestAssertion().evaluate(
        ctx, {"method": "GET", "path": "/v1/courses"}
    )
    assert result.status == "passed"


async def test_db_assertions_unsupported_without_db_url(tmp_path) -> None:
    ctx = await _ctx(tmp_path)
    assert (
        await DbRowExistsAssertion().evaluate(ctx, {"table": "users"})
    ).status == "unsupported"
    assert (
        await DbExactCreditLedgerAssertion().evaluate(ctx, {})
    ).status == "unsupported"
    assert (
        await EventsOutboxContainsAssertion().evaluate(ctx, {"type": "x"})
    ).status == "unsupported"


async def test_db_row_exists_requires_observer(tmp_path) -> None:
    ctx = await _ctx(tmp_path, {"observer": {"db_url": "postgresql://x"}})
    result = await DbRowExistsAssertion().evaluate(ctx, {"table": "users"})
    assert result.status == "unsupported"
    assert "not yet implemented" in result.message
