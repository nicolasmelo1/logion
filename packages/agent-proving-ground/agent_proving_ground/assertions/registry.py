from __future__ import annotations

from agent_proving_ground.assertions.api import (
    AcquisitionIdempotentAssertion,
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
    HarnessInventoryDistinctScopesAssertion,
    HarnessScopeNestedRepoAssertion,
    HarnessScopeTargetsResolvedAssertion,
    IndexedListingExistsAssertion,
    IndexedListingTierAssertion,
    InstalledArtifactDigestMatchesAssertion,
    InventoryReceiptMatchesAssertion,
    LegacyCoursePurchaseExistsAssertion,
    NativeInstallReconciledAssertion,
    NoDoubleCreditDebitAssertion,
    ObservationEnvelopeNoRawDataAssertion,
    PlatformBountyAcceptedAssertion,
    PurchaseExistsAssertion,
    ResourceAcquirePlanDryRunAssertion,
    ResourceAcquisitionExistsAssertion,
    ResourceBackfillAppliedAssertion,
    ResourceBackfillCompleteAssertion,
    ResourceBackfillIdempotentAssertion,
    ResourceDistributionSelectedAssertion,
    ResourceIdentityUniqueAssertion,
    ResourceProjectionExistsAssertion,
    ResourceSearchReturnsKindsAssertion,
    ReviewExistsAssertion,
    SetupTokenPendingAssertion,
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
            NativeInstallReconciledAssertion,
            PurchaseExistsAssertion,
            ResourceAcquisitionExistsAssertion,
            ResourceDistributionSelectedAssertion,
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
            SetupTokenPendingAssertion,
            BountySubmissionPrOpenedAssertion,
            BountySubmissionAcceptedAssertion,
            BountySubmissionRejectedAssertion,
            IndexedListingExistsAssertion,
            InstalledArtifactDigestMatchesAssertion,
            InventoryReceiptMatchesAssertion,
            IndexedListingTierAssertion,
            PlatformBountyAcceptedAssertion,
            GithubPrExistsAssertion,
            GithubPrMergedAssertion,
            GithubPrClosedUnmergedAssertion,
            GithubIssueBotCommentMatchAssertion,
            GithubInstallationDeliveredAssertion,
            ResourceProjectionExistsAssertion,
            ResourceBackfillAppliedAssertion,
            ResourceBackfillCompleteAssertion,
            ResourceBackfillIdempotentAssertion,
            ResourceIdentityUniqueAssertion,
            ResourceSearchReturnsKindsAssertion,
            LegacyCoursePurchaseExistsAssertion,
            HarnessScopeTargetsResolvedAssertion,
            ResourceAcquirePlanDryRunAssertion,
            HarnessScopeNestedRepoAssertion,
            HarnessInventoryDistinctScopesAssertion,
            ObservationEnvelopeNoRawDataAssertion,
            ResourceAcquisitionExistsAssertion,
            ResourceDistributionSelectedAssertion,
            NativeInstallReconciledAssertion,
            InventoryReceiptMatchesAssertion,
            InstalledArtifactDigestMatchesAssertion,
            AcquisitionIdempotentAssertion,
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
