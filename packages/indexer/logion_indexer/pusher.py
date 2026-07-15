"""Pusher: batch-upsert client against the Logion admin API.

Batching ≤100 items per call, presigned PUT flow for bundles,
partial-failure accounting.  Run lifecycle: open → push → close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import DiscoveredSkill
from .transport import Transport

if TYPE_CHECKING:
    from collections.abc import Sequence

BATCH_SIZE = 100


@dataclass
class PushResult:
    """Result of pushing a batch of items."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list[dict] = field(default_factory=list)


@dataclass
class RunStats:
    """Aggregate statistics for a full indexing run."""

    discovered: int = 0
    resolved: int = 0
    deduped: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    partial: bool = False


class Pusher:
    """Batch-upsert client for the Logion admin ingestion API.

    All HTTP goes through :class:`Transport` so tests can fake it.
    API keys are never logged — the transport redacts Authorization
    headers in error output.
    """

    def __init__(
        self,
        transport: Transport,
        base_url: str = "https://api.logion.sh",
    ) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self._run_id: str | None = None

    def open_run(self) -> str:
        """Open an ingestion audit run, return the run ID."""
        url = f"{self.base_url}/v1/admin/indexing/runs"
        resp = self.transport.post(url, json_body={})
        if resp.status not in (200, 201):
            raise RuntimeError(f"failed to open run: HTTP {resp.status}")
        data = resp.json()
        run_id = data.get("run_id", "") if isinstance(data, dict) else ""
        self._run_id = run_id
        return run_id

    def close_run(self, stats: RunStats) -> None:
        """Close the ingestion run with stats."""
        if not self._run_id:
            return
        url = (
            f"{self.base_url}/v1/admin/indexing/runs/{self._run_id}/completion"
        )
        resp = self.transport.patch(
            url,
            json_body={
                "created": stats.created,
                "updated": stats.updated,
                "skipped": stats.skipped,
                "errors": stats.errors,
                "partial": stats.partial,
            },
        )
        if resp.status not in (200, 204):
            raise RuntimeError(f"failed to close run: HTTP {resp.status}")

    def push_batch(
        self,
        items: Sequence[DiscoveredSkill],
        run_id: str | None = None,
    ) -> PushResult:
        """Push a batch of discovered skills to the batch-upsert endpoint.

        Batches are capped at ``BATCH_SIZE`` (100) items per call.
        """
        rid = run_id or self._run_id or ""
        url = f"{self.base_url}/v1/admin/indexing/listings:batch-upsert"
        result = PushResult()

        for i in range(0, len(items), BATCH_SIZE):
            chunk = items[i : i + BATCH_SIZE]
            payload = {
                "run_id": rid,
                "items": [_serialize_item(item) for item in chunk],
            }
            resp = self.transport.post(url, json_body=payload)
            if resp.status not in (200, 201):
                result.errors += len(chunk)
                result.error_details.append({
                    "status": resp.status,
                    "body": resp.text[:500],
                })
                continue

            data = resp.json()
            if not isinstance(data, dict):
                continue
            results = data.get("results") or []
            if not isinstance(results, list):
                continue
            for item_result in results:
                if not isinstance(item_result, dict):
                    continue
                status = item_result.get("status", "")
                if status == "created":
                    result.created += 1
                elif status == "updated":
                    result.updated += 1
                elif status == "skipped":
                    result.skipped += 1
                elif status == "error":
                    result.errors += 1
                    result.error_details.append(item_result)

        return result

    def upload_bundle(
        self,
        listing_id: str,
        bundle_bytes: bytes,
        sha256: str,
    ) -> bool:
        """Upload a mirrored bundle via the presigned PUT flow.

        1. Request a presigned URL from the API.
        2. PUT the bytes to the presigned URL.
        3. Report completion to the API.
        """
        # Step 1: request presigned URL.
        url = (
            f"{self.base_url}/v1/admin/indexing/listings/{listing_id}"
            f"/bundle-upload"
        )
        resp = self.transport.post(
            url,
            json_body={"sha256": sha256, "size_bytes": len(bundle_bytes)},
        )
        if resp.status not in (200, 201):
            return False
        data = resp.json()
        if not isinstance(data, dict):
            return False
        presigned_url = data.get("presigned_url", "")
        if not presigned_url:
            return False

        # Step 2: PUT bytes to presigned URL.
        put_resp = self.transport.put(
            presigned_url,
            body=bundle_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        if put_resp.status not in (200, 204):
            return False

        # Step 3: report completion.
        complete_url = (
            f"{self.base_url}/v1/admin/indexing/listings/{listing_id}"
            f"/bundle-upload/complete"
        )
        complete_resp = self.transport.patch(
            complete_url,
            json_body={"sha256": sha256, "size_bytes": len(bundle_bytes)},
        )
        return complete_resp.status in (200, 204)


def _serialize_item(item: DiscoveredSkill) -> dict:
    """Serialize a DiscoveredSkill for the batch-upsert payload."""
    return {
        "canonical": str(item.canonical),
        "title": item.title,
        "summary": item.summary,
        "original_author": item.original_author,
        "license_spdx": item.license_spdx,
        "source_commit": item.source_commit,
        "tags": list(item.tags),
        "channels": [
            {
                "hub_slug": ch.hub_slug,
                "hub_url": ch.hub_url,
                "hub_verified": ch.hub_verified,
            }
            for ch in item.channels
        ],
        "inferred_map": item.inferred_map,
        "map_flags": list(item.map_flags),
        "bundle": None,
    }


def serialize_item(item: DiscoveredSkill) -> dict:
    """Public wrapper for test access."""
    return _serialize_item(item)
