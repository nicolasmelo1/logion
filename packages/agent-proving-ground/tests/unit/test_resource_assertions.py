from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent_proving_ground.assertions.api import (
    ResourceBackfillAppliedAssertion,
    ResourceBackfillCompleteAssertion,
    ResourceBackfillIdempotentAssertion,
    ResourceIdentityUniqueAssertion,
    ResourceProjectionExistsAssertion,
    ResourceSearchReturnsKindsAssertion,
)
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


class StaticQueryApi:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.last_query: dict[str, Any] | None = None

    async def query(
        self, _world: World, query: dict[str, Any]
    ) -> dict[str, Any]:
        self.last_query = query
        return self.result


def _context(tmp_path: Path, api: StaticQueryApi) -> AssertionContext:
    return AssertionContext(
        scenario_name="resource_projection_backfill",
        phase_id="verify",
        world=World(
            run_id="run",
            base_url="http://example.test",
            root_dir=tmp_path,
        ),
        api=api,  # type: ignore[arg-type]
        artifacts_dir=tmp_path,
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


@pytest.mark.parametrize(
    ("assertion", "result", "expected_status"),
    [
        (ResourceBackfillCompleteAssertion(), {"found": True}, "passed"),
        (ResourceBackfillCompleteAssertion(), {"found": False}, "failed"),
        (ResourceBackfillAppliedAssertion(), {"found": True}, "passed"),
        (ResourceBackfillAppliedAssertion(), {"found": False}, "failed"),
        (ResourceIdentityUniqueAssertion(), {"found": True}, "passed"),
        (ResourceIdentityUniqueAssertion(), {"found": False}, "failed"),
        (ResourceProjectionExistsAssertion(), {"found": True}, "passed"),
        (ResourceProjectionExistsAssertion(), {"found": False}, "failed"),
        (ResourceBackfillIdempotentAssertion(), {"found": True}, "passed"),
        (ResourceBackfillIdempotentAssertion(), {"found": False}, "failed"),
        (
            ResourceSearchReturnsKindsAssertion(),
            {
                "kinds_match": True,
                "projection_kinds": ["indexed_listing", "published_course"],
                "matched_canonicals": [
                    "gh:resource-projection/python-debugging-skill"
                ],
            },
            "passed",
        ),
        (
            ResourceSearchReturnsKindsAssertion(),
            {"kinds_match": False},
            "failed",
        ),
    ],
)
async def test_resource_assertions_have_explicit_pass_and_fail_paths(
    tmp_path: Path,
    assertion: Any,
    result: dict[str, Any],
    expected_status: str,
) -> None:
    api = StaticQueryApi(result)

    outcome = await assertion.evaluate(
        _context(tmp_path, api), {"marker": "value"}
    )

    assert outcome.status == expected_status
    assert api.last_query == {
        "type": assertion.query_type,
        "marker": "value",
    }


@pytest.mark.parametrize(
    "assertion",
    [
        ResourceBackfillCompleteAssertion(),
        ResourceBackfillAppliedAssertion(),
        ResourceIdentityUniqueAssertion(),
        ResourceProjectionExistsAssertion(),
        ResourceBackfillIdempotentAssertion(),
        ResourceSearchReturnsKindsAssertion(),
    ],
)
async def test_resource_assertions_fail_closed_on_result_contract_drift(
    tmp_path: Path, assertion: Any
) -> None:
    outcome = await assertion.evaluate(
        _context(tmp_path, StaticQueryApi({})), {}
    )

    assert outcome.status == "failed"


async def test_resource_search_assertion_preserves_matched_fixture_evidence(
    tmp_path: Path,
) -> None:
    api = StaticQueryApi({
        "kinds_match": True,
        "projection_kinds": ["indexed_listing", "published_course"],
        "matched_canonicals": [
            "gh:resource-projection/python-debugging-skill"
        ],
        "evidence": {
            "matched_projection_kinds": [
                "indexed_listing",
                "published_course",
            ],
            "matched_canonicals": [
                "gh:resource-projection/python-debugging-skill"
            ],
        },
    })

    outcome = await ResourceSearchReturnsKindsAssertion().evaluate(
        _context(tmp_path, api), {}
    )

    assert outcome.status == "passed"
    assert outcome.evidence["projection_kinds"] == [
        "indexed_listing",
        "published_course",
    ]
    assert outcome.evidence["matched_canonicals"] == [
        "gh:resource-projection/python-debugging-skill"
    ]
    assert outcome.evidence["query_evidence"]["matched_projection_kinds"] == [
        "indexed_listing",
        "published_course",
    ]
