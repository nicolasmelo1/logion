#!/usr/bin/env python3
"""Seed the resource version the instrument scenario instruments.

There is no create-a-resource endpoint: a ResourceVersion only exists as a
projection of an indexed listing, and a listing only earns one once it has
*both* a pinned ``source_commit`` and a mirrored bundle digest. So the
listing is upserted, given a bundle, then re-upserted with its commit —
the same order ``seed_acquisition_fixture.py`` uses.

Everything goes through the public/admin HTTP API; this script never opens
the database. Emits the resource id, version id, title, and publisher
identity as one JSON line for the scenario's capture mechanism.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tarfile
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from agent_proving_ground._json import (
    JsonObject,
    JsonValue,
    collection,
    require_str,
)

#: Pinned so re-seeding reuses the same fixture instead of accumulating
#: near-duplicate versions the scenario could not tell apart.
LISTING_CANONICAL = "gh:nicolasmelo1/logion-fixtures#publisher-review-skill"
# pragma: allowlist nextline secret
LISTING_COMMIT = "9f1c0a4d0f5b4a7c8e2d1b3a6c5e4d7f8a9b0c1d"
SKILL_NAME = "publisher-review-skill"
RESOURCE_TITLE = "Publisher Review Skill"

#: The bundle upload URL is presigned for this content type.
BUNDLE_CONTENT_TYPE = "application/gzip"

SKILL_MD = (
    "---\n"
    f"name: {SKILL_NAME}\n"
    "description: Review a diff and report correctness risks first.\n"
    "license: MIT\n"
    "---\n\n"
    "# Publisher review skill\n\n"
    "Read the diff, then report correctness risks before style.\n"
).encode()


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
        body: JsonObject | None = None,
    ) -> tuple[int, JsonValue]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": f"Bearer {self._keys['admin']}"}
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
        body: JsonObject | None = None,
    ) -> JsonValue:
        status, payload = self.request(method, path, body=body)
        if status not in (200, 201):
            raise SystemExit(
                f"{method} {path} failed: HTTP {status}: {payload}"
            )
        return payload


def _skill_bundle() -> bytes:
    """A minimal, byte-stable Agent Skill bundle.

    Every timestamp and ownership field is pinned so re-running the seed
    produces the identical digest; a drifting digest would look like a new
    version on every run.
    """
    raw = BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
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
    compressed = BytesIO()
    with gzip.GzipFile(
        fileobj=compressed, mode="wb", compresslevel=9, mtime=0
    ) as gz:
        gz.write(raw.getvalue())
    return compressed.getvalue()


def _upsert_listing(api: Api, *, with_commit: bool) -> str:
    item: JsonObject = {
        "canonical": LISTING_CANONICAL,
        "title": RESOURCE_TITLE,
        "summary": "Review skill a publisher instruments for Logion.",
        "original_author": "logion-fixtures",
        "license_spdx": "MIT",
        "tags": ["review"],
        "channels": [],
    }
    if with_commit:
        item["source_commit"] = LISTING_COMMIT
    payload = api.expect(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        body={"items": [item]},
    )
    results = collection(payload, "results") or collection(payload)
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("error"):
            raise SystemExit(f"batch-upsert rejected the item: {entry}")
        listing_id = entry.get("indexed_listing_id") or entry.get("listing_id")
        if listing_id:
            return str(listing_id)
    raise SystemExit(f"batch-upsert returned no listing id: {payload}")


def _upload_bundle(api: Api, listing_id: str) -> None:
    bundle = _skill_bundle()
    digest = hashlib.sha256(bundle).hexdigest()
    # The digest is declared up front so the API can sign it into the PUT
    # URL; completion reads it back from the object's metadata.
    session = api.expect(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload",
        body={"checksum_sha256": digest},
    )
    if not isinstance(session, dict):
        raise SystemExit(f"bundle-upload returned no session: {session}")
    put = urllib.request.Request(
        require_str(session, "put_url"),
        data=bundle,
        # Both headers are covered by the signature the API minted from the
        # declared digest; sending anything else is rejected as unsigned.
        headers={
            "Content-Type": BUNDLE_CONTENT_TYPE,
            "x-amz-meta-sha256": digest,
        },
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
    api.expect(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload/completion",
        body={
            "bundle_key": require_str(session, "bundle_key"),
            "sha256": digest,
            "size_bytes": len(bundle),
        },
    )


def _find_resource(api: Api) -> JsonObject:
    cursor: str | None = None
    while True:
        suffix = f"&cursor={cursor}" if cursor else ""
        page = api.expect("GET", f"/v1/resources?limit=100{suffix}")
        for entry in collection(page):
            if not isinstance(entry, dict):
                continue
            if entry.get("canonical_uri") == LISTING_CANONICAL:
                return entry
        cursor = page.get("next_cursor") if isinstance(page, dict) else None
        if not cursor:
            raise SystemExit(
                f"no resource projected for {LISTING_CANONICAL!r}; the "
                "listing upsert did not produce one"
            )


def _single_version(api: Api, resource_id: str) -> JsonObject:
    """Return the fixture's only version, or explain why there isn't one.

    `logion instrument` resolves a resource and picks a version, so a
    resource with zero versions makes the phase unrunnable and one with
    several makes the choice ambiguous.
    """
    versions = api.expect(
        "GET", f"/v1/resources/{resource_id}/versions?limit=50"
    )
    items = [v for v in collection(versions) if isinstance(v, dict)]
    if not items:
        raise SystemExit(
            f"resource {resource_id} has no versions: an indexed listing "
            "only earns one once it has both a pinned source_commit and a "
            "mirrored bundle digest"
        )
    if len(items) > 1:
        raise SystemExit(
            f"fixture resource has {len(items)} versions; instrument cannot "
            "pick one. Reset the dev database (`make dev-reset` in the "
            "workspace repo) and seed again."
        )
    return items[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=False)
    parser.add_argument("--logion-home", required=False)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)

    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    api = Api(args.base_url, _role_keys())

    listing_id = _upsert_listing(api, with_commit=False)
    _upload_bundle(api, listing_id)
    _upsert_listing(api, with_commit=True)

    resource = _find_resource(api)
    resource_id = require_str(resource, "id")
    version = _single_version(api, resource_id)
    version_id = str(version.get("id") or version.get("version_id") or "")

    (evidence / "resource-seed.json").write_text(
        json.dumps({"resource": resource, "version": version}, indent=2),
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({
            "resource_id": resource_id,
            "version_id": version_id,
            "resource_title": RESOURCE_TITLE,
            "publisher_identity": "did:web:logion-fixtures",
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
