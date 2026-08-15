"""Pusher: batch-upsert client against the Logion admin API.

Batching ≤100 items per call, presigned PUT flow for bundles,
partial-failure accounting.  Run lifecycle: open → push → close.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import DiscoveredResource, DiscoveredSkill
from .transport import HttpResponse, Transport

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
    # Maps canonical id string -> listing id, for follow-up bundle upload.
    listing_ids: dict[str, str] = field(default_factory=dict)


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
    The transport stores method+URL in call_log for debugging.
    """

    def __init__(
        self,
        transport: Transport,
        base_url: str = "https://api.logion.sh",
    ) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.transport.set_api_base_url(base_url)
        self._run_id: str | None = None

    def open_run(self) -> str:
        """Open an ingestion audit run, return the run ID."""
        url = f"{self.base_url}/v1/admin/indexing/runs"
        resp = self.transport.post(url, json_body={})
        if resp.status not in (200, 201):
            raise RuntimeError(f"failed to open run: HTTP {resp.status}")
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            raise RuntimeError("invalid JSON response from server") from None
        run_id = data.get("run_id", "") if isinstance(data, dict) else ""
        if not run_id:
            raise RuntimeError("open_run: response did not contain a run_id")
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
                "stats": {
                    "created": stats.created,
                    "updated": stats.updated,
                    "skipped": stats.skipped,
                    "errors": stats.errors,
                    "partial": stats.partial,
                }
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
        return self.push_serialized(
            [
                _serialize_resource_item(item)
                if isinstance(item, DiscoveredResource)
                else _serialize_item(item)
                for item in items
            ],
            run_id=run_id,
        )

    def push_serialized(
        self,
        items: Sequence[dict],
        run_id: str | None = None,
    ) -> PushResult:
        """Push already-serialized batch items verbatim.

        This is the failure-resume path: a plan file carries the full
        serialized items and is pushed here without rebuilding them.
        """
        rid = run_id or self._run_id or ""
        url = f"{self.base_url}/v1/admin/indexing/listings:batch-upsert"
        result = PushResult()

        for i in range(0, len(items), BATCH_SIZE):
            chunk = items[i : i + BATCH_SIZE]
            payload = {"run_id": rid, "items": list(chunk)}
            resp = self.transport.post(url, json_body=payload)
            self._absorb_response(resp, len(chunk), result)

        return result

    def _absorb_response(
        self, resp: HttpResponse, chunk_len: int, result: PushResult
    ) -> None:
        """Fold one batch-upsert HTTP response into *result*."""
        results = _parse_batch_results(resp)
        if results is None:
            result.errors += chunk_len
            result.error_details.append({
                "status": resp.status,
                "body": resp.text[:500],
            })
            return
        for item_result in results:
            if not isinstance(item_result, dict):
                continue
            canonical = item_result.get("canonical", "")
            listing_id = item_result.get("id") or item_result.get("listing_id")
            if canonical and listing_id:
                result.listing_ids[str(canonical)] = str(listing_id)
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
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            return False
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


def _parse_batch_results(resp: HttpResponse) -> list | None:
    """Return the ``results`` list, or None on any malformed response."""
    if resp.status not in (200, 201):
        return None
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("results") or []
    if not isinstance(results, list):
        return None
    return results


def _serialize_item(item: DiscoveredSkill) -> dict:
    """Serialize a DiscoveredSkill for the batch-upsert payload."""
    return {
        "canonical": str(item.canonical),
        "resource_id": f"skill:{item.canonical}",
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
                "metadata": ch.metadata,
            }
            for ch in item.channels
        ],
        "inferred_map": item.inferred_map,
        "map_flags": list(item.map_flags),
        "bundle": item.bundle,
    }


def serialize_item(item: DiscoveredSkill) -> dict:
    """Public wrapper for test access."""
    return _serialize_item(item)


def _serialize_resource_item(item: DiscoveredResource) -> dict:
    """Serialize a DiscoveredResource for the batch-upsert payload."""
    result = _serialize_skill_from_resource(item)
    result["resource_type"] = item.resource_type
    result["canonical_uri"] = item.canonical_uri
    result["resource_id"] = str(item.canonical)
    return result


def _serialize_skill_from_resource(item: DiscoveredResource) -> dict:
    """Serialize the skill-compatible fields of a DiscoveredResource.

    This produces the same keys as :func:`_serialize_item` so the
    pusher can accept both types.  The ``resource_type`` and
    ``canonical_uri`` fields are added by the caller when the
    full resource serialization is needed.
    """
    return {
        "canonical": item.canonical_uri,
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
                "metadata": ch.metadata,
            }
            for ch in item.channels
        ],
        "inferred_map": item.inferred_map,
        "map_flags": list(item.map_flags),
        "bundle": item.bundle,
    }


def serialize_resource_item(item: DiscoveredResource) -> dict:
    """Public wrapper for test access."""
    return _serialize_resource_item(item)
