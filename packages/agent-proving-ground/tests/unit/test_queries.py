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


async def test_setup_token_pending_requires_exact_prefix(monkeypatch) -> None:
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore({"seller": {"api_key": "redacted"}}),
    )

    async def fake_get(path: str, _role: str | None):
        assert path == "/v1/setup-tokens/run-prefix"
        return 200, {"token_prefix": "other-prefix", "status": "pending"}

    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "setup_token_pending",
            "owner_agent": "creator",
            "token_prefix": "run-prefix",
        },
        {"creator": "seller"},
    )

    assert result["pending"] is False
    assert result["token_prefix"] == "other-prefix"
