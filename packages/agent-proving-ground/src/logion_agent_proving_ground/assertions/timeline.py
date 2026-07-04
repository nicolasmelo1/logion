from __future__ import annotations

from logion_agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)
from logion_agent_proving_ground.redaction import redact_text


class TimelineNoUnredactedSecretAssertion(Assertion):
    type = "timeline.no_unredacted_secret"

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,  # noqa: ARG002
    ) -> AssertionOutcome:
        timeline_path = ctx.artifacts_dir / "timeline.jsonl"
        if not timeline_path.exists():
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message="no timeline file to inspect",
                evidence={},
            )
        text = timeline_path.read_text(encoding="utf-8")
        for line in text.splitlines():
                return AssertionOutcome(
                    type=self.type,
                    status="failed",
                    message="timeline contains unredacted secret-like value",
                    evidence={"line": redact_text(line)[:200]},
                )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message="timeline contains no obvious unredacted secrets",
            evidence={},
        )
