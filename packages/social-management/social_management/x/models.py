"""Models for the X / Twitter domain."""

from __future__ import annotations

from pydantic import BaseModel


class CostEstimate(BaseModel):
    """Estimated cost of a single X write."""

    cents: int  # 2 (no link) or 20 (link), per cost constants
    has_link: bool
    reason: str  # human explanation, shown in --dry-run

    @property
    def dollars(self) -> str:
        return f"${self.cents / 100:.2f}"
