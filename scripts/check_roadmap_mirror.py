#!/usr/bin/env python3
"""Verify or update hashes for the public planning projection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "roadmap-sync-manifest.json"
MIRROR_DIRS = ("plans", "future-roadmap")
NOTICE = "<!-- Generated from Logion's canonical planning source."


def files() -> list[Path]:
    return sorted(
        path.relative_to(ROOT)
        for directory in MIRROR_DIRS
        for path in (ROOT / directory).glob("*.md")
        if path.is_file()
    )


def sha(path: Path) -> str:
    value = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    return "-".join(value[index : index + 8] for index in range(0, 64, 8))


def update() -> None:
    previous = (
        json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    )
    data = {
        "schema_version": 1,
        "source_revision": previous.get("source_revision", "public-proposal"),
        "files": [{"path": str(path), "sha256": sha(path)} for path in files()],
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def check() -> int:
    if not MANIFEST.exists():
        print("roadmap mirror manifest is missing")
        return 1
    data = json.loads(MANIFEST.read_text())
    expected = {Path(item["path"]): item["sha256"] for item in data["files"]}
    actual = set(files())
    errors: list[str] = []
    for path in sorted(actual):
        if not (ROOT / path).read_text().startswith(NOTICE):
            errors.append(f"missing generated notice: {path}")
        if path not in expected:
            errors.append(f"not in manifest: {path}")
        elif sha(path) != expected[path]:
            errors.append(f"hash mismatch: {path}")
    for path in sorted(set(expected) - actual):
        errors.append(f"manifest file missing: {path}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"roadmap mirror verified ({len(actual)} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    if args.update:
        update()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
