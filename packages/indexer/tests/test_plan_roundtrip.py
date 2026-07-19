"""Tests for crawl --out / push --plan: full items pushed verbatim."""

from __future__ import annotations

import json
from collections.abc import Mapping

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.dedup import DedupPlan
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.pusher import Pusher
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://api.logion.sh"


def _full_skill() -> DiscoveredSkill:
    return DiscoveredSkill(
        canonical=CanonicalSkillId(
            owner="octocat", repo="hello", subpath="skills/foo"
        ),
        title="foo",
        summary="A foo skill",
        original_author="octocat",
        license_spdx="MIT",
        source_commit="abc123",
        tags=("coding",),
        channels=(
            DiscoveryChannel(
                hub_slug="clawhub",
                hub_url="https://clawhub.ai/skills/octocat/hello",
                hub_verified=True,
            ),
        ),
        inferred_map={
            "version": 1,
            "package": {"slug": "foo"},
            "components": {
                "capabilities": {"foo": {"entrypoint": "skills/foo/SKILL.md"}},
                "runtime": {"include": ["skills/foo/**"]},
            },
        },
        map_flags=("skillmap_frontmatter_missing",),
        bundle={"sha256": "sha256:deadbeef", "size_bytes": 42},
    )


class _CapturingTransport(FakeTransport):
    def __init__(self) -> None:
        super().__init__()
        self.posted: list[dict] = []

    def post(
        self,
        url: str,
        *,
        json_body: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,  # noqa: ARG002
    ) -> HttpResponse:
        self._call_log.append(f"POST {url}")
        if json_body is not None and "batch-upsert" in url:
            self.posted.append(dict(json_body))
            items = json_body.get("items", [])
            return HttpResponse(
                200,
                json.dumps({
                    "results": [
                        {
                            "canonical": it["canonical"],
                            "status": "created",
                            "id": "listing-1",
                        }
                        for it in items
                    ]
                }).encode(),
            )
        if url in self._post_responses:
            return self._post_responses[url]
        return HttpResponse(404, b'{"error":"not found"}')


class TestPlanRoundTrip:
    def test_plan_carries_full_items(self) -> None:
        plan = DedupPlan(create=[_full_skill()])
        reloaded = json.loads(json.dumps(plan.to_dict()))
        assert len(reloaded["create"]) == 1
        item = reloaded["create"][0]
        # No degenerate rebuild: real title, real channel, real map, bundle.
        assert item["title"] == "foo"
        assert item["channels"][0]["hub_slug"] == "clawhub"
        assert item["channels"][0]["hub_slug"] != "plan"
        assert item["inferred_map"] is not None
        assert item["bundle"] == {
            "sha256": "sha256:deadbeef",
            "size_bytes": 42,
        }

    def test_push_serialized_verbatim(self) -> None:
        plan = DedupPlan(create=[_full_skill()])
        reloaded = json.loads(json.dumps(plan.to_dict()))
        transport = _CapturingTransport()
        pusher = Pusher(transport, BASE)
        result = pusher.push_serialized(reloaded["create"], run_id="run-1")
        assert result.created == 1
        # The exact serialized item was posted, unmodified.
        assert transport.posted[0]["items"] == reloaded["create"]
        assert result.listing_ids["gh:octocat/hello#skills/foo"] == "listing-1"
