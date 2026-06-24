"""X cost estimation — pure-function cost model, no I/O."""

from __future__ import annotations

from social_management.cost.constants import (
    POST_COST_CENTS,
    POST_WITH_LINK_COST_CENTS,
    URL_RE,
)
from social_management.x.models import CostEstimate


class CostEstimator:
    """Pure-function cost model — no I/O, trivially testable."""

    @staticmethod
    def has_link(text: str) -> bool:
        return URL_RE.search(text) is not None

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
