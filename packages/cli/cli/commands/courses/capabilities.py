"""Handlers for ``courses capabilities`` sub-commands."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from cli._course_capabilities import (
    CAPABILITY_MANIFEST_PATH,
    CapabilityManifestError,
    load_and_validate_capability_manifest,
    summarize_capability_manifest,
)
from cli.commands.courses._capability_render import (
    _append_summary_fields,
)

CAPABILITIES_TEMPLATE_FILENAME = "course_capabilities.template.yaml"


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


def _template_text() -> str:
    """Return the bundled capability manifest scaffold contents."""
    return (
        resources
        .files("cli.templates")
        .joinpath(CAPABILITIES_TEMPLATE_FILENAME)
        .read_text(encoding="utf-8")
    )


def handle_courses_capabilities_scaffold(
    args: argparse.Namespace,
) -> int:
    """Emit the capability manifest scaffold.

    With ``--bundle-dir`` the scaffold is written to
    ``<bundle-dir>/course/capabilities.yaml`` (refuses to overwrite an
    existing file unless ``--force`` is passed).  Without ``--bundle-dir``
    the scaffold is printed to stdout so the agent can pipe it.
    """
    text = _template_text()
    bundle_dir: Path | None = getattr(args, "bundle_dir", None)
    if bundle_dir is None:
        print(text, end="")
        return 0
    dest = bundle_dir / CAPABILITY_MANIFEST_PATH
    if dest.exists() and not args.force:
        print(
            f"Refusing to overwrite existing manifest: {dest} "
            "(pass --force to replace)",
            file=sys.stderr,
        )
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write the already-loaded text directly.  ``resources.files()``
    # returns a Traversable that may not have a stable on-disk path
    # (e.g. zip-installed wheels), so do not round-trip through
    # ``Path(str(...))`` just to call shutil.copyfile.
    dest.write_text(text, encoding="utf-8")
    print(f"Wrote scaffold to {dest}")
    return 0
