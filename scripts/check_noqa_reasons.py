#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Require a written reason on complexity suppressions.

``# noqa: C901`` silences the one rule that says a function has grown
past what a reader can hold. Silencing it is sometimes right, but it
should cost a sentence — an unexplained suppression is how
MockApiAdapter.query reached 85 branches and 149 statements with the
guardrail nominally switched on.

So: the directive is allowed, but it must carry a reason after a ``-``
or an em dash. The same applies to ``PLR0912``/``PLR0915``.

Files mirrored byte-for-byte from the canonical planning repo are
exempt, since a style change here would break check_roadmap_mirror.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCAN_DIRS = ("packages", "scripts", "tests")
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".runs",
    "node_modules",
}

# Mirrored from the canonical planning repo; see check_roadmap_mirror.
EXEMPT = {os.path.join("scripts", "check_protocol_specs.py")}

GUARDED = ("C901", "PLR0912", "PLR0915")
DIRECTIVE = re.compile(
    r"#\s*noqa:\s*(?P<codes>[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)"
    r"(?P<reason>.*)$"
)


def has_reason(text: str) -> bool:
    """True when the directive is followed by prose explaining it."""
    stripped = text.strip().lstrip("-—:").strip()
    return len(stripped) >= 10


def iter_files() -> list[str]:
    files: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(ROOT, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            files.extend(
                os.path.join(dirpath, name)
                for name in filenames
                if name.endswith(".py")
            )
    return sorted(files)


def main() -> None:
    failures: list[tuple[str, int, str]] = []
    for path in iter_files():
        rel = os.path.relpath(path, ROOT)
        if rel in EXEMPT:
            continue
        with open(path) as fh:
            for lineno, line in enumerate(fh, start=1):
                match = DIRECTIVE.search(line)
                if match is None:
                    continue
                codes = {
                    code.strip() for code in match.group("codes").split(",")
                }
                guarded = sorted(codes & set(GUARDED))
                if guarded and not has_reason(match.group("reason")):
                    failures.append((rel, lineno, ", ".join(guarded)))

    if not failures:
        print("check_noqa_reasons: ok.")
        return

    print("check_noqa_reasons: complexity suppressions without a reason:")
    for rel, lineno, codes in failures:
        print(f"  {rel}:{lineno}  # noqa: {codes}")
    print(
        "\nEither split the function, or say why it should stay whole "
        "by appending a reason after the code, separated by a dash."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
