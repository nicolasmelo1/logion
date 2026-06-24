"""Exception hierarchy for social-management."""

from __future__ import annotations


class SocialError(Exception):
    """Base class for all social-management errors."""


class MissingCredentialsError(SocialError):
    """A backend was asked to act but its credentials are absent.

    Callers catch this to fall back to manual-render mode rather than
    crash.
    """


class BudgetExceededError(SocialError):
    """A post would push estimated month-to-date X spend past the cap.

    Carries the numbers so the CLI can print an actionable message.
    """

    def __init__(
        self,
        *,
        estimate_cents: int,
        spent_cents: int,
        budget_cents: int,
    ) -> None:
        self.estimate_cents = estimate_cents
        self.spent_cents = spent_cents
        self.budget_cents = budget_cents
        super().__init__(
            f"X post would cost {estimate_cents}c; "
            f"month-to-date {spent_cents}c + {estimate_cents}c "
            f"exceeds cap {budget_cents}c"
        )


class ConfirmationRequiredError(SocialError):
    """A paid/irreversible action was attempted without --confirm."""
