"""Discord client: webhook posting + read-only bot triage."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

import httpx

from social_management._json import JsonObject
from social_management.core.config import SocialConfig
from social_management.core.errors import MissingCredentialsError
from social_management.core.models import PostResult
from social_management.discord.constants import (
    DISCORD_API,
    KNOWN_FORUM_CHANNELS,
    WEBHOOK_RATE_LIMIT,
    WEBHOOK_RATE_WINDOW_S,
)
from social_management.discord.models import RecentMessage


class DiscordClient:
    """Thin wrapper over Discord's webhook + channel-messages endpoints."""

    def __init__(
        self,
        config: SocialConfig,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._http = client or httpx.Client(timeout=15.0)
        self._sent_at: dict[str, deque[float]] = {}

    def _respect_rate_limit(self, webhook_url: str) -> None:
        """Block if >30 posts to the same webhook in 60s.

        Trim a deque of send timestamps to the window; if it is already
        full, sleep until the oldest falls out.
        """
        now = time.monotonic()
        window = self._sent_at.setdefault(
            webhook_url, deque(maxlen=WEBHOOK_RATE_LIMIT)
        )
        # Drop entries older than the window.
        while window and window[0] <= now - WEBHOOK_RATE_WINDOW_S:
            window.popleft()
        if len(window) >= WEBHOOK_RATE_LIMIT:
            # Sleep until the oldest falls out of the window.
            sleep_for = window[0] + WEBHOOK_RATE_WINDOW_S - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            # Re-trim after sleeping.
            now = time.monotonic()
            while window and window[0] <= now - WEBHOOK_RATE_WINDOW_S:
                window.popleft()
        window.append(time.monotonic())

    def post_webhook(
        self, channel: str, content: str, *, dry_run: bool = False
    ) -> PostResult:
        """Post `content` to a channel's incoming webhook.

        Text channels: POST {webhook_url}  body={"content": content}
        (<=2000 chars). Forum channels (e.g. the `support` slot): the
        body MUST also carry ``thread_name`` (new post) or the request
        gets ``?thread_id=...`` (existing thread).
        Raises MissingCredentialsError if the channel has no configured
        webhook (even on dry_run, so misconfiguration is caught early).
        On dry_run: returns a PostResult with sent=False and
        rendered=content, making NO network call.
        """
        webhook_url = self._config.webhook_for(channel)  # may raise
        if dry_run:
            return PostResult(
                platform="discord",
                target=channel,
                dry_run=True,
                sent=False,
                rendered=content,
            )
        self._respect_rate_limit(webhook_url)
        # Forum channels require thread_name/thread_id (see note above).
        body: dict[str, object] = {"content": content[:2000]}
        if channel in KNOWN_FORUM_CHANNELS:
            thread_name = content[:100].strip() or "Logion post"
            body["thread_name"] = thread_name
        resp = self._http.post(webhook_url, json=body)
        resp.raise_for_status()
        return PostResult(
            platform="discord",
            target=channel,
            dry_run=False,
            sent=True,
            rendered=content,
        )

    def read_recent(
        self,
        channel_id: str,
        limit: int = 20,
        *,
        dry_run: bool = False,
    ) -> list[RecentMessage]:
        """Read recent messages from a channel using the bot token.

        Text channels: GET /channels/{id}/messages?limit=N. Forum
        channels (the ``support`` slot): enumerate threads then read
        per-thread messages and merge.

        Read-only. Raises MissingCredentialsError if no bot token is
        set. Maps each message to
        RecentMessage(id, author, content, created_at).
        """
        if dry_run:
            return []
        if not self._config.discord_bot_token:
            raise MissingCredentialsError("DISCORD_BOT_TOKEN not set")
        headers = {"Authorization": f"Bot {self._config.discord_bot_token}"}
        # Detect channel type: 15 = GUILD_FORUM.
        ch_resp = self._http.get(
            f"{DISCORD_API}/channels/{channel_id}", headers=headers
        )
        ch_resp.raise_for_status()
        ch_type = ch_resp.json().get("type", 0)
        messages: list[JsonObject] = []
        if ch_type == 15:
            # Forum: enumerate active threads, then read each.
            threads_resp = self._http.get(
                f"{DISCORD_API}/channels/{channel_id}/threads/active",
                headers=headers,
            )
            threads_resp.raise_for_status()
            threads = threads_resp.json().get("threads", [])
            for thread in threads:
                tid = thread["id"]
                per = min(limit, 10)
                mr = self._http.get(
                    f"{DISCORD_API}/channels/{tid}/messages",
                    params={"limit": per},
                    headers=headers,
                )
                mr.raise_for_status()
                messages.extend(mr.json())
                if len(messages) >= limit:
                    break
        else:
            # Text channel: direct messages read.
            mr = self._http.get(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                params={"limit": limit},
                headers=headers,
            )
            mr.raise_for_status()
            messages = mr.json()
        # Map to RecentMessage, cap at limit.
        results: list[RecentMessage] = []
        for msg in messages[:limit]:
            author = msg.get("author")
            username = (
                author.get("username") if isinstance(author, dict) else None
            )
            # A message with no usable timestamp is skipped rather than
            # crashing the triage read: Discord only ever omits it on
            # payload shapes we do not consume.
            ts = msg.get("timestamp")
            if not isinstance(ts, str):
                continue
            created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            results.append(
                RecentMessage(
                    id=str(msg.get("id", "")),
                    author=(
                        username if isinstance(username, str) else "unknown"
                    ),
                    content=str(msg.get("content", "")),
                    created_at=created,
                )
            )
        return results
