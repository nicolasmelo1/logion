"""Local month-to-date spend ledger for X posts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from social_management.core.constants import SPEND_LEDGER_FILE
from social_management.core.errors import BudgetExceededError
from social_management.x.models import CostEstimate


class SpendLedger:
    """JSON file tracking month-to-date X spend, keyed by 'YYYY-MM'.

    File shape: {"2026-06": 42, "2026-05": 118}  (cents per month)
    Default location: ./.spend-ledger.json (git-ignored).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(SPEND_LEDGER_FILE)

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
