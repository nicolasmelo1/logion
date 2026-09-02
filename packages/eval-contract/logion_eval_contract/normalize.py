"""Normalize raw run output into a validated, canonical result.

A result belongs to a model-harness pair: the environment digest is
computed over the closed, named fields ``harness_id``,
``harness_version``, ``model_id``, and ``model_version`` — never an
opaque blob, never prose in ``limitations``. Two executions of a
``deterministic`` contract normalize to byte-identical results.
"""

from __future__ import annotations

from logion_eval_contract._json import opt_bool, opt_str
from logion_eval_contract.canonical import short_sha256
from logion_eval_contract.errors import EvalContractInvalid
from logion_eval_contract.models import (
    ASSERTION_OPERATORS,
    METRIC_DIRECTIONS,
    METRIC_KINDS,
    OUTCOME_VALUES,
    REQUIRED_RESULT_FIELDS,
    RESULT_MEDIA_TYPE,
    AssertionOutcome,
    EvalResult,
    MetricValue,
    ResultEnvironment,
)

#: Version of the normalization this release performs. Pinned in
#: evidence so an unversioned normalizer cannot claim stability.
NORMALIZATION_VERSION = "logion.eval.normalize.v1"


def _scalar(value: object, where: str) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise EvalContractInvalid(f"{where} must be a scalar")


def result_to_json(result: EvalResult) -> dict:
    """Round-trip a model back to its JSON document form."""
    document: dict = {
        "contract_digest": result.contract_digest,
        "subject_digest": result.subject_digest,
        "environment_digest": result.environment_digest(),
        "environment": {
            "harness_id": result.environment.harness_id,
            "harness_version": result.environment.harness_version,
            "model_id": result.environment.model_id,
            "model_version": result.environment.model_version,
        },
        "assertion_vector": [
            {
                "id": outcome.id,
                "operator": outcome.operator,
                "passed": outcome.passed,
                "actual": outcome.actual,
            }
            for outcome in result.assertion_vector
        ],
        "metrics": [
            {
                "id": metric.id,
                "kind": metric.kind,
                "direction": metric.direction,
                "value": metric.value,
            }
            for metric in result.metrics
        ],
        "outcome": result.outcome,
        "artifacts": result.artifacts,
        "resource_usage": result.resource_usage,
        "limitations": result.limitations,
        "contract_standing": result.contract_standing,
    }
    if result.extensions:
        document["extensions"] = result.extensions
    return document


def environment_digest_from(
    harness_id: str,
    harness_version: str,
    model_id: str,
    model_version: str,
) -> str:
    """Digest over the closed named environment fields only."""
    return short_sha256({
        "harness_id": harness_id,
        "harness_version": harness_version,
        "model_id": model_id,
        "model_version": model_version,
    })


def _parse_environment(environment: dict) -> ResultEnvironment:
    unknown = sorted(
        set(environment)
        - {
            "harness_id",
            "harness_version",
            "model_id",
            "model_version",
        }
    )
    if unknown:
        raise EvalContractInvalid(
            f"environment has unknown keys: {', '.join(unknown)}"
        )
    return ResultEnvironment(
        harness_id=_require_text(
            environment.get("harness_id"), "environment.harness_id"
        ),
        harness_version=_require_text(
            environment.get("harness_version"),
            "environment.harness_version",
        ),
        model_id=_require_text(
            environment.get("model_id"), "environment.model_id"
        ),
        model_version=_require_text(
            environment.get("model_version"), "environment.model_version"
        ),
    )


def _parse_outcome(payload: dict) -> str:
    outcome = _require_text(payload.get("outcome"), "outcome")
    if outcome not in OUTCOME_VALUES:
        raise EvalContractInvalid(f"outcome must be one of {OUTCOME_VALUES}")
    return outcome


def _parse_standing(payload: dict) -> str:
    standing = opt_str(payload, "contract_standing") or "unreviewed"
    if standing not in ("unreviewed", "contested", "reproduced", "superseded"):
        raise EvalContractInvalid(
            "contract_standing must be one of"
            " ('unreviewed', 'contested', 'reproduced', 'superseded')"
        )
    return standing


def _parse_assertion_vector(vector_value: list) -> tuple:
    vector: list[AssertionOutcome] = []
    for index, item in enumerate(vector_value):
        where = f"assertion_vector[{index}]"
        if not isinstance(item, dict):
            raise EvalContractInvalid(f"{where} must be an object")
        unknown = sorted(set(item) - {"id", "operator", "passed", "actual"})
        if unknown:
            raise EvalContractInvalid(
                f"{where} has unknown keys: {', '.join(unknown)}"
            )
        passed = opt_bool(item, "passed")
        if passed is None:
            raise EvalContractInvalid(f"{where}.passed must be a boolean")
        operator = _require_text(item.get("operator"), f"{where}.operator")
        if operator not in ASSERTION_OPERATORS:
            raise EvalContractInvalid(
                f"{where}.operator must be one of {ASSERTION_OPERATORS}"
            )
        vector.append(
            AssertionOutcome(
                id=_require_text(item.get("id"), f"{where}.id"),
                operator=operator,
                passed=passed,
                actual=_scalar(item.get("actual"), f"{where}.actual"),
            )
        )
    return tuple(vector)


