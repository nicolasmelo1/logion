"""Plain data models shared across clients."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PostDraft(BaseModel):
    """A unit of content the operator/agent wants to publish."""

    platform: str  # "discord" | "x"
    target: str  # discord channel name, or "x"
    text: str
    has_link: bool = False  # populated by CostEstimator for X
    source_file: str | None = None  # path in content/ if queued


class CostEstimate(BaseModel):
    """Estimated cost of a single X write."""

    cents: int  # 2 (no link) or 20 (link), per cost.py
    has_link: bool
    reason: str  # human explanation, shown in --dry-run

    @property
    def dollars(self) -> str:
        return f"${self.cents / 100:.2f}"


class PostResult(BaseModel):
    """Outcome of an attempted (or dry-run) post."""

    platform: str
    target: str
    dry_run: bool
    sent: bool
    cost_cents: int = 0  # 0 for discord
    remote_id: str | None = None  # tweet id / discord message id
    rendered: str | None = None  # the exact body, for manual fallback
    note: str | None = None


class RecentMessage(BaseModel):
    """A read-only Discord message for triage."""

    id: str
    author: str
    content: str
    created_at: datetime
