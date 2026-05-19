"""Handlers for ``courses capabilities`` sub-commands."""

from __future__ import annotations

import argparse
import json
import sys

from cli._course_capabilities import (
    CapabilityManifestError,
    load_and_validate_capability_manifest,
    summarize_capability_manifest,
)
from cli.commands.courses._capability_render import (
    _append_summary_fields,
)


def handle_courses_capabilities_validate(
    args: argparse.Namespace,
) -> int:
    """Validate a local capability manifest and print a summary."""
    try:
        manifest = load_and_validate_capability_manifest(args.bundle_dir)
    except CapabilityManifestError as exc:
        print(f"Invalid capability manifest: {exc}", file=sys.stderr)
        return 2
    summary = summarize_capability_manifest(manifest)
    lines = ["capabilities_status: declared"]
    _append_summary_fields(lines, summary)
    print("\n".join(lines))
    return 0


def handle_courses_capabilities_print(
    args: argparse.Namespace,
) -> int:
    """Validate a local capability manifest and print normalised JSON."""
    try:
        manifest = load_and_validate_capability_manifest(args.bundle_dir)
    except CapabilityManifestError as exc:
        print(f"Invalid capability manifest: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0
