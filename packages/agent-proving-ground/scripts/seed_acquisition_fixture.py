#!/usr/bin/env python3
"""Seed the catalog fixtures the native-acquisition scenario acquires.

The scenario needs two resources that no dev seed creates:

* an indexed skill whose version carries an ``npx_skills`` distribution, so
  Logion can delegate acquisition to the upstream package manager;
* a Logion-hosted Course bundle, so the hosted download path is exercised.

Both are created through the public/admin HTTP API only — this script never
opens the database. An indexed listing earns a native distribution only once
it has *both* a pinned ``source_commit`` and a mirrored bundle digest, so the
listing is upserted, given a bundle, then re-upserted with its commit.

Usage: seed_acquisition_fixture.py [--base-url URL]
Emits one JSON line describing what the scenario can acquire.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

#: Pinned so re-running the seed reuses the same fixtures instead of
#: accumulating near-duplicates the reconciler would call ambiguous.
LISTING_CANONICAL = "gh:logion-fixtures/code-review-skill"
LISTING_COMMIT = "b" * 40
SKILL_NAME = "code-review"

#: The bundle upload URL is presigned for this content type.
BUNDLE_CONTENT_TYPE = "application/gzip"


def _role_keys() -> dict[str, str]:
    path = os.environ.get("LOGION_PROVING_GROUND_ROLE_KEYS_FILE")
    if not path:
        raise SystemExit(
            "LOGION_PROVING_GROUND_ROLE_KEYS_FILE is required so the seed "
            "uses the same role credentials as the scenario"
        )
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    keys: dict[str, str] = {}
    for role, value in raw.items():
        if isinstance(value, str):
            keys[role] = value
        elif isinstance(value, dict) and value.get("api_key"):
            keys[role] = str(value["api_key"])
    return keys


class Api:
    def __init__(self, base_url: str, keys: dict[str, str]) -> None:
        self._base = base_url.rstrip("/")
        self._keys = keys

    def request(
        self,
        method: str,
        path: str,
        *,
        role: str = "admin",
        body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": f"Bearer {self._keys[role]}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"detail": raw.decode(errors="replace")}

    def expect(
        self,
        method: str,
        path: str,
        *,
        role: str = "admin",
        body: dict[str, Any] | None = None,
        ok: tuple[int, ...] = (200, 201),
    ) -> Any:
        status, payload = self.request(method, path, role=role, body=body)
        if status not in ok:
            raise SystemExit(
                f"{method} {path} failed: HTTP {status}: {payload}"
            )
        return payload


SKILL_MD = (
    "---\n"
    f"name: {SKILL_NAME}\n"
    "description: Lightweight code review checklist.\n"
    "license: MIT\n"
    "---\n\n"
    "# Code review\n\n"
    "Read the diff, then report correctness risks first.\n"
).encode()


def _skill_bundle() -> bytes:
    """A minimal, byte-stable Agent Skill bundle.

    Every timestamp and ownership field is pinned so re-running the seed
    produces the identical digest; a drifting digest would make the
    fixture look like a new version on every run.
    """
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=9) as archive:
        for name, payload in (
            (f"{SKILL_NAME}/SKILL.md", SKILL_MD),
            (f"{SKILL_NAME}/LICENSE", b"MIT\n"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, BytesIO(payload))
    return buffer.getvalue()


def _upsert_listing(api: Api, *, with_commit: bool) -> str:
    item: dict[str, Any] = {
        "canonical": LISTING_CANONICAL,
        "title": "Code Review Skill",
        "summary": "Lightweight code-review capability for coding agents.",
        "original_author": "logion-fixtures",
        "license_spdx": "MIT",
        "tags": ["code-review", "quality"],
        "channels": [],
    }
    if with_commit:
        item["source_commit"] = LISTING_COMMIT
    payload = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    results = payload.get("results") or payload.get("items") or []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("error"):
            raise SystemExit(f"batch-upsert rejected the item: {entry}")
        listing_id = entry.get("indexed_listing_id") or entry.get("listing_id")
        if listing_id:
            return str(listing_id)
    listings = api.expect("GET", "/v1/listings?limit=50&include_indexed=true")
    items = (
        listings if isinstance(listings, list) else listings.get("items", [])
    )
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if entry.get("canonical_url") == LISTING_CANONICAL:
            return str(entry.get("listing_id") or entry["id"])
    raise SystemExit(f"batch-upsert returned no listing id: {payload}")


def _upload_bundle(api: Api, listing_id: str) -> str:
    bundle = _skill_bundle()
    digest = hashlib.sha256(bundle).hexdigest()
    session = api.expect(
        "POST", f"/v1/admin/indexing/listings/{listing_id}/bundle-upload"
    )
    # The URL is signed for this exact content type; sending anything else
    # makes object storage reject the signature.
    put = urllib.request.Request(
        session["put_url"],
        data=bundle,
        # Only the content type is signed, so no other header may be sent:
        # object storage rejects the whole request as an unsigned header.
        headers={"Content-Type": BUNDLE_CONTENT_TYPE},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(put) as response:
            if response.status not in (200, 204):
                raise SystemExit(f"bundle PUT failed: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise SystemExit(
            f"bundle PUT failed: HTTP {exc.code}: {detail}"
        ) from exc
    status, payload = api.request(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload/completion",
        body={
            "bundle_key": session["bundle_key"],
            "sha256": digest,
            "size_bytes": len(bundle),
        },
    )
    if status not in (200, 201):
        detail = str(payload)
        if "sha256 metadata" in detail:
            raise SystemExit(
                "indexed bundle upload cannot be completed: the presigned "
                "PUT URL is signed for content-type only, so the uploaded "
                "object carries no sha256 metadata, but completion requires "
                "it. The upload session has to accept the digest and sign "
                "it in (the course upload session already does this via "
                "`checksum_sha256`). Until then no indexed listing can get "
                "a mirrored bundle, and therefore no npx_skills "
                f"distribution. Server said: {detail}"
            )
        raise SystemExit(f"bundle completion failed: HTTP {status}: {detail}")
    return digest


def _find_resource(api: Api, canonical: str) -> dict[str, Any] | None:
    cursor: str | None = None
    while True:
        suffix = f"&cursor={cursor}" if cursor else ""
        page = api.expect("GET", f"/v1/resources?limit=100{suffix}")
        items = page if isinstance(page, list) else page.get("items", [])
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if entry.get("canonical_uri") == canonical:
                return entry
        cursor = page.get("next_cursor") if isinstance(page, dict) else None
        if not cursor:
            return None


def _acquirable(api: Api, resource: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first version whose acquisition plan actually resolves."""
    versions = api.expect(
        "GET", f"/v1/resources/{resource['id']}/versions?limit=50"
    )
    items = (
        versions if isinstance(versions, list) else versions.get("items", [])
    )
    for version in items:
        version_id = version.get("id") or version.get("version_id")
        if not version_id:
            continue
        status, plan = api.request(
            "GET",
            f"/v1/resources/{resource['id']}/versions/{version_id}"
            "/acquisition-plan?channel=auto",
        )
        if status == 200 and isinstance(plan, dict):
            return {
                "resource_id": str(resource["id"]),
                "version_id": str(version_id),
                "channel": plan.get("selected_channel"),
                "content_digest": plan.get("content_digest"),
            }
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args(argv)
    api = Api(args.base_url, _role_keys())

    listing_id = _upsert_listing(api, with_commit=False)
    _upload_bundle(api, listing_id)
    # The second upsert is what earns the native distributions: the dual
    # write only registers them once the listing has both a mirrored bundle
    # digest and a pinned commit.
    _upsert_listing(api, with_commit=True)

    resource = _find_resource(api, LISTING_CANONICAL)
    if resource is None:
        raise SystemExit(
            f"indexed listing {LISTING_CANONICAL} did not project a resource"
        )
    indexed = _acquirable(api, resource)
    if indexed is None:
        raise SystemExit(
            "indexed resource has no resolvable acquisition plan; the "
            "listing dual-write did not register a native distribution"
        )

    sys.stdout.write(
        json.dumps(
            {
                "indexed_resource_id": indexed["resource_id"],
                "indexed_version_id": indexed["version_id"],
                "indexed_channel": indexed["channel"],
                "indexed_canonical": LISTING_CANONICAL,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
