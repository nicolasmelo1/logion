# SPDX-License-Identifier: MIT
"""Contract test: every leaf CLI command has non-empty help and --json.

An agent driving the CLI must always be able to (a) discover what a
command does and (b) get machine-readable output.  This test enforces
that invariant by walking the live ``build_parser()`` argparse tree and
asserting every leaf subcommand carries a non-empty description/help
string and a ``--json`` flag.

Failures are parameterized per leaf command path so the offending
command (e.g. ``skills install``) is named, not just "a command failed".
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator

from cli._parser import build_parser

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

    Yields ``(path, subparser, help_text, description)`` tuples where
    ``help_text`` is the ``help=`` from the parent's ``add_parser`` call
    and ``description`` is ``subparser.description``.
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


def _build_and_collect() -> tuple[
    argparse.ArgumentParser,
    list[tuple[tuple[str, ...], argparse.ArgumentParser, str, str]],
]:
    """Build the parser with admin enabled and collect leaves."""
    import os

    os.environ["LOGION_ENABLE_ADMIN"] = "1"
    parser = build_parser()
    leaves = list(_iter_leaves(parser))
    return parser, leaves


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_json_allowlist_is_empty_or_justified() -> None:
    """The JSON-exempt allowlist must be empty unless every entry is
    documented with a justification comment above."""
    # The allowlist is defined as a module-level frozenset.  If a
    # future command legitimately cannot emit JSON, add it there with
    # an inline comment explaining why.  This test asserts the set is
    # currently empty so any addition is a deliberate, reviewable diff.
    assert frozenset() == JSON_EXEMPT_COMMANDS, (
        "JSON_EXEMPT_COMMANDS is non-empty — each entry must be "
        "justified with a comment in the frozenset definition and "
        "approved by a reviewer."
    )


def test_every_leaf_command_has_nonempty_help() -> None:
    """Every leaf command must carry a non-empty help or description.

    argparse always *accepts* ``--help``, but if the subparser was
    registered without ``help=`` or ``description=``, ``--help`` prints a
    bare usage line that documents nothing.  We assert at least one of
    the two is non-empty.
    """
    _parser, leaves = _build_and_collect()
    missing: list[str] = []
    for path, _sub, help_text, desc in leaves:
        text = (help_text or desc or "").strip()
        if not text:
            missing.append(" ".join(path))
    assert not missing, (
        "Leaf commands with empty help AND description (agents cannot "
        "discover what they do):\n  - " + "\n  - ".join(missing)
    )


def _leaf_command_ids() -> list[tuple[str, tuple[str, ...]]]:
    """Return ``(id_string, path)`` for every leaf command."""
    _parser, leaves = _build_and_collect()
    return [(" ".join(path), path) for path, _sub, _h, _d in leaves]


def test_every_leaf_command_supports_json() -> None:
    """Every leaf command (not in the exempt set) must define ``--json``.

    Uses a single collection assertion so each offender is named in the
    failure message without pytest's parametrize limitations on
    module-scoped fixtures.
    """
    _parser, leaves = _build_and_collect()
    missing: list[str] = []
    for path, sub, _help, _desc in leaves:
        if path in JSON_EXEMPT_COMMANDS:
            continue
        flags = _flags_for(sub)
        if "--json" not in flags:
            missing.append(" ".join(path))
    assert not missing, (
        "Leaf commands missing --json (agents cannot get "
        "machine-readable output):\n  - "
        + "\n  - ".join(missing)
        + "\nIf a command genuinely cannot emit JSON, add it to "
        "JSON_EXEMPT_COMMANDS with a justification."
    )
