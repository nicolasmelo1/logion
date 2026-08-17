from __future__ import annotations

from unittest.mock import Mock

import pytest

from agent_proving_ground._json import JsonObject, JsonValue
from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
from agent_proving_ground.api_adapters.mock import MockApiAdapter

GetResponse = tuple[int, JsonValue]


def _queries() -> LogionApiQueries:
    return LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore({"admin": {"api_key": "redacted"}}),
    )


async def test_paged_get_collects_all_supported_pages(monkeypatch) -> None:
    queries = _queries()

    async def fake_get(path: str, _role: str | None) -> GetResponse:
        if path == "/v1/resources?limit=50":
            return 200, {"items": [{"id": "r1"}], "next_cursor": "next"}
        if path == "/v1/resources?limit=50&cursor=next":
            return 200, {"items": [{"id": "r2"}], "next_cursor": None}
        raise AssertionError(path)

    monkeypatch.setattr(queries, "_get", fake_get)
    status, rows = await queries._paged_get("/v1/resources", "admin")

    assert status == 200
    assert rows == [{"id": "r1"}, {"id": "r2"}]


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": []},
        {"items": "not-a-list"},
        {"items": ["not-an-object"]},
        {"items": [], "next_cursor": 123},
    ],
)
async def test_paged_get_rejects_collection_contract_drift(
    monkeypatch, payload: JsonValue
) -> None:
    queries = _queries()

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, payload

    monkeypatch.setattr(queries, "_get", fake_get)
    status, _rows = await queries._paged_get("/v1/resources", "admin")

    assert status == 0


async def test_paged_get_rejects_page_cap_instead_of_truncating(
    monkeypatch,
) -> None:
    queries = _queries()
    calls = 0

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        nonlocal calls
        calls += 1
        return 200, {"items": [], "next_cursor": f"cursor-{calls}"}

    monkeypatch.setattr(queries, "_get", fake_get)
    status, rows = await queries._paged_get("/v1/resources", "admin")

    assert status == 0
    assert rows == []
    assert calls == 1000


@pytest.mark.parametrize(
    ("projection_kind", "detail", "expected", "unsupported"),
    [
        (
            "published_course",
            {"projections": [{"projection_kind": "published_course"}]},
            True,
            False,
        ),
        (
            "published_course",
            {"projections": [{"projection_kind": "indexed_listing"}]},
            False,
            False,
        ),
        ("published_course", {"projections": "invalid"}, False, True),
    ],
)
async def test_resource_projection_exists_pass_fail_and_contract_drift(
    monkeypatch,
    projection_kind: str,
    detail: JsonObject,
    expected: bool,
    unsupported: bool,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        _path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        return 200, [{"id": "resource-1"}]

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, detail

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "resource_projection_exists",
            "projection_kind": projection_kind,
        },
        {},
    )

    assert result["found"] is expected
    assert result.get("unsupported", False) is unsupported


