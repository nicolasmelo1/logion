"""Phase 6.10 §11.5: CLI-parity test for references.

Extracts every ``logion ...`` invocation from each
``references/*.md`` and asserts:

1. The verb chain (``logion bounties submissions list``) is registered
   in the live ``logion`` argparse tree.
2. Every ``--flag`` named in the bash block is a real flag on the
   resolved subparser.

This is the gate that prevents docs from drifting from the CLI.
"""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

import pytest

from cli._parser import build_parser

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"

CANONICAL_REFERENCES = (
    "creator-course-management.md",
    "account-and-identity.md",
    "notifications-and-reports.md",
    "payments-and-checkout.md",
    "bounties.md",
    "course-review-queue.md",
    "admin-operations.md",
    "troubleshooting.md",
)


def _iter_subparsers(parser: argparse.ArgumentParser):
    """Yield (name, subparser) pairs for every subcommand."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            yield from action.choices.items()


def _resolve_command(
    parser: argparse.ArgumentParser, tokens: list[str]
) -> tuple[argparse.ArgumentParser | None, list[str]]:
    """Walk down the argparse tree following positional subcommand
    tokens. Stops as soon as a token does not match a registered
    subparser (which is how the parser would itself interpret a
    positional argument). Returns ``(deepest_parser, consumed_tokens)``.

    If the first token does not match any subcommand, returns
    ``(None, [])``.
    """
    current = parser
    consumed: list[str] = []
    for token in tokens:
        children = dict(_iter_subparsers(current))
        if not children:
            break
        if token not in children:
            # Either a positional value (COURSE_ID) or an invalid verb.
            # We can't tell the two apart from argparse introspection
            # alone, so we trust the deepest matching parser.
            break
        current = children[token]
        consumed.append(token)
    if not consumed and current is parser:
        return None, []
    return current, consumed


def _flags_for(parser: argparse.ArgumentParser) -> set[str]:
    flags: set[str] = set()
    for action in parser._actions:
        for opt in action.option_strings:
            if opt.startswith("--"):
                flags.add(opt)
    return flags


_LOGION_CMD_RE = re.compile(r"\blogion\b[^\n;|`<>]*")


def _extract_bash_commands(markdown: str) -> list[str]:
    """Return ``logion ...`` invocations from fenced bash blocks and
    inline backtick spans. Each command is extracted per-line so that a
    multi-command block produces multiple entries."""
    commands: list[str] = []
    in_block = False
    fence_lang: str | None = None
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                in_block = False
                fence_lang = None
            else:
                fence_lang = stripped.lstrip("`").strip().lower() or None
                in_block = fence_lang in {None, "bash", "shell", "sh"}
            continue
        if in_block:
            cleaned = line.split("#", 1)[0].rstrip(" \\")
            for match in _LOGION_CMD_RE.finditer(cleaned):
                commands.append(match.group(0).strip())
        else:
            for backtick_match in re.finditer(r"`([^`]+)`", line):
                span = backtick_match.group(1)
                if "logion" not in span:
                    continue
                for match in _LOGION_CMD_RE.finditer(span):
                    commands.append(match.group(0).strip())
    return commands


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


@pytest.fixture(scope="module")
def root_parser(
    monkeypatch_module: pytest.MonkeyPatch,
) -> argparse.ArgumentParser:
    # Admin commands are gated by env var; enable so the parity test
    # can validate the admin-operations reference.
    monkeypatch_module.setenv("LOGION_ENABLE_ADMIN", "1")
    return build_parser()


@pytest.fixture(scope="module")
def monkeypatch_module() -> pytest.MonkeyPatch:
    mpatch = pytest.MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.mark.parametrize("reference_name", CANONICAL_REFERENCES)
def test_references_cli_parity_each_file(
    reference_name: str, root_parser: argparse.ArgumentParser
) -> None:
    path = REFERENCES_DIR / reference_name
    assert path.exists(), f"missing canonical reference: {reference_name}"
    commands = _extract_bash_commands(path.read_text())
    assert commands, (
        f"{reference_name} has no ``logion ...`` bash commands — either "
        "it is a stub or the extractor is broken."
    )

    errors: list[str] = []
    for command in commands:
        tokens = _tokenize(command)
        if not tokens or tokens[0] != "logion":
            continue
        positional_tokens = [t for t in tokens[1:] if not t.startswith("-")]
        flags = {t.split("=", 1)[0] for t in tokens[1:] if t.startswith("--")}

        # ``logion`` alone (e.g. truncated by a ``<placeholder>``) carries
        # no information to validate.
        if not positional_tokens and not flags:
            continue

        sub, consumed = _resolve_command(root_parser, positional_tokens)
        if sub is None:
            errors.append(f"unknown verb chain: {' '.join(tokens)}")
            continue

        valid_flags = _flags_for(sub)
        # --help is registered on every argparse parser.
        valid_flags.add("--help")
        unknown = flags - valid_flags
        if unknown:
            errors.append(
                f"unknown flag(s) {sorted(unknown)} for "
                f"`{' '.join(['logion', *consumed])}`"
            )

    assert not errors, (
        f"{reference_name} contains invalid CLI usage:\n  - "
        + "\n  - ".join(errors)
    )
