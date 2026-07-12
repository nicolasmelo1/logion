# SPDX-License-Identifier: MIT
"""Pure, zero-I/O parser for issue-mention bot commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .commands import (
    ISSUE_BOUNTY_AMOUNT_RE,
    ISSUE_BOUNTY_COURSE_TOKEN_PREFIX,
)

_FENCE_RE = re.compile(r"```[\s\S]*?```")
_FENCE_MARK = "```"
_COURSE_PREFIX_LEN = len(ISSUE_BOUNTY_COURSE_TOKEN_PREFIX)


@dataclass(frozen=True)
class IssueBotCommand:
    kind: str
    amount_credits: int | None = None
    course_slug: str | None = None


def _parse_bounty_amount(tokens: list[str]) -> tuple[int | None, str | None]:
    """Return (amount_credits, course_slug) from tokens after the verb."""
    amount: int | None = None
    course_slug: str | None = None
    for nxt in tokens:
        nxt_low = nxt.lower()
        if nxt_low == "credits":
            continue
        if nxt_low == "confirm":
            # One comment can propose; confirmation must be a later comment.
            # The parser ignores the trailing confirm token and still
            # returns the bounty proposal for the backend to handle.
            continue
        if nxt_low.startswith(ISSUE_BOUNTY_COURSE_TOKEN_PREFIX):
            course_slug = nxt[_COURSE_PREFIX_LEN:]
            continue
        if re.match(ISSUE_BOUNTY_AMOUNT_RE, nxt):
            if amount is not None:
                # A second amount token is ambiguous input, not a retry.
                amount = None
                break
            amount = int(nxt)
            continue
        # Any other token after a candidate amount invalidates it.
        amount = None
        break
    return amount, course_slug


def parse_issue_bot_command(
    body: str, *, bot_login: str
) -> IssueBotCommand | None:
    """Parse one comment/issue body into at most one bot command."""
    text = _FENCE_RE.sub("", body)
    # An unterminated fence renders as code to the end of the body, so
    # anything after it must be ignored too.
    text = text.split(_FENCE_MARK, 1)[0]
    tokens = text.split()
    mention = f"@{bot_login}".lower()
    try:
        idx = next(i for i, tok in enumerate(tokens) if tok.lower() == mention)
    except StopIteration:
        return None

    for verb_idx, tok in enumerate(tokens[idx + 1 :], start=idx + 1):
        low = tok.lower()
        if low == "bounty":
            amount, course_slug = _parse_bounty_amount(tokens[verb_idx + 1 :])
            return IssueBotCommand(
                kind="bounty", amount_credits=amount, course_slug=course_slug
            )
        if low == "confirm":
            return IssueBotCommand(kind="confirm")
        if low == "cancel":
            return IssueBotCommand(kind="cancel")
        if low == "help":
            return IssueBotCommand(kind="help")

    return None