async def test_resource_backfill_complete_passes_and_stops_detail_reads(
    monkeypatch,
) -> None:
    queries = _queries()
    detail_paths: list[str] = []

    async def fake_paged_get(
        path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        assert _limit == 50
        if path.startswith("/v1/listings"):
            return 200, [{"id": "listing-1"}]
        return 200, [{"id": "resource-1"}, {"id": "resource-unused"}]

    async def fake_get(path: str, _role: str | None) -> GetResponse:
        detail_paths.append(path)
        return 200, {
            "projections": [
                {
                    "projection_kind": "indexed_listing",
                    "projection_id": "listing-1",
                }
            ]
        }

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query({"type": "resource_backfill_complete"}, {})

    assert result["found"] is True
    assert detail_paths == ["/v1/resources/resource-1"]
    assert result["evidence"]["missing_listing_ids"] == []


async def test_resource_backfill_complete_fails_when_projection_is_missing(
    monkeypatch,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        if path.startswith("/v1/listings"):
            return 200, [{"id": "listing-1"}, {"id": "listing-2"}]
        return 200, [{"id": "resource-1"}]

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, {
            "projections": [
                {
                    "projection_kind": "indexed_listing",
                    "projection_id": "listing-1",
                }
            ]
        }

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query({"type": "resource_backfill_complete"}, {})

    assert result["found"] is False
    assert result["evidence"]["missing_listing_ids"] == ["listing-2"]


async def test_resource_backfill_complete_rejects_invalid_detail_shape(
    monkeypatch,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        if path.startswith("/v1/listings"):
            return 200, [{"id": "listing-1"}]
        return 200, [{"id": "resource-1"}]

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, {"projections": "invalid"}

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query({"type": "resource_backfill_complete"}, {})

    assert result["unsupported"] is True
    assert "invalid projections" in result["reason"]


@pytest.mark.parametrize(
    ("items", "expected", "unsupported"),
    [
        (
            [
                {"resource_type": "agent_skill", "canonical_uri": "gh:o/one"},
                {"resource_type": "course", "canonical_uri": "course:one"},
            ],
            True,
            False,
        ),
        (
            [
                {"resource_type": "agent_skill", "canonical_uri": "gh:o/one"},
                {"resource_type": "agent_skill", "canonical_uri": "gh:o/one"},
            ],
            False,
            False,
        ),
        ([{"resource_type": "agent_skill"}], False, True),
    ],
)
async def test_resource_identity_unique_pass_fail_and_contract_drift(
    monkeypatch,
    items: list[JsonObject],
    expected: bool,
    unsupported: bool,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        _path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        return 200, items

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    result = await queries.query({"type": "resource_identity_unique"}, {})

    assert result["found"] is expected
    assert result.get("unsupported", False) is unsupported


@pytest.mark.parametrize(
    ("overrides", "expected", "unsupported"),
    [
        ({}, True, False),
        ({"rerun_created": 1}, False, False),
        ({"after_identity_snapshot": "different"}, False, False),
        (
            {
                "before_identity_snapshot": "[]",
                "after_identity_snapshot": "[]",
            },
            False,
            False,
        ),
        ({"rerun_created": "invalid"}, False, False),
    ],
)
async def test_resource_backfill_idempotent_passes_and_fails_strictly(
    overrides: JsonObject, expected: bool, unsupported: bool
) -> None:
    queries = _queries()
    params: JsonObject = {
        "type": "resource_backfill_idempotent",
        "rerun_created": 0,
        "rerun_linked": 0,
        "before_identity_snapshot": '[{"canonical_uri":"gh:o/one"}]',
        "after_identity_snapshot": '[{"canonical_uri":"gh:o/one"}]',
    }
    params.update(overrides)

    result = await queries.query(params, {})

    assert result["found"] is expected
    assert result.get("unsupported", False) is unsupported


async def test_resource_backfill_idempotent_rejects_missing_capture() -> None:
    result = await _queries().query(
        {
            "type": "resource_backfill_idempotent",
            "rerun_created": 0,
            "rerun_linked": 0,
        },
        {},
    )

    assert result["unsupported"] is True
    assert "identity_snapshot" in result["reason"]


@pytest.mark.parametrize(
    ("overrides", "expected", "unsupported"),
    [
        ({}, True, False),
        ({"resources_created": 0}, False, False),
        ({"projections_linked": 1}, False, False),
        ({"identity_snapshot": ""}, False, False),
        ({"identity_snapshot": "[]"}, False, False),
        ({"identity_snapshot": "{}"}, False, False),
        ({"identity_snapshot": "null"}, False, False),
        ({"identity_snapshot": "None"}, False, False),
        ({"resources_created": "invalid"}, False, False),
    ],
)
async def test_resource_backfill_applied_requires_clean_transition(
    overrides: JsonObject, expected: bool, unsupported: bool
) -> None:
    queries = _queries()
    params: JsonObject = {
        "type": "resource_backfill_applied",
        "resources_created": 2,
        "projections_linked": 2,
        "identity_snapshot": "stable-snapshot",
    }
    params.update(overrides)

    result = await queries.query(params, {})

    assert result["found"] is expected
    assert result.get("unsupported", False) is unsupported


async def test_resource_backfill_applied_rejects_missing_capture() -> None:
    result = await _queries().query(
        {
            "type": "resource_backfill_applied",
            "resources_created": 2,
        },
        {},
    )

    assert result["unsupported"] is True
    assert "missing keys" in result["reason"]


@pytest.mark.parametrize("snapshot", ["", "[]", "{}", "null", "None"])
async def test_mock_resource_backfill_applied_rejects_empty_snapshots(
    snapshot: str,
) -> None:
    result = await MockApiAdapter().query(
        Mock(),
        {
            "type": "resource_backfill_applied",
            "resources_created": 2,
            "projections_linked": 2,
            "identity_snapshot": snapshot,
        },
    )

    assert result["found"] is False


async def test_resource_search_matches_fixture_canonical_and_both_projections(
    monkeypatch,
) -> None:
    queries = _queries()
    detail_paths: list[str] = []
    observed_roles: list[str | None] = []

    async def fake_paged_get(
        _path: str, role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        observed_roles.append(role)
        return 200, [
            {"id": "skill"},
            {"id": "course"},
            {"id": "unused"},
        ]

    details = {
        "/v1/resources/skill": {
            "canonical_uri": "gh:resource-projection/python-debugging-skill",
            "projections": [{"projection_kind": "indexed_listing"}],
        },
        "/v1/resources/course": {
            "canonical_uri": "course:python-debugging",
            "projections": [{"projection_kind": "published_course"}],
        },
    }

    async def fake_get(path: str, role: str | None) -> GetResponse:
        detail_paths.append(path)
        observed_roles.append(role)
        return 200, details[path]

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "resource_search_returns_kinds",
            "projection_kinds": ["indexed_listing", "published_course"],
            "canonicals": [
                "gh:resource-projection/python-debugging-skill",
                "course:python-debugging",
            ],
            "observer_agent": "consumer",
        },
        {"consumer": "buyer"},
    )

    assert result["kinds_match"] is True
    assert result["projection_kinds"] == [
        "indexed_listing",
        "published_course",
    ]
    assert result["matched_canonicals"] == [
        "course:python-debugging",
        "gh:resource-projection/python-debugging-skill",
    ]
    assert detail_paths == ["/v1/resources/skill", "/v1/resources/course"]
    assert observed_roles == ["buyer", "buyer", "buyer"]


async def test_resource_search_fails_when_fixture_projection_is_missing(
    monkeypatch,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        _path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        return 200, [{"id": "skill"}]

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, {
            "canonical_uri": "gh:resource-projection/python-debugging-skill",
            "projections": [{"projection_kind": "indexed_listing"}],
        }

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "resource_search_returns_kinds",
            "projection_kinds": ["indexed_listing", "published_course"],
            "canonicals": [
                "gh:resource-projection/python-debugging-skill",
                "course:python-debugging",
            ],
        },
        {},
    )

    assert result["kinds_match"] is False
    assert result["projection_kinds"] == ["indexed_listing"]


async def test_resource_search_does_not_mix_unrelated_projection_kinds(
    monkeypatch,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        _path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        return 200, [
            {"id": "skill"},
            {"id": "expected-course"},
            {"id": "unrelated-course"},
        ]

    details = {
        "/v1/resources/skill": {
            "canonical_uri": "gh:resource-projection/python-debugging-skill",
            "projections": [{"projection_kind": "indexed_listing"}],
        },
        "/v1/resources/expected-course": {
            "canonical_uri": "course:python-debugging",
            "projections": [{"projection_kind": "indexed_listing"}],
        },
        "/v1/resources/unrelated-course": {
            "canonical_uri": "course:unrelated",
            "projections": [{"projection_kind": "published_course"}],
        },
    }

    async def fake_get(path: str, _role: str | None) -> GetResponse:
        return 200, details[path]

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)

    result = await queries.query(
        {
            "type": "resource_search_returns_kinds",
            "projection_kinds": ["indexed_listing", "published_course"],
            "canonicals": [
                "gh:resource-projection/python-debugging-skill",
                "course:python-debugging",
            ],
        },
        {},
    )

    assert result["kinds_match"] is False
    assert result["matched_canonicals"] == [
        "gh:resource-projection/python-debugging-skill"
    ]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"projection_kinds": "indexed_listing"},
        {"projection_kinds": []},
        {"projection_kinds": [123]},
        {"projection_kinds": ["indexed_listing"], "canonicals": "gh:o/r"},
        {
            "projection_kinds": ["indexed_listing", "published_course"],
            "canonicals": ["gh:o/r"],
        },
    ],
)
async def test_resource_search_rejects_invalid_expectation_shapes(
    params: JsonObject,
) -> None:
    result = await _queries().query(
        {"type": "resource_search_returns_kinds", **params}, {}
    )

    assert result["unsupported"] is True
    assert "invalid shape" in result["reason"]


async def test_resource_search_rejects_invalid_projection_shape(
    monkeypatch,
) -> None:
    queries = _queries()

    async def fake_paged_get(
        _path: str, _role: str | None, *, _limit: int = 50
    ) -> tuple[int, list[JsonObject]]:
        return 200, [{"id": "skill"}]

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 200, {
            "canonical_uri": "gh:resource-projection/python-debugging-skill",
            "projections": ["invalid"],
        }

    monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "resource_search_returns_kinds",
            "projection_kinds": ["indexed_listing"],
            "canonicals": ["gh:resource-projection/python-debugging-skill"],
        },
        {},
    )

    assert result["unsupported"] is True
    assert "invalid projections" in result["reason"]
