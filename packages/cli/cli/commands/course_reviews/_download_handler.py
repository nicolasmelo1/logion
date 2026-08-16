# SPDX-License-Identifier: MIT
"""``course-reviews download`` — fetch the bundle under review.

Fetches the bundle manifest through the typed SDK
(``client.v1.course_reviews.get_bundle``), then streams each file from
its presigned URL and reconstructs the bundle's directory tree under
TARGET so the reviewer can read SKILL.md and references before
approve/reject.

The manifest call goes through the SDK like every other API call. The
per-file downloads hit short-lived presigned object-storage URLs
(carried in the manifest), which have no SDK wrapper — those use httpx
directly and are allowlisted in ``scripts/check_cli_http.lock``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._lazy_import import LazyModule
from cli._output import emit

if TYPE_CHECKING:
    import httpx
else:
    httpx = LazyModule("httpx")


# Structural types rather than the SDK's generated models: the CLI is
# barred from importing logion.v1._types.generated (see
# scripts/check_forbidden_imports.py), and logion.v1 does not re-export
# them. These say exactly which fields this handler reads.
class BundleFile(Protocol):
    """A single downloadable file in a review bundle."""

    @property
    def filename(self) -> str: ...

    @property
    def download_url(self) -> str: ...


class ReviewBundle(Protocol):
    """The bundle manifest returned by ``get_bundle``."""

    @property
    def review_id(self) -> str: ...

    @property
    def files(self) -> list[BundleFile]: ...


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

    client = make_client(config)
    try:
        bundle = client.v1.course_reviews.get_bundle(review_id=args.review_id)
    except Exception as exc:
        return handle_error(exc)
    finally:
        client.close()

    files = bundle.files
    if not files:
        print_err("Error: review has no assets")
        return 1

    # Presigned object-storage URLs (download_url) are external and have
    # no SDK wrapper — stream them directly. See scripts/check_cli_http.lock.
    try:
        with httpx.Client(timeout=config.timeout) as http:
            rc = _download_files(http, files, target)
            if rc != 0:
                return rc
    except Exception as exc:
        return handle_error(exc)

    _emit_result(bundle, files, target, json_output=config.json_output)
    return 0


def _download_files(
    http: httpx.Client,
    files: list[BundleFile],
    target: Path,
) -> int:
    for f in files:
        filename = f.filename
        dest = target / filename
        if not dest.resolve().is_relative_to(target):
            print_err(f"Error: refusing path escape: {filename}")
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        with http.stream("GET", f.download_url) as r:
            r.raise_for_status()
            with open(dest, "wb") as out:
                for chunk in r.iter_bytes():
                    out.write(chunk)
    return 0


def _emit_result(
    bundle: ReviewBundle,
    files: list[BundleFile],
    target: Path,
    *,
    json_output: bool,
) -> None:
    if json_output:
        emit(
            {
                "review_id": bundle.review_id,
                "target": str(target),
                "files": [f.filename for f in files],
            },
            json_output=True,
        )
        return
    sys.stdout.write(f"Downloaded {len(files)} file(s) to {target}\n")
    for f in files:
        sys.stdout.write(f"  {f.filename}\n")
    sys.stdout.write(
        "\nNext: read SKILL.md and references/* before approve/reject.\n"
    )
