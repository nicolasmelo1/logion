#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep the duplicated ``_json.py`` helper module byte-identical.

``typing.Any`` is banned repo-wide (ruff ``TID251``), so every package
needs the ``JsonValue``/``JsonObject`` aliases and the ``require_*``
narrowing helpers that replace it. The packages here are published
independently, so importing a shared module would mean adding a runtime
dependency between them purely for typing. Instead the module is
duplicated, and this check turns that duplication into an enforced
invariant rather than something that quietly drifts.

The copy under ``packages/client`` is canonical. Run with ``--update``
to rewrite every other copy from it.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CANONICAL = os.path.join("packages", "client", "src", "logion", "_json.py")

# Copies, and whether that package's files carry an SPDX header. The
# convention is per package, so the check compares the body only and
# applies the local header rule.
COPIES: tuple[tuple[str, bool], ...] = (
    (os.path.join("packages", "cli", "cli", "_json.py"), True),
    (
        os.path.join(
            "packages", "agent-companion", "evals", "harness", "_json.py"
        ),
        True,
    ),
    (os.path.join("packages", "indexer", "logion_indexer", "_json.py"), True),
    (os.path.join("packages", "landing", "landing", "_json.py"), True),
    (
        os.path.join(
            "packages",
            "agent-proving-ground",
            "agent_proving_ground",
            "_json.py",
        ),
        False,
    ),
    (
        os.path.join("packages", "scanners", "logion_scanners", "_json.py"),
        False,
    ),
    (
        os.path.join(
            "packages", "social-management", "social_management", "_json.py"
        ),
        False,
    ),
)

SPDX_LINE = "# SPDX-License-Identifier: MIT\n"


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel)) as fh:
        return fh.read()


def body_of(text: str) -> str:
    """Return *text* without a leading SPDX header line."""
    if text.startswith(SPDX_LINE):
        return text[len(SPDX_LINE) :]
    return text


def expected_for(body: str, spdx: bool) -> str:
    return SPDX_LINE + body if spdx else body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite every copy from the canonical module.",
    )
    args = parser.parse_args()

    body = body_of(read(CANONICAL))
    stale: list[str] = []

    for rel, spdx in COPIES:
        path = os.path.join(ROOT, rel)
        want = expected_for(body, spdx)
        have = read(rel) if os.path.isfile(path) else None
        if have == want:
            continue
        if args.update:
            with open(path, "w") as fh:
                fh.write(want)
            print(f"  updated {rel}")
        else:
            stale.append(rel)

    if args.update:
        print("check_json_module_sync: copies synced.")
        return

    if not stale:
        print("check_json_module_sync: ok.")
        return

    print("check_json_module_sync: _json.py copies drifted from canonical:")
    for rel in stale:
        print(f"  {rel}")
    print(
        f"\nCanonical copy is {CANONICAL}. Edit that one, then run "
        "`make update-json-module` to propagate."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
