# SPDX-License-Identifier: MIT
"""Contract test: every leaf CLI command has non-empty help and --json.

An agent driving the CLI must always be able to (a) discover what a
command does and (b) get machine-readable output.  This test enforces
that invariant by walking the live ``build_parser()`` argparse tree and
asserting every leaf subcommand carries a non-empty description/help
string and a ``--json`` flag.

Each leaf command is a separate parametrized test case so a failure
names the exact offending command path (e.g. ``skills install``), not
just "a command failed."
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from cli._parser import build_parser


@contextmanager
def _admin_enabled_temporarily() -> Iterator[None]:
    """Temporarily enable admin commands while collecting parser leaves."""
    old = os.environ.get("LOGION_ENABLE_ADMIN")
    os.environ["LOGION_ENABLE_ADMIN"] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("LOGION_ENABLE_ADMIN", None)
        else:
            os.environ["LOGION_ENABLE_ADMIN"] = old


# ---------------------------------------------------------------------------
# Argparse tree introspection helpers
# ---------------------------------------------------------------------------


def _iter_subparsers(
    parser: argparse.ArgumentParser,
) -> Iterator[tuple[str, argparse.ArgumentParser]]:
    """Yield ``(name, subparser)`` for every direct child subcommand."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            yield from action.choices.items()


def _flags_for(parser: argparse.ArgumentParser) -> set[str]:
    """Return the set of ``--flag`` strings registered on *parser*."""
    flags: set[str] = set()
    for action in parser._actions:
        for opt in action.option_strings:
            if opt.startswith("--"):
                flags.add(opt)
    return flags


def _help_for_choice(
    parent_action: argparse._SubParsersAction,
    name: str,
) -> str:
    """Return the ``help=`` string passed to ``add_parser(name, help=...)``.

    argparse stores it on a ``_ChoicesPseudoAction`` inside the parent
    ``_SubParsersAction``.  Fallback to empty string if not found.
    """
    for ca in parent_action._choices_actions:
        if ca.dest == name:
            return ca.help or ""
    return ""


def _iter_leaves(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], argparse.ArgumentParser, str, str]]:
    """Walk the argparse tree yielding leaf commands only.

    A leaf is a subparser that has no further ``_SubParsersAction``
    (i.e. it dispatches directly to a handler, not to sub-subcommands).
    """
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child_name, child_parser in action.choices.items():
                child_path = (*path, child_name)
                child_help = _help_for_choice(action, child_name)
                child_desc = child_parser.description or ""
                has_subparsers = any(
                    isinstance(a, argparse._SubParsersAction)
                    for a in child_parser._actions
                )
                if has_subparsers:
                    yield from _iter_leaves(child_parser, child_path)
                else:
                    yield child_path, child_parser, child_help, child_desc


# ---------------------------------------------------------------------------
# Explicit allowlist for commands that legitimately cannot emit JSON.
#
# Default expectation: this set is empty.  Each entry must include a
# comment justifying why --json is not applicable.  A reviewer must
# approve any addition; the test FAILS (not skips) for unlisted violators.
# ---------------------------------------------------------------------------

JSON_EXEMPT_COMMANDS: frozenset[tuple[str, ...]] = frozenset()


def _build_and_collect() -> list[
    tuple[tuple[str, ...], argparse.ArgumentParser, str, str]
]:
    """Build the parser with admin enabled briefly and collect leaves."""
    with _admin_enabled_temporarily():
        parser = build_parser()
    return list(_iter_leaves(parser))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_json_allowlist_is_empty_or_justified() -> None:
    """The JSON-exempt allowlist must be empty unless every entry is
    documented with a justification comment above."""
    assert frozenset() == JSON_EXEMPT_COMMANDS, (
        "JSON_EXEMPT_COMMANDS is non-empty — each entry must be "
        "justified with a comment in the frozenset definition and "
        "approved by a reviewer."
    )


def test_every_leaf_command_has_nonempty_help() -> None:
    """Every leaf command must carry a non-empty help or description."""
    leaves = _build_and_collect()
    missing: list[str] = []
    for path, _sub, help_text, desc in leaves:
        text = (help_text or desc or "").strip()
        if not text:
            missing.append(" ".join(path))
    assert not missing, (
        "Leaf commands with empty help AND description (agents cannot "
        "discover what they do):\n  - " + "\n  - ".join(missing)
    )


def _leaf_ids() -> list[str]:
    """Return ``"path parts"`` for every leaf, for parametrize IDs."""
    leaves = _build_and_collect()
    return [" ".join(path) for path, _sub, _h, _d in leaves]


def _leaf_param_data() -> list[
    tuple[tuple[str, ...], argparse.ArgumentParser]
]:
    """Return ``(path, subparser)`` for every leaf command."""
    leaves = _build_and_collect()
    return [(path, sub) for path, sub, _h, _d in leaves]


@pytest.mark.parametrize(
    ("path", "sub"),
    _leaf_param_data(),
    ids=_leaf_ids(),
)
def test_every_leaf_command_supports_json(
    path: tuple[str, ...],
    sub: argparse.ArgumentParser,
) -> None:
    """Every leaf command (not in the exempt set) must define ``--json``.

    Parametrized per leaf so a failure names the exact offending command
    path (e.g. ``skills install``), not just ``"a command failed"``.
    """
    if path in JSON_EXEMPT_COMMANDS:
        pytest.skip(
            reason=f"{path!r} is in JSON_EXEMPT_COMMANDS",
        )
    flags = _flags_for(sub)
    assert "--json" in flags, (
        f"{' '.join(path)} is missing --json "
        f"(agents cannot get machine-readable output). "
        f"If a command genuinely cannot emit JSON, add it to "
        f"JSON_EXEMPT_COMMANDS with a justification."
    )
