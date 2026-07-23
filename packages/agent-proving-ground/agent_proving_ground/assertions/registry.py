from __future__ import annotations

from agent_proving_ground.assertions.api import (
    AdminStateObservedAssertion,
    BountyAcceptedAssertion,
    BountyExistsAssertion,
    BountySubmissionAcceptedAssertion,
    BountySubmissionExistsAssertion,
    BountySubmissionPrOpenedAssertion,
    BountySubmissionRejectedAssertion,
    CourseExistsAssertion,
    CourseRemainsPurchasableAssertion,
    CreditBalanceChangedAssertion,
    GithubIdentityLinkedAssertion,
    NoDoubleCreditDebitAssertion,
    PurchaseExistsAssertion,
    ReviewExistsAssertion,
    SourceLinkExistsAssertion,
    UsageReportExistsAssertion,
)
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)
from agent_proving_ground.assertions.db import (
    DbExactCreditLedgerAssertion,
    DbRowExistsAssertion,
    EventsOutboxContainsAssertion,
)
from agent_proving_ground.assertions.files import FileExistsAssertion
from agent_proving_ground.assertions.github import (
    GithubInstallationDeliveredAssertion,
    GithubIssueBotCommentMatchAssertion,
    GithubPrClosedUnmergedAssertion,
    GithubPrExistsAssertion,
    GithubPrMergedAssertion,
)
from agent_proving_ground.assertions.logs import (
    LogsContainsRequestAssertion,
    LogsNo500sAssertion,
)
from agent_proving_ground.assertions.timeline import (
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
            GithubIdentityLinkedAssertion,
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
            SourceLinkExistsAssertion,
            BountySubmissionPrOpenedAssertion,
            BountySubmissionAcceptedAssertion,
            BountySubmissionRejectedAssertion,
            GithubPrExistsAssertion,
            GithubPrMergedAssertion,
            GithubPrClosedUnmergedAssertion,
            GithubIssueBotCommentMatchAssertion,
            GithubInstallationDeliveredAssertion,
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
