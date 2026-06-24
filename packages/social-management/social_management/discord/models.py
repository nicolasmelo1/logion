"""Models for the Discord domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RecentMessage(BaseModel):
    """A read-only Discord message for triage."""

    id: str
    author: str
    content: str
    created_at: datetime
