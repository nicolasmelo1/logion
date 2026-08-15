#!/usr/bin/env python3
"""Seed plugin-shaped indexed listings for the dsh scenario.

Publishes two entries: one acquirable plugin, and one whose advertised
digest does not match any content, so the scenario can prove acquisition
fails closed on a digest mismatch instead of installing anyway.
"""

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

#: Fixture Git revisions, not credentials.
COMMIT = "0123456789abcdef0123456789abcdef01234567"  # pragma: allowlist secret
POISONED_COMMIT = (
    "fedcba9876543210fedcba9876543210fedcba98"  # pragma: allowlist secret
)

#: A well-formed digest that matches no artifact anywhere. Acquisition
#: must refuse it rather than install whatever it actually receives.
POISONED_DIGEST = "de" * 32

CANONICAL = "gh:logion-fixtures/dsh-plugin"
POISONED_CANONICAL = "gh:logion-fixtures/dsh-plugin-poisoned"


def _item(canonical: str, title: str, commit: str) -> dict[str, Any]:
    return {
        "canonical": canonical,
        "canonical_uri": canonical,
        "resource_type": "plugin",
        "title": title,
        "summary": "A small plugin for repository work.",
        "original_author": "logion-fixtures",
        "license_spdx": "MIT",
        "source_commit": commit,
        "tags": ["dsh", "repository"],
        "channels": [],
        "declared_capabilities": {
            "tools": ["@deepseek-ai/dsh-tools"],
            "patch": "./cordis.patch.yml",
        },
    }


def _upsert(api: base.Api, item: dict[str, Any]) -> str:
    payload = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    results = payload.get("results") or []
    errors = [entry for entry in results if entry.get("error")]
    if errors:
        raise SystemExit(f"plugin fixture upsert failed: {errors}")
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
    return str(listing_id)


def main() -> int:
    keys = base._role_keys()
    api = base.Api(
        os.environ.get("PG_API_BASE_URL", "http://localhost:8000"), keys
    )

    item = _item(CANONICAL, "Repository helper plugin", COMMIT)
    listing_id = _upsert(api, item)
    bundle_digest = base._upload_bundle(api, listing_id)
    # Re-upsert after the mirrored bundle exists so the version receives
    # the immutable revision and native distributions are registered.
    item["bundle"] = {"sha256": bundle_digest, "size_bytes": 1}
    _upsert(api, item)

    poisoned = _item(
        POISONED_CANONICAL, "Poisoned helper plugin", POISONED_COMMIT
    )
    poisoned["bundle"] = {"sha256": POISONED_DIGEST, "size_bytes": 1}
    _upsert(api, poisoned)
    poisoned_resource = base._find_resource(api, POISONED_CANONICAL)
    if poisoned_resource is None:
        raise SystemExit("poisoned fixture did not produce a resource")

    sys.stdout.write(
        json.dumps(
            {
                "listing_id": listing_id,
                "canonical": CANONICAL,
                "poisoned_resource_id": str(poisoned_resource["id"]),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
