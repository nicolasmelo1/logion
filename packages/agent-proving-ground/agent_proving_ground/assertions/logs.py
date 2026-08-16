from __future__ import annotations

import os
from pathlib import Path

from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class LogsNo500sAssertion(Assertion):
    type = "logs.no_500s"

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,  # noqa: ARG002
    ) -> AssertionOutcome:
        log_path = _find_log_path(ctx)
        if log_path is None:
            return _unsupported(self.type, "no API log available")
        read_result = _read_log(log_path)
        if read_result is None:
            return _unsupported(
                self.type, f"could not read log file: {log_path}"
            )
        text = read_result
        for line in text.splitlines():
            upper = line.upper()
            if any(marker in upper for marker in (" 500 ", 'HTTP/1.1" 500')):
                return AssertionOutcome(
                    type=self.type,
                    status="failed",
                    message="API log contains a 500 response",
                    evidence={"line": line[:200]},
                )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message="API log contains no obvious 500 responses",
            evidence={"log_path": str(log_path)},
        )


class LogsContainsRequestAssertion(Assertion):
    type = "logs.contains_request"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        log_path = _find_log_path(ctx)
        if log_path is None:
            return _unsupported(self.type, "no API log available")
        read_result = _read_log(log_path)
        if read_result is None:
            return _unsupported(
                self.type, f"could not read log file: {log_path}"
            )
        method = params.get("method", "GET")
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        text = read_result
        needle = f"{method.upper()} {path}"
        if needle in text:
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"log contains request: {needle}",
                evidence={"log_path": str(log_path)},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"log does not contain request: {needle}",
            evidence={"log_path": str(log_path)},
        )


def _find_log_path(ctx: AssertionContext) -> Path | None:
    artifacts_candidate = ctx.artifacts_dir / "services" / "api.log"
    if artifacts_candidate.is_file():
        return artifacts_candidate

    for devrig_dir in _devrig_dirs(ctx):
        for log_name in ("api.log", "prism.log"):
            devrig_log = devrig_dir / log_name
            if devrig_log.is_file():
                return devrig_log
    return None


def _devrig_dirs(ctx: AssertionContext) -> list[Path]:
    """Directories that may hold the running API's log.

    The dev rig does not have to live in the same checkout the run was
    pointed at: a scenario can run from this repo while the API and its
    log belong to the workspace that owns the rig. Looking only under the
    run root made `logs.no_500s` report `unsupported`, which a required
    assertion turns into a failure that looks like a 500 but is not one.
    """
    dirs: list[Path] = []
    # The role-keys file the run is already configured with sits in the
    # same `.devrig` the API writes its log into.
    role_keys = os.environ.get("LOGION_PROVING_GROUND_ROLE_KEYS_FILE")
    if role_keys:
        candidate = Path(role_keys).parent
        if candidate.is_dir() and candidate not in dirs:
            dirs.append(candidate)
    root_devrig = ctx.world.root_dir / ".devrig"
    if root_devrig.is_dir() and root_devrig not in dirs:
        dirs.append(root_devrig)
    return dirs


def _read_log(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _unsupported(type_: str, reason: str) -> AssertionOutcome:
    return AssertionOutcome(
        type=type_,
        status="unsupported",
        message=reason,
        evidence={},
    )
