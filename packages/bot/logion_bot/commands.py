# SPDX-License-Identifier: MIT
"""Command grammar and pinned comment copy for the issue-mention bot.

All user-facing amounts are credits. Never render USD here.
"""

from __future__ import annotations

# Matches "@{bot_login}" as a standalone token, case-insensitive.
# bot_login comes from settings.github_app_bot_login (the App slug,
# WITHOUT the "[bot]" suffix GitHub appends to the acting identity).
ISSUE_BOUNTY_COMMANDS = ("bounty", "confirm", "cancel", "help")

# Amount token: integer credits, 1..9_999_999. No decimals, no symbols.
ISSUE_BOUNTY_AMOUNT_RE = r"^[1-9][0-9]{0,6}$"

# Optional course disambiguator token: "course:<slug>"
ISSUE_BOUNTY_COURSE_TOKEN_PREFIX = "course:"

ISSUE_BOUNTY_THREAD_STATES = (
    "awaiting_amount",
    "awaiting_confirmation",
    "opened",
    "cancelled",
    "expired",
)
