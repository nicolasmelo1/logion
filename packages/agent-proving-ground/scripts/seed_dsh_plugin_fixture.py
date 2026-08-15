#!/usr/bin/env python3
"""Seed one real plugin-shaped indexed listing for the dsh scenario."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SEED = (
    ROOT / "packages/agent-proving-ground/scripts/seed_acquisition_fixture.py"
)
sys.path.insert(0, str(SEED.parent))
import seed_acquisition_fixture as base  # noqa: E402


def main() -> int:
    keys = base._role_keys()
    api = base.Api(
        os.environ.get("PG_API_BASE_URL", "http://localhost:8000"), keys
    )
    commit = "0123456789abcdef0123456789abcdef01234567"
    canonical = "gh:logion-fixtures/dsh-plugin"
    item: dict[str, Any] = {
        "canonical": canonical,
        "canonical_uri": canonical,
        "resource_type": "plugin",
        "title": "Repository helper plugin",
        "summary": "A small plugin for repository work.",
        "original_author": "logion-fixtures",
        "license_spdx": "MIT",
        "source_commit": commit,
        "tags": ["dsh", "repository"],
        "channels": [],
    }
    payload = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    results = payload.get("results") or []
    listing_id = next(
        (
            entry.get("indexed_listing_id")
            for entry in results
            if entry.get("indexed_listing_id")
        ),
        None,
    )
    if not listing_id:
        raise SystemExit(f"no listing id returned: {payload}")
    bundle_digest = base._upload_bundle(api, str(listing_id))
    # Re-upsert after the mirrored bundle exists so the version receives the
    # immutable revision and native distributions are registered.
    item["bundle"] = {"sha256": bundle_digest, "size_bytes": 1}
    second = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    if any(result.get("error") for result in second.get("results") or []):
        raise SystemExit(f"plugin fixture upsert failed: {second}")
    sys.stdout.write(
        json.dumps(
            {"listing_id": listing_id, "canonical": canonical}, sort_keys=True
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
