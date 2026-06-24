"""Tests for DiscordClient."""

from __future__ import annotations

import time

import httpx
import pytest

from social_management.core.config import SocialConfig
from social_management.core.errors import MissingCredentialsError
from social_management.discord.client import DiscordClient
from social_management.discord.constants import (
    DISCORD_API,
    WEBHOOK_RATE_LIMIT,
)


def _config_with_webhook(
    env,
    tmp_path,
    channel: str = "general",  # type: ignore[no-untyped-def]
) -> SocialConfig:
    env(**{  # type: ignore[arg-type]
        f"DISCORD_WEBHOOK_{channel.upper()}": (
            "https://discord.com/api/webhooks/test123"
        )
    })
    return SocialConfig.from_env(env_local=tmp_path / "nope")


def test_webhook_payload_shape(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _config_with_webhook(env, tmp_path)
    route = respx_mock.post("https://discord.com/api/webhooks/test123").mock(
        return_value=httpx.Response(204)
    )
    client = DiscordClient(config)
    result = client.post_webhook("general", "hi")
    assert result.sent is True
    assert route.called
    request = route.calls[0].request
    assert request.headers["content-type"] == "application/json"
    import json

    body = json.loads(request.content)
    assert body == {"content": "hi"}


def test_webhook_truncates_to_2000(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _config_with_webhook(env, tmp_path)
    route = respx_mock.post("https://discord.com/api/webhooks/test123").mock(
        return_value=httpx.Response(204)
    )
    client = DiscordClient(config)
    long_text = "a" * 2500
    client.post_webhook("general", long_text)
    request = route.calls[0].request
    import json

    body = json.loads(request.content)
    assert len(body["content"]) == 2000


def test_webhook_dry_run_no_network(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _config_with_webhook(env, tmp_path)
    client = DiscordClient(config)
    result = client.post_webhook("general", "hi", dry_run=True)
    assert result.sent is False
    assert result.rendered == "hi"
    assert respx_mock.calls.call_count == 0


def test_webhook_missing_raises(
    env,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    client = DiscordClient(config)
    with pytest.raises(MissingCredentialsError):
        client.post_webhook("general", "hi")


def test_read_recent_requires_bot_token(
    env,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    client = DiscordClient(config)
    with pytest.raises(MissingCredentialsError):
        client.read_recent("123")


def test_read_recent_maps_messages(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    env(DISCORD_BOT_TOKEN="bot123")
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    channel_id = "999"
    respx_mock.get(f"{DISCORD_API}/channels/{channel_id}").mock(
        return_value=httpx.Response(200, json={"type": 0})
    )
    respx_mock.get(f"{DISCORD_API}/channels/{channel_id}/messages").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "1",
                    "author": {"username": "alice"},
                    "content": "hello",
                    "timestamp": "2026-06-24T12:00:00Z",
                },
                {
                    "id": "2",
                    "author": {"username": "bob"},
                    "content": "world",
                    "timestamp": "2026-06-24T12:01:00Z",
                },
            ],
        )
    )
    client = DiscordClient(config)
    messages = client.read_recent(channel_id, limit=20)
    assert len(messages) == 2
    assert messages[0].author == "alice"
    assert messages[0].content == "hello"
    assert messages[1].author == "bob"
    assert messages[1].content == "world"


def test_webhook_forum_includes_thread_name(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _config_with_webhook(env, tmp_path, channel="support")
    route = respx_mock.post("https://discord.com/api/webhooks/test123").mock(
        return_value=httpx.Response(204)
    )
    client = DiscordClient(config)
    client.post_webhook("support", "Need help with setup")
    request = route.calls[0].request
    import json

    body = json.loads(request.content)
    assert "thread_name" in body
    assert body["thread_name"] == "Need help with setup"


def test_read_recent_forum_enumerates_threads(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    env(DISCORD_BOT_TOKEN="bot123")
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    channel_id = "forum555"
    respx_mock.get(f"{DISCORD_API}/channels/{channel_id}").mock(
        return_value=httpx.Response(200, json={"type": 15})
    )
    respx_mock.get(f"{DISCORD_API}/channels/{channel_id}/threads/active").mock(
        return_value=httpx.Response(
            200,
            json={
                "threads": [
                    {"id": "t1"},
                    {"id": "t2"},
                ]
            },
        )
    )
    respx_mock.get(f"{DISCORD_API}/channels/t1/messages").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "m1",
                    "author": {"username": "alice"},
                    "content": "thread1msg",
                    "timestamp": "2026-06-24T12:00:00Z",
                }
            ],
        )
    )
    respx_mock.get(f"{DISCORD_API}/channels/t2/messages").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "m2",
                    "author": {"username": "bob"},
                    "content": "thread2msg",
                    "timestamp": "2026-06-24T12:01:00Z",
                }
            ],
        )
    )
    # Ensure the direct messages endpoint is NOT called for forums.
    direct_msgs = respx_mock.get(
        f"{DISCORD_API}/channels/{channel_id}/messages"
    ).mock(return_value=httpx.Response(404))
    client = DiscordClient(config)
    messages = client.read_recent(channel_id, limit=20)
    assert len(messages) == 2
    assert messages[0].author == "alice"
    assert messages[1].author == "bob"
    assert not direct_msgs.called


def test_rate_limit_blocks_31st_post(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _config_with_webhook(env, tmp_path)
    respx_mock.post("https://discord.com/api/webhooks/test123").mock(
        return_value=httpx.Response(204)
    )
    client = DiscordClient(config)
    webhook_url = "https://discord.com/api/webhooks/test123"
    # Patch the deque to simulate 30 recent sends within the window.
    from collections import deque

    now = time.monotonic()
    client._sent_at[webhook_url] = deque(
        [now - 1.0] * WEBHOOK_RATE_LIMIT,
        maxlen=WEBHOOK_RATE_LIMIT,
    )
    # The 31st post should trigger a sleep. Use a small window to avoid
    # a long wait: mock time.sleep to capture the call instead.
    slept = []
    original_sleep = time.sleep

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        # Simulate time advancing past the oldest entry.
        client._sent_at[webhook_url].popleft()

    time.sleep = fake_sleep  # type: ignore[method-assign]
    try:
        client.post_webhook("general", "31st post")
    finally:
        time.sleep = original_sleep  # type: ignore[method-assign]
    assert len(slept) > 0
