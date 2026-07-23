#!/usr/bin/env python3
"""Verify integrity of pinned upstream protocol specifications."""

# ruff: noqa: T201

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "protocol-specs"
LOCK = SPEC_ROOT / "UPSTREAM.lock.json"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:  # noqa: C901
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected: set[Path] = set()

    if data.get("schema_version") != 1:
        errors.append("unsupported protocol-spec lock schema")

    for source in data.get("sources", []):
        name = source.get("name", "<unnamed>")
        commit = source.get("commit", "")
        if not COMMIT.fullmatch(commit):
            errors.append(f"{name}: commit must be a full lowercase Git SHA")
        if not source.get("repository", "").startswith("https://github.com/"):
            errors.append(f"{name}: repository must be an HTTPS GitHub URL")
        if not source.get("license"):
            errors.append(f"{name}: license is required")

        for item in source.get("files", []):
            relative = Path(item["path"])
            expected.add(relative)
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"{name}: unsafe path {relative}")
                continue
            digest = item.get("sha256", "")
            if not SHA256.fullmatch(digest):
                errors.append(f"{name}: invalid SHA-256 for {relative}")
                continue
            target = SPEC_ROOT / relative
            if not target.is_file():
                errors.append(f"missing pinned protocol file: {relative}")
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest:
                errors.append(
                    f"hash mismatch: {relative} (expected {digest}, got {actual})"
                )

    actual = {
        path.relative_to(SPEC_ROOT)
        for path in (SPEC_ROOT / "upstream").rglob("*")
        if path.is_file()
    }
    for relative in sorted(actual - expected):
        errors.append(f"unlocked upstream protocol file: {relative}")
    for relative in sorted(expected - actual):
        if (SPEC_ROOT / relative).is_file():
            errors.append(f"locked file is outside upstream/: {relative}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"protocol specs verified ({len(expected)} pinned files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
