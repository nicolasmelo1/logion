#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate committed logion.sh URLs against known public paths.

Both hosts are in scope. ``www`` is the canonical production host and the apex
redirects to it, so the same paths are reachable through either — and a typo
behind ``www.`` is exactly as broken as one behind the apex. Matching only the
apex would have left every URL the app now emits unchecked.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS_FILE = ROOT / "scripts" / "logion_sh_public_paths.txt"

URL_RE = re.compile(
    r"https://(?:www\.)?logion\.sh"
    r"(?P<path>/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?"
)

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "__pycache__",
    # Proving-ground run output. Gitignored, not ours to audit, and its
    # agent workspaces contain dangling symlinks that crash the walk.
    ".runs",
    # Mutation fixtures: deliberately broken repositories.
    ".software-factory",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
}
PLANNING_DIRS = {"plans", "future-roadmap"}


def load_public_paths() -> tuple[set[str], tuple[str, ...]]:
    exact: set[str] = set()
    wildcard: list[str] = []
    for raw in PUBLIC_PATHS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith("*"):
            wildcard.append(line[:-1])
        else:
            exact.add(line)
    return exact, tuple(wildcard)


def repo_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.relative_to(ROOT).parts[0] in PLANNING_DIRS:
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            files.append(path)
    return sorted(files)


def normalize_path(raw: str | None) -> str:
    path = raw or "/"
    path = path.rstrip(").,;\"'*")
    path = path.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return "/"
    return path.rstrip("/") or "/"


def is_allowed(path: str, exact: set[str], wildcard: tuple[str, ...]) -> bool:
    return path in exact or any(path.startswith(prefix) for prefix in wildcard)


def main() -> int:
    exact, wildcard = load_public_paths()
    failures: list[tuple[str, str]] = []
    for file_path in repo_files():
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = file_path.relative_to(ROOT).as_posix()
        for match in URL_RE.finditer(content):
            if match.group(0).endswith("/..."):
                continue
            path = normalize_path(match.group("path"))
            if not is_allowed(path, exact, wildcard):
                failures.append((rel, match.group(0)))

    if not failures:
        sys.stdout.write("check_logion_sh_urls: ok.\n")
        return 0

    sys.stdout.write(
        "check_logion_sh_urls: unknown logion.sh URLs detected:\n"
    )
    for rel, url in failures:
        sys.stdout.write(f"  {rel}: {url}\n")
    sys.stdout.write(
        "\nUse an existing public route or add the route to "
        "scripts/logion_sh_public_paths.txt with the landing route.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
