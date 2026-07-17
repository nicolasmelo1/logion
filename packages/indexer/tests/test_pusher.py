"""Tests for pusher: batching, presigned-PUT, partial-failure, lifecycle."""

from __future__ import annotations

import json
from collections.abc import Mapping

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.pusher import BATCH_SIZE, Pusher, RunStats
from logion_indexer.transport import FakeTransport, HttpResponse


def _make_skills(n: int) -> list[DiscoveredSkill]:
    skills: list[DiscoveredSkill] = []
    for i in range(n):
        skills.append(
            DiscoveredSkill(
                canonical=CanonicalSkillId(owner="octocat", repo=f"repo{i}"),
                title=f"Skill {i}",
                original_author="octocat",
                channels=(
                    DiscoveryChannel(
                        hub_slug="github",
                        hub_url=f"https://github.com/octocat/repo{i}",
                    ),
                ),
            )
        )
    return skills


class TestBatching:
    def test_batch_size_constant(self) -> None:
        assert BATCH_SIZE == 100

    def test_batch_under_100(self) -> None:
        transport = FakeTransport()
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/runs",
            HttpResponse(201, json.dumps({"run_id": "run-1"}).encode()),
        )
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/listings:batch-upsert",
            HttpResponse(
                200,
                json.dumps({
                    "results": [
                        {
                            "canonical": f"gh:octocat/repo{i}",
                            "status": "created",
                        }
                        for i in range(5)
                    ]
                }).encode(),
            ),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        pusher.open_run()
        result = pusher.push_batch(_make_skills(5))
        assert result.created == 5
        assert result.errors == 0

    def test_batch_over_100_splits(self) -> None:
        transport = FakeTransport()

        # Use a dynamic response that returns exactly the number of
        # items in each batch.
        class _BatchTransport(FakeTransport):
            def post(self, url, *, json_body=None, headers=None):  # noqa: ARG002
                self._call_log.append(f"POST {url}")
                if "batch-upsert" in url and json_body is not None:
                    items = json_body.get("items", [])
                    return HttpResponse(
                        200,
                        json.dumps({
                            "results": [
                                {"status": "created"}
                                for _ in range(len(items))
                            ]
                        }).encode(),
                    )
                if url in self._post_responses:
                    return self._post_responses[url]
                return HttpResponse(404, b'{"error":"not found"}')

        transport = _BatchTransport()
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/runs",
            HttpResponse(201, json.dumps({"run_id": "run-1"}).encode()),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        result = pusher.push_batch(_make_skills(150))
        assert result.created == 150
        # Should have made 2 POST calls (100 + 50).
        posts = [
            c
            for c in transport.call_log
            if "batch-upsert" in c and c.startswith("POST")
        ]
        assert len(posts) == 2


class TestPartialFailure:
    def test_partial_failure_accounting(self) -> None:
        transport = FakeTransport()
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/listings:batch-upsert",
            HttpResponse(
                200,
                json.dumps({
                    "results": [
                        {"status": "created"},
                        {"status": "error", "message": "bad"},
                        {"status": "created"},
                    ]
                }).encode(),
            ),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        result = pusher.push_batch(_make_skills(3))
        assert result.created == 2
        assert result.errors == 1

    def test_http_error_counts_all(self) -> None:
        transport = FakeTransport()
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/listings:batch-upsert",
            HttpResponse(500, b'{"error":"server"}'),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        result = pusher.push_batch(_make_skills(3))
        assert result.errors == 3


class TestRunLifecycle:
    def test_open_and_close(self) -> None:
        class _CapturingPatchTransport(FakeTransport):
            def __init__(self) -> None:
                super().__init__()
                self.patched: list[dict[str, object]] = []

            def patch(
                self,
                url: str,
                *,
                json_body: Mapping[str, object] | None = None,
                headers: Mapping[str, str] | None = None,
            ) -> HttpResponse:
                if json_body is not None:
                    self.patched.append(dict(json_body))
                return super().patch(url, json_body=json_body, headers=headers)

        transport = _CapturingPatchTransport()
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/runs",
            HttpResponse(201, json.dumps({"run_id": "run-1"}).encode()),
        )
        transport.set_patch_response(
            "https://api.logion.sh/v1/admin/indexing/runs/run-1/completion",
            HttpResponse(200, b"{}"),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        run_id = pusher.open_run()
        assert run_id == "run-1"
        stats = RunStats(created=5, updated=3)
        pusher.close_run(stats)
        patches = [c for c in transport.call_log if c.startswith("PATCH")]
        assert len(patches) == 1
        assert transport.patched == [
            {
                "stats": {
                    "created": 5,
                    "updated": 3,
                    "skipped": 0,
                    "errors": 0,
                    "partial": False,
                }
            }
        ]


class TestPresignedPut:
    def test_presigned_put_flow(self) -> None:
        transport = FakeTransport()
        # Step 1: request presigned URL.
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/listings/listing-1/bundle-upload",
            HttpResponse(
                200,
                json.dumps({
                    "presigned_url": "https://s3.example.com/put-here"
                }).encode(),
            ),
        )
        # Step 2: PUT to presigned URL.
        transport.set_put_response(
            "https://s3.example.com/put-here",
            HttpResponse(200, b""),
        )
        # Step 3: completion.
        transport.set_patch_response(
            "https://api.logion.sh/v1/admin/indexing/listings/listing-1/bundle-upload/complete",
            HttpResponse(200, b"{}"),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        success = pusher.upload_bundle(
            "listing-1", b"bundle-bytes", "sha256:abc"
        )
        assert success is True
        puts = [c for c in transport.call_log if c.startswith("PUT")]
        assert len(puts) == 1


class TestApiKeyRedaction:
    def test_api_key_never_logged(self) -> None:
        """The API key must never appear in transport call logs."""
        transport = FakeTransport(
            github_token="ghp_secret_token",
            api_key="sk-secret-api-key",
        )
        transport.set_post_response(
            "https://api.logion.sh/v1/admin/indexing/runs",
            HttpResponse(201, json.dumps({"run_id": "r1"}).encode()),
        )
        pusher = Pusher(transport, "https://api.logion.sh")
        pusher.open_run()
        for log_entry in transport.call_log:
            assert "sk-secret-api-key" not in log_entry
            assert "ghp_secret_token" not in log_entry
