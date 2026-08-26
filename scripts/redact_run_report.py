# SPDX-License-Identifier: MIT
"""Make a proving-ground run report safe to retain in a public tree.

A run report is written on the machine that ran it, so it carries that
machine's absolute paths -- including the checkout that drives the dev
rig, whose name must not appear here. Retaining it verbatim publishes
someone's home directory layout and an internal repository name as a
side effect of proving a phase.

Redaction is by path, not by name. The roots come from the environment
at redaction time, so this script never has to contain the names it is
removing, and it keeps working when the layout changes.

What survives is what the evidence is for: which assertions ran, what
they observed, and the shape of the paths involved. `${DEVRIG}/evidence
/crawl-1.json` still says the crawl report was read from the run's own
evidence directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

#: Longest first: the rig root is inside the home directory, and
#: replacing the home first would leave the more specific root
#: unrecognizable.
PLACEHOLDERS = (
    ("LOGION_PROVING_GROUND_ARTIFACT_ROOT", "${ARTIFACTS}"),
    ("LOGION_DEVRIG_ROOT", "${DEVRIG}"),
    ("LOGION_PUBLIC_REPO_PATH", "${PUBLIC_REPO}"),
    ("HOME", "${HOME}"),
)


def _roots(extra: list[str]) -> list[tuple[str, str]]:
    """Collect the absolute prefixes to strip, longest first."""
    roots: list[tuple[str, str]] = []
    for index, given in enumerate(extra):
        roots.append((given, f"${{ROOT_{index}}}"))
    for env_name, placeholder in PLACEHOLDERS:
        value = os.environ.get(env_name)
        if value:
            roots.append((value, placeholder))
            # The rig lives beside the repository it drives, and that
            # sibling's name is the one that must not survive.
            roots.append((str(Path(value).parent), f"{placeholder}/.."))
    return sorted(roots, key=lambda item: len(item[0]), reverse=True)


def redact(text: str, roots: list[tuple[str, str]]) -> str:
    for value, placeholder in roots:
        if value and value != "/":
            text = text.replace(value, placeholder)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="run report to redact in place")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="an additional absolute prefix to replace",
    )
    args = parser.parse_args(argv)

    path = Path(args.report)
    original = path.read_text(encoding="utf-8")
    redacted = redact(original, _roots(args.root))

    # Parse after redacting: a replacement that broke the JSON would
    # otherwise be discovered by whoever reads the evidence next.
    try:
        json.loads(redacted)
    except json.JSONDecodeError as exc:
        print(f"redaction produced invalid JSON: {exc}", file=sys.stderr)
        return 1

    path.write_text(redacted, encoding="utf-8")
    print(f"redacted {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
