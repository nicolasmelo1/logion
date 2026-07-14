"""GitHub-observed assertions for proving-ground scenarios."""

from __future__ import annotations

import re
from typing import Any

from agent_proving_ground.api_adapters.github_observer import (
    GithubObserver,
)
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class _GithubAssertionBase(Assertion):
    """Shared logic for GitHub-observed assertions."""

    type = ""
    optional = False

    def _observer(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> GithubObserver | None:
        repo = params.get("repository") or ""
        role = params.get("role", "creator")
        env_repo = ctx.world.data.get("gh_repo") if ctx.world.data else ""
        return GithubObserver.from_env(role=role, repo=repo or env_repo or "")


class GithubPrExistsAssertion(_GithubAssertionBase):
    type = "github.pr_exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> AssertionOutcome:
        observer = self._observer(ctx, params)
        if observer is None:
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message="GitHub token or repo not configured",
                evidence={},
            )
        marker = params.get("marker")
        head_branch = params.get("head_branch")
        pr = observer.pr_exists(head_branch=head_branch, marker=marker)
        if pr is not None:
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="PR exists on GitHub",
                evidence={
                    "pr_number": pr.get("number"),
                    "pr_url": pr.get("html_url"),
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="No matching PR found on GitHub",
            evidence={**params},
        )


class GithubPrMergedAssertion(_GithubAssertionBase):
    type = "github.pr_merged"

    async def evaluate(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> AssertionOutcome:
        observer = self._observer(ctx, params)
        if observer is None:
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message="GitHub token or repo not configured",
                evidence={},
            )
        pr_number = int(params.get("pr_number", 0))
        if not pr_number:
            marker = params.get("marker")
            pr = observer.pr_exists(marker=marker)
            if pr is not None:
                pr_number = int(pr.get("number", 0))
        if not pr_number:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="No PR number provided or found",
                evidence={**params},
            )
        state = observer.pr_state(pr_number)
        if state == "merged":
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"PR #{pr_number} is merged",
                evidence={"pr_number": pr_number, "state": state},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"PR #{pr_number} is {state}, not merged",
            evidence={"pr_number": pr_number, "state": state},
        )


class GithubPrClosedUnmergedAssertion(_GithubAssertionBase):
    type = "github.pr_closed_unmerged"

    async def evaluate(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> AssertionOutcome:
        observer = self._observer(ctx, params)
        if observer is None:
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message="GitHub token or repo not configured",
                evidence={},
            )
        pr_number = int(params.get("pr_number", 0))
        if not pr_number:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="No PR number provided",
                evidence={**params},
            )
        state = observer.pr_state(pr_number)
        if state == "closed":
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"PR #{pr_number} is closed (not merged)",
                evidence={"pr_number": pr_number, "state": state},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"PR #{pr_number} is {state}, not closed-unmerged",
            evidence={"pr_number": pr_number, "state": state},
        )


class GithubIssueBotCommentMatchAssertion(_GithubAssertionBase):
    type = "github.issue_bot_comment_matches"

    async def evaluate(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> AssertionOutcome:
        observer = self._observer(ctx, params)
        if observer is None:
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message="GitHub token or repo not configured",
                evidence={},
            )
        issue_number = int(params.get("issue", 0))
        pattern = params.get("pattern", "")
        if not issue_number or not pattern:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="Missing issue number or pattern",
                evidence={**params},
            )
        comments = observer.issue_comments(issue_number)
        bot_suffix = "[bot]"
        regex = re.compile(pattern, re.IGNORECASE)
        for comment in comments:
            author = str(comment.get("user", {}).get("login", ""))
            body = str(comment.get("body", ""))
            if author.endswith(bot_suffix) and regex.search(body):
                return AssertionOutcome(
                    type=self.type,
                    status="passed",
                    message=(
                        f"Bot comment matches pattern on issue #{issue_number}"
                    ),
                    evidence={
                        "issue": issue_number,
                        "author": author,
                        "pattern": pattern,
                    },
                )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message="No matching bot comment found",
            evidence={**params},
        )


class GithubInstallationDeliveredAssertion(_GithubAssertionBase):
    type = "github.installation_delivered"
    optional = True

    async def evaluate(
        self, ctx: AssertionContext, params: dict[str, Any]
    ) -> AssertionOutcome:
        observer = self._observer(ctx, params)
        if observer is None:
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message="GitHub token or repo not configured",
                evidence={},
            )
        return AssertionOutcome(
            type=self.type,
            status="unsupported",
            message="Installation delivery requires GitHub App admin access",
            evidence={},
        )
