#!/usr/bin/env python3
"""Seed a vendor-owned DSH plugin that declares a closed remote MCP service."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agent_proving_ground._json import (
    JsonObject,
    collection,
    require_str,
)

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
import seed_acquisition_fixture as base  # noqa: E402

CANONICAL = "gh:acme-vendor/private-mcp-connector"
COMMIT = "1234567890abcdef1234567890abcdef12345678"  # pragma: allowlist secret
NPM_NAME = "@acme-vendor/private-mcp-connector"
NPM_VERSION = "1.0.0"
ENDPOINT = "http://127.0.0.1:18765/mcp"


def _item() -> JsonObject:
    return {
        "npm_distribution": {"name": NPM_NAME, "version": NPM_VERSION},
        "canonical": CANONICAL,
        "canonical_uri": CANONICAL,
        "resource_type": "plugin",
        "title": "Acme Private MCP Connector",
        "summary": "Vendor connector for an OAuth-protected remote MCP.",
        "original_author": "acme-vendor",
        "license_spdx": "MIT",
        "source_commit": COMMIT,
        "tags": ["mcp", "oauth", "remote"],
        "channels": [],
        "declared_capabilities": {
            "services": [
                {
                    "kind": "mcp",
                    "transport": "http",
                    "endpoint": ENDPOINT,
                    "authentication": "oauth2",
                }
            ],
        },
    }


def main() -> int:
    keys = base._role_keys()
    api = base.Api(
        os.environ.get("PG_API_BASE_URL", "http://localhost:8000"), keys
    )
    item = _item()
    payload = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    listing_id = next(
        require_str(entry, "indexed_listing_id")
        for entry in collection(payload, "results")
        if entry.get("indexed_listing_id")
    )
    digest = base._upload_bundle(api, listing_id)
    item["bundle"] = {"sha256": digest, "size_bytes": 1}
    api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    resource = base._find_resource(api, CANONICAL)
    if resource is None:
        raise SystemExit("remote MCP fixture did not produce a resource")
    acquired = base._acquirable(api, resource)
    if acquired is None:
        raise SystemExit("remote MCP fixture has no native distribution")
    sys.stdout.write(
        json.dumps({
            "resource_id": acquired["resource_id"],
            "version_id": acquired["version_id"],
            "canonical": CANONICAL,
            "publisher": "acme-vendor",
            "npm_name": NPM_NAME,
            "npm_version": NPM_VERSION,
            "commit": COMMIT,
            "endpoint": ENDPOINT,
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
