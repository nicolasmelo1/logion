# SPDX-License-Identifier: MIT
"""``course-reviews download`` — fetch the bundle under review.

Calls ``GET /v1/course-reviews/{id}/bundle`` directly via httpx (the
endpoint returns presigned URLs; the typed SDK doesn't ship a wrapper
for it yet), downloads each file streamed, and reconstructs the
bundle's directory tree under TARGET so the reviewer can read SKILL.md
and references before approve/reject.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from cli._config import resolve_config_from_args
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit


def handle_download(args: argparse.Namespace) -> int:
    """Execute course-reviews download — fetch bundle for review."""
    bad_id = validate_uuid_id(args.review_id, "REVIEW_ID")
    if bad_id is not None:
        return bad_id

    config = resolve_config_from_args(args)
    target = Path(
        args.target if args.target else f"./review-bundles/{args.review_id}"
    ).resolve()
    target.mkdir(parents=True, exist_ok=True)

    url = (
        f"{config.base_url.rstrip('/')}/v1/course-reviews/"
        f"{args.review_id}/bundle"
    )
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        with httpx.Client(timeout=config.timeout) as http:
            payload = _fetch_bundle_payload(http, url, headers)
            if payload is None:
                return 1
            files = payload.get("files", [])
            if not files:
                print_err("Error: review has no assets")
                return 1
            rc = _download_files(http, files, target)
            if rc != 0:
                return rc
    except Exception as exc:
        return handle_error(exc)

    _emit_result(payload, files, target, json_output=config.json_output)
    return 0


def _fetch_bundle_payload(
    http: httpx.Client, url: str, headers: dict
) -> dict | None:
    resp = http.get(url, headers=headers)
    if resp.status_code != 200:
        print_err(
            f"Error: bundle request failed: "
            f"HTTP {resp.status_code} — {resp.text[:200]}"
        )
        return None
    return resp.json()


def _download_files(
    http: httpx.Client, files: list[dict], target: Path
) -> int:
    for f in files:
        filename = f["filename"]
        dest = target / filename
        if not dest.resolve().is_relative_to(target):
            print_err(f"Error: refusing path escape: {filename}")
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        with http.stream("GET", f["download_url"]) as r:
            r.raise_for_status()
            with open(dest, "wb") as out:
                for chunk in r.iter_bytes():
                    out.write(chunk)
    return 0


def _emit_result(
    payload: dict, files: list[dict], target: Path, *, json_output: bool
) -> None:
    if json_output:
        emit(
            {
                "review_id": payload["review_id"],
                "target": str(target),
                "files": [f["filename"] for f in files],
            },
            json_output=True,
        )
        return
    sys.stdout.write(f"Downloaded {len(files)} file(s) to {target}\n")
    for f in files:
        sys.stdout.write(f"  {f['filename']}\n")
    sys.stdout.write(
        "\nNext: read SKILL.md and references/* before approve/reject.\n"
    )
