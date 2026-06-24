"""Configuration loaded from environment / .env.local."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from social_management.core.constants import (
    ENV_LOCAL_FILE,
    WEBHOOK_ENV_BY_CHANNEL,
)
from social_management.core.errors import MissingCredentialsError, SocialError

XBackend = Literal["api", "off"]


def _load_env_local(path: Path) -> None:
    """Populate os.environ from a KEY=value .env.local (no override).

    Lines that are blank or start with '#' are skipped. Existing env
    vars win (so the shell can override the file). No external
    dependency.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class SocialConfig(BaseModel):
    """Immutable, validated view of all social creds + the budget cap."""

    model_config = ConfigDict(frozen=True)

    discord_bot_token: str | None = None
    discord_guild_id: str | None = None
    discord_channel_support: str | None = None
    discord_webhooks: dict[str, str] = Field(default_factory=dict)
    x_backend: XBackend = "off"
    x_api_key: str | None = None
    x_api_secret: str | None = None
    x_access_token: str | None = None
    x_access_secret: str | None = None
    x_bearer_token: str | None = None
    x_monthly_budget_cents: int = 0

    @classmethod
    def from_env(cls, *, env_local: Path | None = None) -> SocialConfig:
        """Build config from os.environ, after merging .env.local.

        `env_local` defaults to ./.env.local in the cwd. Missing values
        are left as None; validation that a given backend has what it
        needs is deferred to the client (so `--dry-run` works with
        nothing set).
        """
        if env_local is None:
            env_local = Path(ENV_LOCAL_FILE)
        _load_env_local(env_local)
        webhooks = {
            ch: os.environ[var]
            for ch, var in WEBHOOK_ENV_BY_CHANNEL.items()
            if os.environ.get(var)
        }
        raw_backend = os.environ.get("X_BACKEND", "off")
        if raw_backend not in ("api", "off"):
            raise SocialError(
                f"X_BACKEND={raw_backend!r} is invalid; must be 'api' or 'off'"
            )
        return cls(
            discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN"),
            discord_guild_id=os.environ.get("DISCORD_GUILD_ID"),
            discord_channel_support=os.environ.get("DISCORD_CHANNEL_SUPPORT"),
            discord_webhooks=webhooks,
            x_backend=raw_backend,  # type: ignore[arg-type]
            x_api_key=os.environ.get("X_API_KEY"),
            x_api_secret=os.environ.get("X_API_SECRET"),
            x_access_token=os.environ.get("X_ACCESS_TOKEN"),
            x_access_secret=os.environ.get("X_ACCESS_SECRET"),
            x_bearer_token=os.environ.get("X_BEARER_TOKEN"),
            x_monthly_budget_cents=int(
                os.environ.get("X_MONTHLY_BUDGET_CENTS", "0")
            ),
        )

    def webhook_for(self, channel: str) -> str:
        """Return the webhook URL for a channel or raise."""
        url = self.discord_webhooks.get(channel)
        if not url:
            env_var = WEBHOOK_ENV_BY_CHANNEL.get(channel, "DISCORD_WEBHOOK_*")
            raise MissingCredentialsError(
                f"no webhook configured for #{channel} (set {env_var})"
            )
        return url

    def has_x_oauth1(self) -> bool:
        return all((
            self.x_api_key,
            self.x_api_secret,
            self.x_access_token,
            self.x_access_secret,
        ))

    def x_is_live(self) -> bool:
        """True only when backend=api AND a usable credential set exists."""
        return self.x_backend == "api" and (
            self.has_x_oauth1() or bool(self.x_bearer_token)
        )
