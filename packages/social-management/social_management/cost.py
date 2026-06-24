"""X cost estimation + a local month-to-date spend ledger.

Pricing constants reflect X pay-per-use as researched Jun 2026. They are
the ONLY place magic numbers live; tests assert against them.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from social_management.errors import BudgetExceededError
from social_management.models import CostEstimate

POST_COST_CENTS = 2  # ~$0.015 rounded up to 2c
POST_WITH_LINK_COST_CENTS = 20  # ~$0.20 link tax
READ_COST_CENTS = 1  # ~$0.005 rounded up; reads are not gated, FYI

# Matches http(s):// and bare domains likely to be unfurled by X.
_URL_RE = re.compile(
    r"(https?://\S+|\bwww\.\S+|\b[a-z0-9.-]+\.(?:com|sh|io|org|net|dev)\b)",
    re.IGNORECASE,
)


class CostEstimator:
    """Pure-function cost model — no I/O, trivially testable."""

    @staticmethod
    def has_link(text: str) -> bool:
        return _URL_RE.search(text) is not None

    @classmethod
    def estimate(cls, text: str) -> CostEstimate:
        """Return the cost of posting `text` to X.

        20c if the body contains any URL/domain, else 2c.
        """
        if cls.has_link(text):
            return CostEstimate(
                cents=POST_WITH_LINK_COST_CENTS,
                has_link=True,
                reason="contains a link → ~$0.20 link tax"
                " (put link in a reply)",
            )
        return CostEstimate(
            cents=POST_COST_CENTS,
            has_link=False,
            reason="link-free body → ~$0.015",
        )


class SpendLedger:
    """JSON file tracking month-to-date X spend, keyed by 'YYYY-MM'.

    File shape: {"2026-06": 42, "2026-05": 118}  (cents per month)
    Default location: ./.spend-ledger.json (git-ignored).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(".spend-ledger.json")

    def _data(self) -> dict[str, int]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    @staticmethod
    def _month_key() -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    def month_to_date_cents(self) -> int:
        return self._data().get(self._month_key(), 0)

    def check_and_reserve(
        self, estimate: CostEstimate, budget_cents: int
    ) -> None:
        """Raise BudgetExceededError if this post would breach the cap.

        Does NOT write — call record() only after a real send succeeds.
        """
        spent = self.month_to_date_cents()
        if spent + estimate.cents > budget_cents:
            raise BudgetExceededError(
                estimate_cents=estimate.cents,
                spent_cents=spent,
                budget_cents=budget_cents,
            )

    def record(self, estimate: CostEstimate) -> None:
        """Add a successful post's cost to the current month."""
        data = self._data()
        key = self._month_key()
        data[key] = data.get(key, 0) + estimate.cents
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))