def _parse_metric_values(metrics_value: list) -> tuple:
    metrics: list[MetricValue] = []
    for index, item in enumerate(metrics_value):
        where = f"metrics[{index}]"
        if not isinstance(item, dict):
            raise EvalContractInvalid(f"{where} must be an object")
        unknown = sorted(set(item) - {"id", "kind", "direction", "value"})
        if unknown:
            raise EvalContractInvalid(
                f"{where} has unknown keys: {', '.join(unknown)}"
            )
        raw_value = item.get("value")
        if isinstance(raw_value, bool) or not isinstance(
            raw_value, (int, float)
        ):
            raise EvalContractInvalid(f"{where}.value must be a number")
        kind = _require_text(item.get("kind"), f"{where}.kind")
        if kind not in METRIC_KINDS:
            raise EvalContractInvalid(
                f"{where}.kind must be one of {METRIC_KINDS}"
            )
        direction = _require_text(item.get("direction"), f"{where}.direction")
        if direction not in METRIC_DIRECTIONS:
            raise EvalContractInvalid(
                f"{where}.direction must be one of {METRIC_DIRECTIONS}"
            )
        metrics.append(
            MetricValue(
                id=_require_text(item.get("id"), f"{where}.id"),
                kind=kind,
                direction=direction,
                value=raw_value,
            )
        )
    return tuple(metrics)


def _require_mapping_field(payload: dict, key: str) -> dict:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise EvalContractInvalid(f"{key} must be an object")
    return value


def _require_list_field(payload: dict, key: str) -> list:
    value = payload.get(key)
    if not isinstance(value, list):
        raise EvalContractInvalid(f"{key} must be an array")
    return value


def parse_result_document(payload: dict) -> EvalResult:
    """Validate one result document into its typed model."""
    from logion_eval_contract.parse import _require_json_value

    _require_json_value(payload, "eval result")
    allowed = {
        *REQUIRED_RESULT_FIELDS,
        "extensions",
        "environment",
        "contract_standing",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise EvalContractInvalid(
            f"eval result has unknown top-level keys: {', '.join(unknown)}"
        )
    contract_digest = _require_digest_field(payload, "contract_digest")
    subject_digest = _require_digest_field(payload, "subject_digest")
    env = _parse_environment(_require_mapping_field(payload, "environment"))
    outcome = _parse_outcome(payload)
    standing = _parse_standing(payload)
    limitations = _require_text(payload.get("limitations"), "limitations")
    vector = _parse_assertion_vector(
        _require_list_field(payload, "assertion_vector")
    )
    metrics = _parse_metric_values(_require_list_field(payload, "metrics"))
    artifacts = _require_mapping_field(payload, "artifacts")
    resource_usage = _require_mapping_field(payload, "resource_usage")
    extensions_value = (
        _require_mapping_field(payload, "extensions")
        if "extensions" in payload
        else {}
    )
    declared_env_digest = _require_digest_field(payload, "environment_digest")
    expected_env_digest = environment_digest_from(
        env.harness_id,
        env.harness_version,
        env.model_id,
        env.model_version,
    )
    if declared_env_digest != expected_env_digest:
        raise EvalContractInvalid(
            "environment_digest must equal the digest over the closed"
            " named environment fields"
        )
    return EvalResult(
        contract_digest=contract_digest,
        subject_digest=subject_digest,
        environment=env,
        assertion_vector=vector,
        metrics=metrics,
        outcome=outcome,
        artifacts=artifacts,
        resource_usage=resource_usage,
        limitations=limitations,
        contract_standing=standing,
        extensions=extensions_value,
    )


def computed_env_digest(env: ResultEnvironment) -> str:
    """Digest over the closed named fields of a parsed environment."""
    return environment_digest_from(
        env.harness_id,
        env.harness_version,
        env.model_id,
        env.model_version,
    )


def result_digest(result: EvalResult) -> str:
    """SHA-256 over the JCS-canonical bytes of the result document."""
    return short_sha256(result_to_json(result))


def result_media_type() -> str:
    """The media type a normalized result carries."""
    return RESULT_MEDIA_TYPE


def pair_key(result: EvalResult) -> tuple[str, str, str, str]:
    """The model-harness pair a result belongs to.

    ``compare`` fails closed when the pair differs between two
    results: a harness upgrade must never read as an artifact
    improvement, so two results across differing pairs are not
    comparable rather than comparable-with-caveat.
    """
    return (
        result.environment.harness_id,
        result.environment.harness_version,
        result.environment.model_id,
        result.environment.model_version,
    )


def _require_text(value: object, where: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise EvalContractInvalid(f"{where} must be a non-empty string")


def _require_digest_field(payload: dict, key: str) -> str:
    value = payload.get(key)
    text = _require_text(value, key)
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise EvalContractInvalid(
            f"{key} must be a lowercase sha256 hex digest"
        )
    return text
