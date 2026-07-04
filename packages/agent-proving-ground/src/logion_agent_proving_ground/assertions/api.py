from __future__ import annotations

from logion_agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class CourseExistsAssertion(Assertion):
    type = "api.course_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "course_exists", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="course exists",
                evidence={"course_id": result.get("course_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching course found",
            evidence=params,
        )


class PurchaseExistsAssertion(Assertion):
    type = "api.purchase_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "purchase_exists", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="purchase exists",
                evidence={"purchase_id": result.get("purchase_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching purchase found",
            evidence=params,
        )


class ReviewExistsAssertion(Assertion):
    type = "api.review_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "review_exists", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="review exists",
                evidence={"review_id": result.get("review_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching review found",
            evidence=params,
        )


class UsageReportExistsAssertion(Assertion):
    type = "api.usage_report_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "usage_report_exists", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="usage report exists",
                evidence={"report_id": result.get("report_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching usage report found",
            evidence=params,
        )


class BountyExistsAssertion(Assertion):
    type = "api.bounty_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "bounty_exists", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="bounty exists",
                evidence={"bounty_id": result.get("bounty_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching bounty found",
            evidence=params,
        )


class BountySubmissionExistsAssertion(Assertion):
    type = "api.bounty_submission_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world,
            {"type": "bounty_submission_exists", **params},
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="bounty submission exists",
                evidence={"submission_id": result.get("submission_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no matching bounty submission found",
            evidence=params,
        )


class BountyAcceptedAssertion(Assertion):
    type = "api.bounty_accepted"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "bounty_accepted", **params}
        )
        if result.get("found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="bounty submission accepted",
                evidence={"submission_id": result.get("submission_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no accepted bounty submission found",
            evidence=params,
        )


class CreditBalanceChangedAssertion(Assertion):
    type = "api.credit_balance_changed"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": "credit_balance_changed", **params}
        )
        if result.get("changed"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="credit balance changed",
                evidence={},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="credit balance did not change",
            evidence=params,
        )


class NoDoubleCreditDebitAssertion(Assertion):
    type = "api.no_double_credit_debit"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world,
            {"type": "no_double_credit_debit", **params},
        )
        if not result.get("double_debit_found"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="no double credit debit found",
                evidence={},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="double credit debit detected",
            evidence=params,
        )


class CourseRemainsPurchasableAssertion(Assertion):
    type = "api.course_remains_purchasable"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world,
            {"type": "course_remains_purchasable", **params},
        )
        if result.get("purchasable"):
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="course remains purchasable",
                evidence={"course_id": result.get("course_id")},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="no published purchasable course found",
            evidence=params,
        )
