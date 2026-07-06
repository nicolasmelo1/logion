from __future__ import annotations

from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class DbRowExistsAssertion(Assertion):
    type = "db.row_exists"

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,  # noqa: ARG002
    ) -> AssertionOutcome:
        if not _has_db_observer(ctx):
            return _unsupported(self.type, "no DB observer configured")
        return _unsupported(
            self.type, "db.row_exists query not yet implemented"
        )


class DbExactCreditLedgerAssertion(Assertion):
    type = "db.exact_credit_ledger"

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,  # noqa: ARG002
    ) -> AssertionOutcome:
        if not _has_db_observer(ctx):
            return _unsupported(self.type, "no DB observer configured")
        return _unsupported(
            self.type, "db.exact_credit_ledger query not yet implemented"
        )


class EventsOutboxContainsAssertion(Assertion):
    type = "events.outbox_contains"

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,  # noqa: ARG002
    ) -> AssertionOutcome:
        if not _has_db_observer(ctx):
            return _unsupported(self.type, "no DB observer configured")
        return _unsupported(
            self.type, "events.outbox_contains query not yet implemented"
        )


def _has_db_observer(ctx: AssertionContext) -> bool:
    """Return True when the world data advertises an available DB observer."""
    data = ctx.world.data or {}
    observer = data.get("observer") or {}
    return bool(observer.get("db_url"))


def _unsupported(type_: str, reason: str) -> AssertionOutcome:
    return AssertionOutcome(
        type=type_,
        status="unsupported",
        message=reason,
        evidence={},
    )
