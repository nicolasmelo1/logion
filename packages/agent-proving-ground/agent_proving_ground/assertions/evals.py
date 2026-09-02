"""Assertion handlers for the 16.1 eval-contract evidence.

The evidence driver retains one typed-facts JSON file per assertion; these
handlers recompute the predicates from the manifest params the scenario
declares. Nothing here trusts a captured ``passed``: every fact is an
``{"ok": true, "value": ...}`` envelope the run produced, and the checks
below re-derive the verdict from those values — the same shape the 15.15
runner handlers audit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, cast

from agent_proving_ground.assertions.base import Assertion, AssertionContext
from agent_proving_ground.models import AssertionOutcome

#: The five stable error codes the shared library defines and the private
#: API returns as 422; the rejection assertion is keyed by exactly these.
EVAL_REJECTION_ROLES = (
    "eval_contract_invalid",
    "eval_subject_mismatch",
    "eval_requirement_unsupported",
    "eval_fixture_digest_mismatch",
    "eval_budget_invalid",
)

_CONTRACT_STANDINGS = (
    "unreviewed",
    "contested",
    "reproduced",
    "superseded",
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
        raise TypeError("eval evidence is not an object")
    return value


def _typed_facts(
    payload: dict[str, object], assertion: str | None = None
) -> dict[str, object]:
    """Return the typed facts this assertion owns.

    The manifest is scoped by assertion type — two 16.1 contracts name a
    fact ``contract_digest`` over different keyspaces — with a flat
    manifest still read, for evidence sealed before the scoping.
    """
    facts = payload.get("facts")
    if not isinstance(facts, dict):
        raise TypeError("eval evidence carries no typed facts")
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
        if roles is not None and (
            not isinstance(value, dict) or set(value) != set(roles)
        ):
            errors.append(f"{name}:roles")
    return not errors, evidence, ", ".join(errors)


def _fact_map(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


class _EvalFactsAssertion(Assertion):
    """Shared evaluate loop for manifest-backed eval facts assertions."""

    required: ClassVar[tuple[str, ...]] = ()
    expected: ClassVar[dict[str, object]] = {}
    roles: ClassVar[tuple[str, ...] | None] = None
    success_message = "eval evidence satisfies the contract"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            payload = _manifest(ctx, params)
            facts = _typed_facts(payload, self.type)
            passed, evidence, errors = _check(
                facts, self.required, self.expected, self.roles
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"eval evidence unreadable: {exc}",
                evidence=params,
            )
        return AssertionOutcome(
            type=self.type,
            status="passed" if passed else "failed",
            message=self.success_message
            if passed
            else f"eval evidence failed: {errors}",
            evidence=evidence,
        )


class EvalContractValidAssertion(_EvalFactsAssertion):
    """A third party validated the golden contract with the public package."""

    type = "files.eval_contract_valid"
    required = (
        "contract_digest",
        "contract_media_type",
        "schema_version",
        "validator_package_version",
        "validator_import_root",
        "validation_exit_code",
        "unknown_field_rejected",
    )
    expected: ClassVar[dict[str, object]] = {
        "contract_media_type": "application/vnd.aktp.eval-contract.v1+json",
        "validator_import_root": "site-packages",
        "validation_exit_code": 0,
        "unknown_field_rejected": True,
    }
    # schema_version (1) and validation_exit_code (0) are legitimate
    # integers, so `false` cannot be in the forbidden tuple here — it is
    # excluded via expected-values instead (unknown_field_rejected: true).
    success_message = (
        "the golden contract validates from the published package"
    )


class EvalRunsCompletedAssertion(_EvalFactsAssertion):
    """The golden contract ran twice, each run terminal and distinct."""

    type = "api.eval_runs_completed"
    required = (
        "eval_run_id",
        "terminal_status",
        "contract_digest",
        "subject_digest",
        "runner_id",
        "receipt_digest",
    )
    roles = ("run_one", "run_two")
    expected: ClassVar[dict[str, object]] = {"terminal_status": "succeeded"}

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, run_ids = _value(facts, "eval_run_id")
        ids_map = _fact_map(run_ids)
        distinct = len(set(ids_map.values())) == len(ids_map) and all(
            isinstance(item, str) and item for item in ids_map.values()
        )
        result.status = "passed" if distinct else "failed"
        result.message = (
            "two distinct eval runs completed"
            if distinct
            else "eval evidence failed: one run captured twice"
        )
        return result


class EvalResultDigestStableAssertion(_EvalFactsAssertion):
    """Two runs of the deterministic contract normalize to one digest."""

    type = "api.eval_result_digest_stable"
    required = (
        "run_one_result_digest",
        "run_two_result_digest",
        "digests_equal",
        "normalization_version",
        "determinism_class",
    )
    expected: ClassVar[dict[str, object]] = {
        "digests_equal": True,
        "determinism_class": "deterministic",
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, one = _value(facts, "run_one_result_digest")
        _, two = _value(facts, "run_two_result_digest")
        agrees = isinstance(one, str) and one != "" and one == two
        result.status = "passed" if agrees else "failed"
        result.message = (
            "the two run digests agree"
            if agrees
            else "eval evidence failed: digests disagree"
        )
        return result


class EvalReproducedCleanWorkspaceAssertion(_EvalFactsAssertion):
    """A clean workspace reproduced the result seeing neither checkout."""

    type = "files.eval_reproduced_clean_workspace"
    required = (
        "workspace_root",
        "public_checkout_visible",
        "private_checkout_visible",
        "installed_from",
        "reproduced_result_digest",
        "matches_original_digest",
        "commands_used",
    )
    # `false` is absent on purpose: it is the correct value of both
    # visibility facts on an honest run.
    expected: ClassVar[dict[str, object]] = {
        "public_checkout_visible": False,
        "private_checkout_visible": False,
        "installed_from": "package-index",
        "matches_original_digest": True,
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, digest = _value(facts, "reproduced_result_digest")
        _, commands = _value(facts, "commands_used")
        usable = isinstance(digest, str) and bool(digest) and bool(commands)
        result.status = "passed" if usable else "failed"
        result.message = (
            "the clean workspace reproduced the original result digest"
            if usable
            else "eval evidence failed: reproduction without a result"
        )
        return result


class InvalidEvalRejectedAssertion(_EvalFactsAssertion):
    """All five malformed-contract classes were rejected before execution."""

    type = "api.invalid_eval_rejected"
    required = (
        "error_code",
        "http_status",
        "rejected_before_execution",
        "job_created",
    )
    roles = EVAL_REJECTION_ROLES
    # error_code is deliberately not pinned: each role carries a different
    # correct value, and the role key already names which one.
    expected: ClassVar[dict[str, object]] = {
        "http_status": 422,
        "rejected_before_execution": True,
        "job_created": False,
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, codes = _value(facts, "error_code")
        codes_map = _fact_map(codes)
        aligned = all(
            codes_map.get(role) == role for role in EVAL_REJECTION_ROLES
        )
        result.status = "passed" if aligned else "failed"
        result.message = (
            "each rejection class failed with its own stable code"
            if aligned
            else "eval evidence failed: rejection codes"
        )
        return result


class ConvertedScenarioAssertionsPreservedAssertion(_EvalFactsAssertion):
    """One companion scenario converted without dropping or adding ids."""

    type = "files.converted_scenario_assertions_preserved"
    required = (
        "source_scenario",
        "source_assertion_ids",
        "converted_assertion_ids",
        "dropped_assertion_count",
        "added_assertion_count",
        "conversion_tool_version",
    )
    expected: ClassVar[dict[str, object]] = {
        "dropped_assertion_count": 0,
        "added_assertion_count": 0,
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, source = _value(facts, "source_assertion_ids")
        _, converted = _value(facts, "converted_assertion_ids")
        comparable = (
            isinstance(source, list)
            and isinstance(converted, list)
            and bool(source)
            and set(source) == set(converted)
        )
        result.status = "passed" if comparable else "failed"
        result.message = (
            "converted assertion identity sets match the source"
            if comparable
            else "eval evidence failed: assertion identity sets differ"
        )
        return result


class CanonicalDigestAgreesAssertion(_EvalFactsAssertion):
    """Backend and runner canonical digests of one golden contract agree."""

    type = "api.canonical_digest_agrees"
    required = (
        "golden_contract_id",
        "backend_canonical_digest",
        "runner_canonical_digest",
        "digests_equal",
        "canonicalization",
    )
    expected: ClassVar[dict[str, object]] = {
        "digests_equal": True,
        "canonicalization": "JCS",
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, backend = _value(facts, "backend_canonical_digest")
        _, runner = _value(facts, "runner_canonical_digest")
        agrees = (
            isinstance(backend, str)
            and isinstance(runner, str)
            and bool(backend)
            and backend == runner
        )
        result.status = "passed" if agrees else "failed"
        result.message = (
            "backend and runner canonical digests agree"
            if agrees
            else "eval evidence failed: canonical digests disagree"
        )
        return result


class EvalContractIndexedAssertion(_EvalFactsAssertion):
    """The contract is addressable in the index its subjects share."""

    type = "api.eval_contract_indexed"
    required = (
        "resource_id",
        "resource_type",
        "contract_digest",
        "indexed_alongside_subject",
        "result_contract_digest",
        "result_contract_standing",
    )
    expected: ClassVar[dict[str, object]] = {
        "resource_type": "eval_contract",
        "indexed_alongside_subject": True,
        # Every standing in the closed vocabulary is a legitimate outcome;
        # what may not happen is a result presenting no standing at all.
        "result_contract_standing": _CONTRACT_STANDINGS,
    }

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await super().evaluate(ctx, params)
        if result.status == "failed":
            return result
        facts = _typed_facts(_manifest(ctx, params), self.type)
        _, standing = _value(facts, "result_contract_standing")
        ok = standing in _CONTRACT_STANDINGS
        result.status = "passed" if ok else "failed"
        result.message = (
            "the result carries a standing in the closed vocabulary"
            if ok
            else "eval evidence failed: result presents no standing"
        )
        return result
