#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every driven actor in a proving-ground scenario receives a goal.

Implements ``L3.EVERY_ACTOR_HAS_A_GOAL``. An agent that declares a ``driver``
is a role the scenario claims met the product; if no phase ever hands it a
non-empty ``goal``, the work happened in a ``local_hook`` and the role is
decoration. An agent with no ``driver`` is the honest way to mark a fixture
step and is left alone.

The reader is deliberately strict rather than lenient. A scenario whose roster
or phase list cannot be read is reported, not skipped: a parser that quietly
matches nothing looks exactly like a rule that works.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    Path("packages/agent-proving-ground/agent_proving_ground")
    / "scenarios/builtin"
)
EXCEPTIONS = Path("scripts") / "allowed_mute_actors.txt"

ITEM_RE = re.compile(r"^(?P<indent> *)- +(?P<rest>\S.*)$")
FIELD_RE = re.compile(
    r"^(?P<indent> *)(?P<key>[A-Za-z_][A-Za-z0-9_]*): ?(?P<value>.*)$"
)
BLOCK_RE = re.compile(r"^[|>][-+0-9]*$")
EMPTY_SCALAR = {"", '""', "''", "~", "null"}


def _records(lines: list[str], block: str) -> list[dict[str, str]]:
    """Every ``- `` item directly under a top-level ``block:`` key."""
    out: list[dict[str, str]] = []
    inside = False
    item_indent = None
    for index, raw in enumerate(lines):
        if raw.rstrip() == f"{block}:":
            inside = True
            continue
        if not inside:
            continue
        if raw.strip() and not raw.startswith(" "):
            break
        item = ITEM_RE.match(raw.rstrip())
        if item:
            indent = len(item.group("indent"))
            if item_indent is None:
                item_indent = indent
            if indent != item_indent:
                continue
            out.append({})
            key, _, value = item.group("rest").partition(":")
            out[-1][key.strip()] = _scalar(
                value.strip(), lines, index, indent
            )
            continue
        field = FIELD_RE.match(raw.rstrip())
        if (
            field
            and item_indent is not None
            and out
            and len(field.group("indent")) == item_indent + 2
        ):
            out[-1][field.group("key")] = _scalar(
                field.group("value").strip(),
                lines,
                index,
                len(field.group("indent")),
            )
    return out


def _scalar(
    value: str, lines: list[str], index: int, field_indent: int
) -> str:
    """A field's value, following a ``|`` or ``>`` block into its body."""
    if not BLOCK_RE.match(value):
        return value
    body = []
    for raw in lines[index + 1 :]:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= field_indent:
            break
        if not ITEM_RE.match(raw.rstrip()):
            body.append(raw.strip())
    return " ".join(body)


def _load_exceptions(root: Path) -> tuple[set[str], str | None]:
    path = root / EXCEPTIONS
    if not path.exists():
        return set(), None
    keys: set[str] = set()
    review_by = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("review_by:"):
            review_by = line.split(":", 1)[1].strip()
        elif line and not line.startswith("#"):
            keys.add(line)
    return keys, review_by


def _mute(path: Path) -> tuple[list[str], list[str]]:
    """``(mute driven agents, reasons the file could not be judged)``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    agents = _records(lines, "agents")
    phases = _records(lines, "phases")
    if not agents:
        return [], [f"{path.name}: no agent roster could be read"]
    if not phases:
        return [], [f"{path.name}: no phases could be read"]
    voiced = {
        phase.get("actor")
        for phase in phases
        if phase.get("goal", "").strip() not in EMPTY_SCALAR
    }
    driven = [a["id"] for a in agents if a.get("driver", "").strip()]
    return [agent for agent in driven if agent not in voiced], []


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else DEFAULT_ROOT
    allowed, review_by = _load_exceptions(root)
    findings: list[str] = []
    seen: set[str] = set()
    scenarios = sorted((root / SCENARIOS).glob("*.yaml"))
    if not scenarios:
        print(f"no scenarios under {root / SCENARIOS}", file=sys.stderr)
        return 1
    for path in scenarios:
        mute, unreadable = _mute(path)
        findings.extend(unreadable)
        for agent in mute:
            key = f"{path.name}:{agent}"
            seen.add(key)
            if key not in allowed:
                findings.append(
                    f"{key}: declares a driver but no phase gives it a goal"
                )
    for stale in sorted(allowed - seen):
        findings.append(f"{stale}: listed as an exception but no longer mute")
    if review_by and review_by < _today():
        findings.append(f"the exception list expired on {review_by}")
    for finding in findings:
        print(finding, file=sys.stderr)
    return 1 if findings else 0


def _today() -> str:
    return datetime.now(tz=timezone.utc).date().isoformat()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
