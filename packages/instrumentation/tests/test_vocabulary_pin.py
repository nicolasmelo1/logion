# SPDX-License-Identifier: MIT
"""Grep-pinned test: vocabulary must match cli/usage/observations.py.

This test reads the CLI source file directly and asserts that the
enum values in ``logion_instrumentation.vocabulary`` are identical.
It prevents a second, divergent vocabulary set from drifting.

The instrumentation package must NOT import the CLI at runtime — this
test reads the source file as text, not as a Python module.
"""

from __future__ import annotations

import re
from pathlib import Path

from logion_instrumentation.vocabulary import (
    DURATION_BUCKET_VALUES,
    EVENT_VALUES,
    OUTCOME_VALUES,
)

#: Path to the CLI observations module, relative to the repo root.
#: The test discovers it by walking up from this file.
_CLI_OBSERVATIONS = (
    Path(__file__).resolve().parents[2]
    / "cli"
    / "cli"
    / "usage"
    / "observations.py"
)


def _extract_tuple(source: str, name: str) -> tuple[str, ...] | None:
    """Extract a tuple literal value from Python source text.

    Handles optional type annotations before the ``=`` sign:
    ``NAME: SomeType = ( ... )`` or ``NAME = ( ... )``.
    """
    pattern = rf"{name}\s*(?::[^=]+)?\s*=\s*\(([^)]+)\)"
    match = re.search(pattern, source, re.DOTALL)
    if match is None:
        return None
    body = match.group(1)
    return tuple(
        m.strip().strip('"').strip("'")
        for m in re.findall(r'["\']([^"\']+)["\']', body)
    )


def _extract_frozenset(source: str, name: str) -> tuple[str, ...] | None:
    """Extract a frozenset literal value from Python source text."""
    pattern = rf"{name}\s*=\s*frozenset\(\{{([^}}]+)\}}\)"
    match = re.search(pattern, source)
    if match is None:
        return None
    body = match.group(1)
    return tuple(
        m.strip().strip('"').strip("'")
        for m in re.findall(r'["\']([^"\']+)["\']', body)
    )


def test_cli_observations_file_exists() -> None:
    """The CLI source file must exist for vocabulary pinning."""
    assert _CLI_OBSERVATIONS.is_file(), (
        f"CLI observations file not found at {_CLI_OBSERVATIONS}"
    )


def test_event_values_match_cli() -> None:
    source = _CLI_OBSERVATIONS.read_text(encoding="utf-8")
    cli_events = _extract_tuple(source, "EVENT_VALUES")
    assert cli_events is not None, "EVENT_VALUES not found in CLI source"
    assert sorted(EVENT_VALUES) == sorted(cli_events), (
        f"EVENT_VALUES mismatch: instrumentation={EVENT_VALUES} "
        f"cli={cli_events}"
    )


def test_outcome_values_match_cli() -> None:
    source = _CLI_OBSERVATIONS.read_text(encoding="utf-8")
    cli_outcomes = _extract_tuple(source, "OUTCOME_VALUES")
    assert cli_outcomes is not None, "OUTCOME_VALUES not found in CLI source"
    assert sorted(OUTCOME_VALUES) == sorted(cli_outcomes), (
        f"OUTCOME_VALUES mismatch: instrumentation={OUTCOME_VALUES} "
        f"cli={cli_outcomes}"
    )


def test_duration_buckets_match_cli() -> None:
    source = _CLI_OBSERVATIONS.read_text(encoding="utf-8")
    cli_buckets = _extract_frozenset(source, "DURATION_BUCKETS")
    assert cli_buckets is not None, "DURATION_BUCKETS not found in CLI source"
    assert sorted(DURATION_BUCKET_VALUES) == sorted(cli_buckets), (
        f"DURATION_BUCKET_VALUES mismatch: "
        f"instrumentation={DURATION_BUCKET_VALUES} "
        f"cli={cli_buckets}"
    )


def test_no_second_vocabulary_definition() -> None:
    """The instrumentation package must not define a second enum set.

    Scans all Python files in the instrumentation package for tuple or
    list literals that look like event/outcome/bucket enums but are
    NOT in vocabulary.py.  Only vocabulary.py may define these.
    """
    pkg_src = Path(__file__).resolve().parents[1] / "src"
    enum_names = {
        "EVENTS",
        "OUTCOMES",
        "DURATION_BUCKETS",
        "EVENT_VALUES",
        "OUTCOME_VALUES",
        "DURATION_BUCKET_VALUES",
    }
    for py_file in pkg_src.rglob("*.py"):
        rel = py_file.relative_to(pkg_src)
        if rel.name == "vocabulary.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        for name in enum_names:
            # Allow imports and references, but not assignments.
            pattern = rf"^\s*{name}\s*[:=]"
            match = re.search(pattern, text, re.MULTILINE)
            assert match is None, (
                f"Second vocabulary definition: {name} assigned in"
                f" {rel} (only vocabulary.py may define enums)"
            )
