"""Constants shared across all domains."""

from __future__ import annotations

# Logical channel slot -> env var holding its webhook URL. These slot
# names are the CLI's stable --channel vocabulary; the actual Discord
# channel each URL targets is decided during server setup (e.g.
# "creators" -> #course-building; "support" -> the #support forum).
WEBHOOK_ENV_BY_CHANNEL: dict[str, str] = {
    "announcements": "DISCORD_WEBHOOK_ANNOUNCEMENTS",
    "general": "DISCORD_WEBHOOK_GENERAL",
    "support": "DISCORD_WEBHOOK_SUPPORT",
    "creators": "DISCORD_WEBHOOK_CREATORS",
}

CONTENT_DIR_NAME = "content"
SPEND_LEDGER_FILE = ".spend-ledger.json"
ENV_LOCAL_FILE = ".env.local"
