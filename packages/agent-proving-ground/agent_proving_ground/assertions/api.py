from __future__ import annotations

from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class _ApiQueryAssertion(Assertion):
    """Shared evaluate loop for API-observed-effect assertions.

    Subclasses declare the query type, the result key that proves the
    effect, and pass/fail messages. Adapter capability gaps (query result
    carries ``unsupported``) surface as ``unsupported`` outcomes so the
    runner can apply the optional/required policy.
    """

    type = ""
    query_type = ""
    found_key = "found"
    evidence_keys: tuple[str, ...] = ()
    pass_message = ""  # nosec B105 - assertion copy, not a password.
    fail_message = ""
    # When True the assertion passes if the found_key value is falsy.
    invert = False

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": self.query_type, **params}
        )
        if result.get("unsupported"):
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message=result.get(
                    "reason", f"adapter does not support {self.query_type}"
                ),
                evidence={},
            )
        observed = bool(result.get(self.found_key))
        passed = (not observed) if self.invert else observed
        evidence = {
            key: result.get(key)
            for key in self.evidence_keys
            if result.get(key) is not None
        }
        if result.get("evidence"):
            evidence["query_evidence"] = result["evidence"]
        if passed:
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=self.pass_message,
                evidence=evidence,
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=self.fail_message,
            evidence={**params, **evidence},
        )


class CourseExistsAssertion(_ApiQueryAssertion):
    type = "api.course_exists"
    query_type = "course_exists"
    evidence_keys = ("course_id",)
    pass_message = "course exists"  # nosec B105 - assertion copy.
    fail_message = "no matching course found"


class PurchaseExistsAssertion(_ApiQueryAssertion):
    type = "api.purchase_exists"
    query_type = "purchase_exists"
    evidence_keys = ("purchase_id",)
    pass_message = "purchase exists"  # nosec B105 - assertion copy.
    fail_message = "no matching purchase found"


class ReviewExistsAssertion(_ApiQueryAssertion):
    type = "api.review_exists"
    query_type = "review_exists"
    evidence_keys = ("review_id",)
    pass_message = "review exists"  # nosec B105 - assertion copy.
    fail_message = "no matching review found"


class UsageReportExistsAssertion(_ApiQueryAssertion):
    type = "api.usage_report_exists"
    query_type = "usage_report_exists"
    evidence_keys = ("report_id",)
    pass_message = "usage report exists"  # nosec B105 - assertion copy.
    fail_message = "no matching usage report found"


class BountyExistsAssertion(_ApiQueryAssertion):
    type = "api.bounty_exists"
    query_type = "bounty_exists"
    evidence_keys = ("bounty_id",)
    pass_message = "bounty exists"  # nosec B105 - assertion copy.
    fail_message = "no matching bounty found"


class BountySubmissionExistsAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_exists"
    query_type = "bounty_submission_exists"
    evidence_keys = ("submission_id",)
    pass_message = "bounty submission exists"  # nosec B105 - assertion copy.
    fail_message = "no matching bounty submission found"


class BountyAcceptedAssertion(_ApiQueryAssertion):
    type = "api.bounty_accepted"
    query_type = "bounty_accepted"
    evidence_keys = ("submission_id", "bounty_id")
    pass_message = "bounty submission accepted"  # nosec B105 - assertion copy.
    fail_message = "no accepted bounty submission found"


class CreditBalanceChangedAssertion(_ApiQueryAssertion):
    type = "api.credit_balance_changed"
    query_type = "credit_balance_changed"
    found_key = "changed"
    pass_message = "credit balance changed"  # nosec B105 - assertion copy.
    fail_message = "credit balance did not change"


class NoDoubleCreditDebitAssertion(_ApiQueryAssertion):
    type = "api.no_double_credit_debit"
    query_type = "no_double_credit_debit"
    found_key = "double_debit_found"
    invert = True
    pass_message = "no double credit debit found"  # nosec B105 - assertion copy.
    fail_message = "double credit debit detected"


class CourseRemainsPurchasableAssertion(_ApiQueryAssertion):
    type = "api.course_remains_purchasable"
    query_type = "course_remains_purchasable"
    found_key = "purchasable"
    evidence_keys = ("course_id",)
    pass_message = "course remains purchasable"  # nosec B105 - assertion copy.
    fail_message = "no published purchasable course found"


class AdminStateObservedAssertion(_ApiQueryAssertion):
    type = "api.admin_state_observed"
    query_type = "admin_state_observed"
    pass_message = "admin/operator view observed consistent state"  # nosec B105
    fail_message = "admin state could not be observed"


class SourceLinkExistsAssertion(_ApiQueryAssertion):
    type = "api.source_link_exists"
    query_type = "source_link_exists"
    evidence_keys = ("course_id",)
    pass_message = "source link exists"
    fail_message = "no matching source link found"


class BountySubmissionPrOpenedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_pr_opened"
    query_type = "bounty_submission_pr_opened"
    found_key = "opened"
    evidence_keys = ("submission_id", "pr_url")
    pass_message = "bounty submission PR is opened"
    fail_message = "bounty submission PR is not opened"


class BountySubmissionAcceptedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_accepted"
    query_type = "bounty_submission_accepted"
    found_key = "accepted"
    pass_message = "bounty submission is accepted"
    fail_message = "bounty submission is not accepted"


class BountySubmissionRejectedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_rejected"
    query_type = "bounty_submission_rejected"
    found_key = "rejected"
    pass_message = "bounty submission is rejected"
    fail_message = "bounty submission is not rejected"
