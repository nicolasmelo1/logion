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
import gzip
import hashlib
import json
import os
import sys
import tarfile
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

#: Pinned so re-running the seed reuses the same fixtures instead of
#: accumulating near-duplicates the reconciler would call ambiguous.
#: A real upstream repository at a real commit: the native leg delegates to
#: the actual `npx skills` CLI, which resolves this against GitHub. A
#: fictional source would make the phase unrunnable.
LISTING_CANONICAL = "gh:vercel-labs/skills#find-skills"
# pragma: allowlist nextline secret
LISTING_COMMIT = "c6f69c631292444cc541ac6d91e2226b0ff247da"
SKILL_NAME = "find-skills"
COURSE_SLUG = "acquisition-hosted-code-review"

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
    # gzip stamps the current time into its header unless told otherwise,
    # which would give every seed run a different digest and therefore a
    # new resource version — leaving the reconciler with several
    # indistinguishable candidates for one installation.
    compressed = BytesIO()
    with gzip.GzipFile(
        fileobj=compressed, mode="wb", compresslevel=9, mtime=0
    ) as gz:
        gz.write(raw.getvalue())
    return compressed.getvalue()


def _upsert_listing(api: Api, *, with_commit: bool) -> str:
    item: dict[str, Any] = {
        "canonical": LISTING_CANONICAL,
        "title": "Find Skills (upstream)",
        "summary": "Upstream skill-discovery helper, installed by npx skills.",
        "original_author": "logion-fixtures",
        "license_spdx": "MIT",
        "tags": ["discovery", "upstream"],
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
    # The digest is declared up front so the API can sign it into the PUT
    # URL; completion reads it back from the object's metadata.
    session = api.expect(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload",
        body={"checksum_sha256": digest},
    )
    # The URL is signed for this exact content type; sending anything else
    # makes object storage reject the signature.
    put = urllib.request.Request(
        session["put_url"],
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


#: A free course: the hosted-bundle rollout starts with free bundles, and a
#: paid one answers `resource_entitlement_required` instead of a plan.
COURSE_FILES: tuple[tuple[str, str, bytes], ...] = (
    (
        "SKILL.md",
        "text/markdown",
        b"---\nname: hosted-code-review\nlicense: MIT\n---\n"
        b"# Hosted code review\n\nReview a diff and report risks first.\n",
    ),
    ("LICENSE", "text/plain", b"MIT\n"),
    (
        "course/capabilities.yaml",
        "application/yaml",
        b"version: 1\nsummary: Hosted code review fixture\n",
    ),
    (".bundle-manifest", "application/json", b'{"schema_version":"1"}\n'),
)


def _bundle_digest() -> str:
    """Stable per bundle content, so a re-seed reuses its own course."""
    return hashlib.sha256(_skill_bundle()).hexdigest()


def _existing_course(api: Api) -> dict[str, Any] | None:
    """The newest fixture course, if one is already usable.

    A course published before the projection wiring existed is published
    but not acquirable, and re-approving it is not possible. Rather than
    demanding a database reset, the seed leaves it alone and creates a
    fresh one — an unacquirable leftover is inert, since each course keys
    its own resource and cannot make another one ambiguous.
    """
    payload = api.expect("GET", "/v1/courses/mine?limit=50", role="seller")
    candidates = [
        course
        for course in payload.get("courses", [])
        if isinstance(course, dict)
        and str(course.get("slug", "")).startswith(COURSE_SLUG)
    ]
    for course in candidates:
        if course.get("status") != "published":
            return course
        resource = _find_resource(api, f"course:{course['id']}")
        if resource is not None and _acquirable(api, resource) is not None:
            return course
    return None


def _upload_course_assets(api: Api, course_id: str) -> str:
    specs = []
    for name, content_type, body in COURSE_FILES:
        specs.append({
            "filename": name,
            "content_type": content_type,
            "size_bytes": len(body),
            "checksum_sha256": hashlib.sha256(body).hexdigest(),
        })
    session = api.expect(
        "POST",
        f"/v1/courses/{course_id}/versions",
        role="seller",
        body={"files": specs},
    )
    version_id = str(session["version_id"])
    by_name = {name: (ctype, body) for name, ctype, body in COURSE_FILES}
    for upload in session["uploads"]:
        content_type, body = by_name[upload["filename"]]
        put = urllib.request.Request(
            upload["put_url"],
            data=body,
            headers={
                "Content-Type": content_type,
                "x-amz-meta-checksum-sha256": hashlib.sha256(body).hexdigest(),
            },
            method="PUT",
        )
        with urllib.request.urlopen(put) as response:
            if response.status not in (200, 204):
                raise SystemExit(
                    f"course asset PUT failed for {upload['filename']}"
                )
    api.expect(
        "PATCH",
        f"/v1/courses/{course_id}/versions/{version_id}/upload-session",
        role="seller",
        body={},
    )
    return version_id


def _await(
    api: Api, path: str, *, role: str, check, what: str, tries: int = 60
) -> dict[str, Any]:
    for _ in range(tries):
        status, payload = api.request("GET", path, role=role)
        if status == 200 and check(payload):
            return payload
        time.sleep(1)
    raise SystemExit(f"timed out waiting for {what}")


def _publish_course(api: Api) -> str:
    """Create and publish a free hosted Course, returning its course id."""
    course = _existing_course(api)
    if course is None:
        course = _create_course(api)
    course_id = str(course["id"])
    if course.get("status") == "published":
        return course_id
    _publish_existing(api, course_id)
    return course_id


def _create_course(api: Api) -> dict[str, Any]:
    """Create the fixture course, stepping aside from a stale namesake."""
    # The digest-derived slug lets a re-seed reuse its own course. A
    # leftover published-but-unacquirable course from an older backend
    # holds that slug, so the seed steps around it rather than failing.
    for attempt in range(8):
        suffix = "" if attempt == 0 else f"-{attempt}"
        status, body = api.request(
            "POST",
            "/v1/courses",
            role="seller",
            body={
                "title": "Hosted Code Review",
                "slug": f"{COURSE_SLUG}-{_bundle_digest()[:8]}{suffix}",
                "short_summary": "Hosted code-review capability fixture.",
                "description": "Deterministic hosted-bundle fixture.",
                "visibility": "private",
                "price_cents": 0,
                "currency": "USD",
                "tags": ["code-review"],
            },
        )
        if status in (200, 201):
            return body
        if "slug already exists" not in str(body):
            raise SystemExit(f"cannot create fixture course: {body}")
    raise SystemExit("every fixture course slug is taken; reset the dev DB")


def _publish_existing(api: Api, course_id: str) -> None:
    version_id = _upload_course_assets(api, course_id)
    _await(
        api,
        f"/v1/courses/{course_id}/versions/{version_id}",
        role="seller",
        check=lambda v: v.get("status") in {"ready", "validated"},
        what="course version to become ready",
    )
    review = api.expect(
        "POST",
        f"/v1/courses/{course_id}/publication-reviews",
        role="seller",
        body={"version_id": version_id},
    )
    review_id = str(review["id"])
    _await(
        api,
        f"/v1/course-reviews/{review_id}",
        role="admin",
        check=lambda r: r.get("review_status") == "human_review",
        what="publication review to reach human_review",
    )
    api.expect(
        "PATCH",
        f"/v1/course-reviews/{review_id}/approval",
        role="admin",
        body={"acknowledge_capability_mismatches": True},
    )
    api.expect(
        "PATCH",
        f"/v1/courses/{course_id}",
        role="seller",
        body={"visibility": "public"},
    )


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


def _require_single_version(api: Api, resource: dict[str, Any]) -> None:
    """Refuse to seed a fixture the reconciler cannot attribute.

    Several versions of one resource at the same upstream revision are
    genuinely indistinguishable, so reconcile reports `ambiguous` and the
    scenario can never pass. That is correct behaviour, not a bug to work
    around — the fixture has to be clean instead.
    """
    versions = api.expect(
        "GET", f"/v1/resources/{resource['id']}/versions?limit=50"
    )
    items = (
        versions if isinstance(versions, list) else versions.get("items", [])
    )
    if len(items) > 1:
        raise SystemExit(
            f"fixture resource {resource.get('canonical_uri')} has "
            f"{len(items)} versions; reconcile cannot attribute an install "
            "to one of them. Reset the dev database "
            "(`make dev-reset` in the workspace repo) and seed again."
        )


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
    _require_single_version(api, resource)
    indexed = _acquirable(api, resource)
    if indexed is None:
        raise SystemExit(
            "indexed resource has no resolvable acquisition plan; the "
            "listing dual-write did not register a native distribution"
        )

    course_id = _publish_course(api)
    hosted_resource = _find_resource(api, f"course:{course_id}")
    if hosted_resource is None:
        raise SystemExit(
            f"published course {course_id} did not project a resource; "
            "publication is not registering resource projections"
        )
    hosted = _acquirable(api, hosted_resource)
    if hosted is None:
        raise SystemExit(
            f"published course {course_id} has no resolvable acquisition "
            "plan; publication did not register a logion_bundle "
            "distribution"
        )

    sys.stdout.write(
        json.dumps(
            {
                "indexed_resource_id": indexed["resource_id"],
                "indexed_version_id": indexed["version_id"],
                "indexed_channel": indexed["channel"],
                "indexed_canonical": LISTING_CANONICAL,
                "hosted_resource_id": hosted["resource_id"],
                "hosted_version_id": hosted["version_id"],
                "hosted_channel": hosted["channel"],
                "hosted_course_id": course_id,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
