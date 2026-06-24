"""Constants for the Discord domain."""

from __future__ import annotations

DISCORD_API = "https://discord.com/api/v10"
WEBHOOK_RATE_LIMIT = 30  # messages
WEBHOOK_RATE_WINDOW_S = 60  # per minute, per webhook

# Channels known to be forum (type 15) for webhook posting.
# Trade-off: post_webhook only has the webhook URL, not the channel id
# needed to call GET /channels/{id} and detect type==15 (GUILD_FORUM).
# So we hardcode the known forum slots here. read_recent detects forum
# vs text dynamically (it has the channel id). If another slot becomes
# a forum, add it here or the webhook post will 400.
KNOWN_FORUM_CHANNELS = frozenset({"support"})
