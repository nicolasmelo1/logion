from __future__ import annotations

from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)


async def test_course_exists_honors_captured_course_id(monkeypatch) -> None:
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore({"seller": {"api_key": "redacted"}}),
    )

    async def fake_courses(_role: str | None) -> list[dict[str, str]]:
        return [{"id": "older-course", "status": "published"}]

    monkeypatch.setattr(queries, "_my_courses", fake_courses)
    result = await queries.query(
        {
            "type": "course_exists",
            "owner_agent": "creator",
            "course": "run-course",
        },
        {"creator": "seller"},
    )

    assert result["found"] is False
    assert result["evidence"] == {"source": "api"}
