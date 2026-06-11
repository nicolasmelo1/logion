# SPDX-License-Identifier: MIT
"""Project public repository docs into the installable CLI package."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = (
    REPO_ROOT / "docs" / "marketplace",
    REPO_ROOT / "docs" / "legal",
)
TARGET_DIR = REPO_ROOT / "packages" / "cli" / "cli" / "docs"
GENERATED_NOTICE = """# Generated CLI documentation

The Markdown files in this package are generated from `docs/marketplace/` and
`docs/legal/` by `packages/cli/scripts/sync_docs.py`. Edit the source files,
then run `uv run python packages/cli/scripts/sync_docs.py`.
"""


def source_files() -> dict[str, Path]:
    """Return public article names and their canonical source paths."""
    result: dict[str, Path] = {}
    for source_dir in SOURCE_DIRS:
        for path in sorted(source_dir.glob("*.md")):
            if path.name in result:
                raise ValueError(
                    f"duplicate documentation filename: {path.name}"
                )
            result[path.name] = path
    return result


def check() -> int:
    """Return non-zero when the package projection differs from the source."""
    expected = source_files()
    projected = {
        path.name: path
        for path in TARGET_DIR.glob("*.md")
        if path.name != "README.md"
    }
    drift = sorted(set(expected) ^ set(projected))
    drift.extend(
        name
        for name in sorted(set(expected) & set(projected))
        if expected[name].read_bytes() != projected[name].read_bytes()
    )
    if drift:
        print("CLI documentation projection is stale:", file=sys.stderr)
        for name in drift:
            print(f"  {name}", file=sys.stderr)
        return 1
    return 0


def sync() -> int:
    """Replace the package projection with canonical repository docs."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for path in TARGET_DIR.glob("*.md"):
        path.unlink()
    for name, source in source_files().items():
        shutil.copyfile(source, TARGET_DIR / name)
    (TARGET_DIR / "README.md").write_text(GENERATED_NOTICE, encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return check() if args.check else sync()


if __name__ == "__main__":
    raise SystemExit(main())
