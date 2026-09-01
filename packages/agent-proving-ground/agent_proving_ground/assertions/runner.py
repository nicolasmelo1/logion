from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, cast

from agent_proving_ground.assertions.base import Assertion, AssertionContext
from agent_proving_ground.models import AssertionOutcome

_CANARY_ROLES = (
    "host_home",
    "cloud_metadata",
    "coordinator_token",
    "canary_env",
    "etc_shadow",
    "parent_path",
)
_EFFECT_ROLES = (
    "filesystem_escape",
    "undeclared_network",
    "secret_read",
    "oversized_output",
    "timeout_ignoring_sigterm",
)
_HAZARD_ROLES = (
    "cancellation",
    "timeout",
    "lease_loss",
    "retry",
    "duplicate_submission",
)


def _manifest(ctx: AssertionContext, params: dict) -> dict[str, object]:
    raw = params.get("manifest")
    if not isinstance(raw, str) or not raw:
        raise ValueError("manifest parameter is required")
    target = Path(raw)
    if not target.is_absolute():
        target = (ctx.artifacts_dir / target).resolve()
    target.relative_to(ctx.artifacts_dir.resolve())
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("runner evidence is not an object")
    return value


def _typed_facts(
    payload: dict[str, object], assertion: str | None = None
) -> dict[str, object]:
    """Return the typed facts this assertion owns.

    Three 15.15 contracts name a fact ``terminal_status`` over three
    different keyspaces, so the manifest is scoped by assertion type. A
    flat manifest is still read, for evidence sealed before the scoping.
    """
    facts = payload.get("facts")
    if not isinstance(facts, dict):
        raise TypeError("runner evidence carries no typed facts")
    if assertion is not None and assertion in facts:
        scoped = facts[assertion]
        if not isinstance(scoped, dict):
            raise TypeError(f"{assertion} evidence is not an object")
        return cast(dict[str, object], scoped)
    return cast(dict[str, object], facts)


def _value(facts: dict[str, object], name: str) -> tuple[bool, object]:
    fact = facts.get(name)
    if (
        not isinstance(fact, dict)
        or fact.get("ok") is not True
        or "value" not in fact
    ):
        return False, None
    return True, fact["value"]


def _check(
    facts: dict[str, object],
    required: tuple[str, ...],
    expected: dict[str, object] | None = None,
    roles: tuple[str, ...] | None = None,
    forbidden: tuple[object, ...] = (),
) -> tuple[bool, dict[str, object], str]:
    evidence: dict[str, object] = {}
    errors: list[str] = []
    expected = expected or {}
    for name in required:
        ok, value = _value(facts, name)
        evidence[name] = {"ok": ok, "value": value}
        if not ok:
            errors.append(name)
            continue
        if name in expected and value != expected[name]:
            errors.append(name)
        if forbidden and _contains_forbidden(value, forbidden):
            errors.append(name)
        if roles is not None and (
            not isinstance(value, dict) or set(value) != set(roles)
        ):
            errors.append(f"{name}:roles")
    return not errors, evidence, ", ".join(errors)


