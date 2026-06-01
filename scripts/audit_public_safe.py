#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pre-flight audit: ensure the public repo contains no forbidden strings.

Exit 0 if clean, exit 1 if any forbidden pattern is found (after printing
every offending file:line with the pattern name).

Skips:
  - tests/            (test fixtures legitimately contain patterns)
  - .git/             (VCS metadata)
  - this script itself
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if "--root" in sys.argv:
    idx = sys.argv.index("--root")
    if idx + 1 < len(sys.argv):
        ROOT = os.path.abspath(sys.argv[idx + 1])

FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    ("private repo path", re.compile(r"logion-private")),
    ("private employer domain", re.compile(r"revvadas\.com")),
    ("absolute user path", re.compile(r"/Users/\w+/|/home/\w+/|C:\\Users\\\\")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub PAT", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("Slack token", re.compile(r"xox[bsap]-[A-Za-z0-9-]{10,}")),
    (
        "private key",
        re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    ("OpenAI / Anthropic-style key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("hardcoded password", re.compile(r"""password\s*=\s*["'][^"']""")),
    # Internal-planning vocabulary. Capitalized "Phase" / "Phases" is the
    # milestone-numbering form used in private plans/ docs; lowercase
    # "phase" (e.g. "phased rollout") is fine. "Roadmap" leaks forward-
    # looking commitments; sister repo names and paths leak structure.
    ("internal planning vocabulary", re.compile(r"\bPhases?\b")),
    ("internal planning vocabulary", re.compile(r"\b[Rr]oadmap\b")),
    ("internal coordination repo", re.compile(r"logion-workspace")),
    ("internal docs path", re.compile(r"shared-docs/")),
    ("internal plans path", re.compile(r"(^|[\s\"'`(])plans/")),
    # LLM tells. The cheapest signal that prose was written by a model
    # without being edited. Surgical set — common-in-AI, rare-in-humans.
    (
        "LLM tell",
        re.compile(
            r"\bas (shown|mentioned) (above|below|earlier|previously)\b",
            re.IGNORECASE,
        ),
    ),
    ("LLM tell", re.compile(r"\bIt's important to note\b", re.IGNORECASE)),
    ("LLM tell", re.compile(r"\bIn (summary|conclusion),", re.IGNORECASE)),
    ("LLM tell", re.compile(r"\bdelve into\b", re.IGNORECASE)),
    ("LLM tell", re.compile(r"\bseamlessly\b", re.IGNORECASE)),
]

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "tests"}
SKIP_PREFIXES = (
    os.path.join(ROOT, "tests"),
    os.path.join(ROOT, ".git"),
    # Machine-generated evaluation reports. Contain absolute local paths
    # by design (sandbox roots emitted by llama.cpp / DSPy). Not human-
    # edited; not part of the public surface.
    os.path.join(ROOT, "packages", "agent-companion", "evals", "reports"),
)
SELF = os.path.abspath(__file__)

ALLOWLIST_PATH = os.path.join(ROOT, "scripts", "audit_public_safe.allowlist")


def load_allowlist() -> set[tuple[str, int]]:
    """Load path:line allowlist entries (one per line, ``#`` comments OK)."""
    entries: set[tuple[str, int]] = set()
    if not os.path.isfile(ALLOWLIST_PATH):
        return entries
    with open(ALLOWLIST_PATH) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                entries.add((parts[0], int(parts[1])))
    return entries


def should_skip(rel_path: str) -> bool:
    full = os.path.join(ROOT, rel_path)
    if full == SELF:
        return True
    for prefix in SKIP_PREFIXES:
        if full.startswith(prefix):
            return True
    return False


def audit() -> list[tuple[str, int, str]]:
    """Walk the repo and return [(rel_path, line_no, pattern_name), ...]."""
    hits: list[tuple[str, int, str]] = []
    allowlist = load_allowlist()

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Prune directories we never want to descend into
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        # Skip .git and tests directories entirely
        abs_dir = os.path.abspath(dirpath)
        skip = False
        for prefix in SKIP_PREFIXES:
            if abs_dir.startswith(prefix):
                skip = True
                break
        if skip:
            continue

        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, ROOT)

            if should_skip(rel):
                continue

            # Skip binary files
            try:
                with open(full, encoding="utf-8", errors="strict") as fh:
                    lines = fh.readlines()
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

            for lineno, line in enumerate(lines, start=1):
                for tag, pattern in FORBIDDEN:
                    if pattern.search(line) and (rel, lineno) not in allowlist:
                        hits.append((rel, lineno, tag))
                        break  # one hit per line is enough

    return hits


def main() -> None:
    hits = audit()
    if not hits:
        print("public-audit: clean — no forbidden patterns found.")
        sys.exit(0)

    print("public-audit: FORBIDDEN patterns detected:")
    for rel, lineno, tag in sorted(hits):
        print(f"  {rel}:{lineno}  [{tag}]")
    print(
        f"\n{len(hits)} hit(s). If a hit is a false positive, "
        f"add a path:line entry to scripts/audit_public_safe.allowlist."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()