from __future__ import annotations

from logion_agent_proving_ground.assertions.api import (
    AdminStateObservedAssertion,
    BountyAcceptedAssertion,
    BountyExistsAssertion,
    BountySubmissionExistsAssertion,
    CourseExistsAssertion,
    CourseRemainsPurchasableAssertion,
    CreditBalanceChangedAssertion,
    NoDoubleCreditDebitAssertion,
    PurchaseExistsAssertion,
    ReviewExistsAssertion,
    UsageReportExistsAssertion,
)
from logion_agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)
from logion_agent_proving_ground.assertions.db import (
    DbExactCreditLedgerAssertion,
    DbRowExistsAssertion,
    EventsOutboxContainsAssertion,
)
from logion_agent_proving_ground.assertions.files import FileExistsAssertion
from logion_agent_proving_ground.assertions.logs import (
    LogsContainsRequestAssertion,
    LogsNo500sAssertion,
)
from logion_agent_proving_ground.assertions.timeline import (
    TimelineNoUnredactedSecretAssertion,
)


class AssertionRegistry:
    def __init__(self) -> None:
        self._assertions: dict[str, Assertion] = {}
        self._register_builtin()

    def _register_builtin(self) -> None:
        for cls in (
            CourseExistsAssertion,
            PurchaseExistsAssertion,
            ReviewExistsAssertion,
            UsageReportExistsAssertion,
            BountyExistsAssertion,
            BountySubmissionExistsAssertion,
            BountyAcceptedAssertion,
            CreditBalanceChangedAssertion,
            NoDoubleCreditDebitAssertion,
            CourseRemainsPurchasableAssertion,
            AdminStateObservedAssertion,
            TimelineNoUnredactedSecretAssertion,
            FileExistsAssertion,
            LogsNo500sAssertion,
            LogsContainsRequestAssertion,
            DbRowExistsAssertion,
            DbExactCreditLedgerAssertion,
            EventsOutboxContainsAssertion,
        ):
            instance = cls()
            self._assertions[instance.type] = instance

    async def evaluate(
        self,
        ctx: AssertionContext,
        type_: str,
        params: dict,
    ) -> AssertionOutcome:
        assertion = self._assertions.get(type_)
        if assertion is None:
            return AssertionOutcome(
                type=type_,
                status="unsupported",
                message=f"assertion type {type_} is not registered",
                evidence={},
            )
        return await assertion.evaluate(ctx, params)
