from __future__ import annotations

from agent_proving_ground.artifacts import resolve_artifact_path
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class FileExistsAssertion(Assertion):
    type = "files.exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        try:
            target = resolve_artifact_path(ctx.artifacts_dir, path)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"path": path},
            )
        if target.exists():
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"file exists: {path}",
                evidence={"path": str(target)},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"file missing: {path}",
            evidence={"path": str(target)},
        )