def _contains_forbidden(value: object, forbidden: tuple[object, ...]) -> bool:
    """Mirror the auditor's forbidden-values predicate, leaf by leaf.

    Placeholder sentinels live in the same tuple as booleans the honest run
    legitimately produces, and ``0 == False`` in Python. Reject a leaf only
    when its Python type matches the sentinel's exactly, so the typed zero
    ``verify_exit_code: 0`` and the honest ``accepted_as_late_evidence:
    False`` survive while a bare ``None`` or ``""`` still fails closed.
    """
    if not isinstance(value, (dict, list)) and any(
        type(value) is type(item) and value == item for item in forbidden
    ):
        return True
    if isinstance(value, dict):
        return any(
            _contains_forbidden(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden(item, forbidden) for item in value)
    return False


def _fact_map(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


class _RunnerFactsAssertion(Assertion):
    required: ClassVar[tuple[str, ...]] = ()
    expected: ClassVar[dict[str, object]] = {}
    roles: ClassVar[tuple[str, ...] | None] = None
    forbidden: ClassVar[tuple[object, ...]] = (
        None,
        False,
        "",
        "none",
        "unknown",
        "unavailable",
    )
    success_message = "runner evidence satisfies the contract"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            payload = _manifest(ctx, params)
            facts = _typed_facts(payload, self.type)
            passed, evidence, errors = _check(
                facts,
                self.required,
                self.expected,
                self.roles,
                self.forbidden,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"runner evidence unreadable: {exc}",
                evidence=params,
            )
        return AssertionOutcome(
            type=self.type,
            status="passed" if passed else "failed",
            message=self.success_message
            if passed
            else f"runner evidence failed: {errors}",
            evidence=evidence,
        )


class RunnerEnrolledAssertion(_RunnerFactsAssertion):
    type = "api.runner_enrolled"
    required = (
        "runner_id",
        "runner_key_fingerprint",
        "runner_import_root",
        "runner_credential_kind",
        "runner_package_version",
    )
    expected: ClassVar[dict[str, object]] = {
        "runner_import_root": "site-packages",
        "runner_credential_kind": "runner",
    }


class RunnerJobCompletedAssertion(_RunnerFactsAssertion):
    type = "api.runner_job_completed"
    required = (
        "job_id",
        "terminal_status",
        "attempt_count",
        "uploaded_artifact_digest",
        "coordinator_artifact_digest",
        "lease_holder",
    )
    expected: ClassVar[dict[str, object]] = {
        "terminal_status": "succeeded",
        "attempt_count": 1,
    }


class RunnerReceiptPublishedAssertion(_RunnerFactsAssertion):
    type = "api.runner_receipt_published"
    required = (
        "receipt_id",
        "receipt_digest",
        "coordinator_accepted",
        "accepted_as_late_evidence",
        "published_at",
    )
    expected: ClassVar[dict[str, object]] = {
        "coordinator_accepted": True,
        "accepted_as_late_evidence": False,
    }
    # The policy deliberately drops `false` from this list: an honest run's
    # late-evidence flag is false, and a false pass is rejected by the
    # expected-values check below instead.
    forbidden = (None, "", "none", "unknown", "unavailable")


class RunnerReceiptValidAssertion(_RunnerFactsAssertion):
    type = "crypto.runner_receipt_valid"
    required = (
        "canonicalization",
        "signature_algorithm",
        "signing_key_fingerprint",
        "verify_exit_code",
        "bound_input_digest",
        "bound_image_digest",
        "bound_output_digest",
        "bound_assertion_vector_digest",
    )
    expected: ClassVar[dict[str, object]] = {
        "canonicalization": "JCS",
        "verify_exit_code": 0,
    }
    # verify_exit_code is legitimately 0; only placeholders are forbidden.
    forbidden = (None, False, "", "none", "unknown", "unavailable")


class CanaryNotExfiltratedAssertion(_RunnerFactsAssertion):
    type = "sandbox.canary_not_exfiltrated"
    required = (
        "canary_readable",
        "canary_in_artifacts",
        "canary_in_receipt",
        "canary_in_logs",
    )
    expected: ClassVar[dict[str, object]] = {
        name: dict.fromkeys(_CANARY_ROLES, False) for name in required
    }
    roles = _CANARY_ROLES
    # All-False is the boundary holding; `true` is the only leaf that means
    # the canary saw something it must not, and ``false`` is required.
    forbidden = (True, None, "", "none", "unknown", "unavailable")


class ForbiddenEffectBlockedAssertion(_RunnerFactsAssertion):
    type = "sandbox.forbidden_effect_blocked"
    required = (
        "effect_attempted",
        "effect_blocked",
        "terminal_status",
        "sandbox_profile_digest",
    )
    roles = _EFFECT_ROLES

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, attempted = _value(facts, "effect_attempted")
        _, blocked = _value(facts, "effect_blocked")
        _, statuses = _value(facts, "terminal_status")
        _, profiles = _value(facts, "sandbox_profile_digest")
        attempted_map = _fact_map(attempted)
        blocked_map = _fact_map(blocked)
        statuses_map = _fact_map(statuses)
        profiles_map = _fact_map(profiles)
        valid = (
            all(attempted_map.values())
            and all(blocked_map.values())
            and all(
                statuses_map.get(role)
                in {"failed", "timed_out", "inconclusive"}
                for role in _EFFECT_ROLES
            )
            and all(profiles_map.values())
        )
        result.status = "passed" if valid else "failed"
        result.message = (
            "adversarial effects were attempted and blocked"
            if valid
            else "runner evidence failed: containment"
        )
        return result


class RunnerJobTerminalOnceAssertion(_RunnerFactsAssertion):
    type = "api.runner_job_terminal_once"
    required = (
        "terminal_transition_count",
        "terminal_status",
        "duplicate_receipt_rejected",
        "attempt_count",
    )
    roles = _HAZARD_ROLES

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, counts = _value(facts, "terminal_transition_count")
        _, statuses = _value(facts, "terminal_status")
        _, duplicate = _value(facts, "duplicate_receipt_rejected")
        counts_map = _fact_map(counts)
        statuses_map = _fact_map(statuses)
        duplicate_map = _fact_map(duplicate)
        valid = (
            all(value == 1 for value in counts_map.values())
            and all(statuses_map.values())
            and all(duplicate_map.values())
        )
        result.status = "passed" if valid else "failed"
        result.message = (
            "each lifecycle hazard reached one terminal state"
            if valid
            else "runner evidence failed: terminal transition safety"
        )
        return result
