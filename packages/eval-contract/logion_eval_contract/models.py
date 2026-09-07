"""Typed models with closed enums for eval contracts and results.

Every top-level field is required; absence fails validation rather
than defaulting. Extension fields live only under ``extensions``.

``typing.Any`` is banned repo-wide, so raw JSON shapes use the
``JsonValue``/``JsonObject`` aliases from :mod:`logion_eval_contract._json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from logion_eval_contract._json import JsonObject

#: The contract media type this package owns.
CONTRACT_MEDIA_TYPE = "application/vnd.aktp.eval-contract.v1+json"

#: The result media type this package normalizes to.
RESULT_MEDIA_TYPE = "application/vnd.aktp.eval-result.v1+json"

#: Current contract schema version accepted by this release.
CONTRACT_SCHEMA_VERSION = 1

OUTCOME_VALUES = ("passed", "failed", "errored", "skipped")
ASSERTION_OPERATORS = (
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "contains",
    "matches",
)
METRIC_KINDS = (
    "count",
    "ratio",
    "duration_ms",
    "tokens",
    "cost_usd",
)
METRIC_DIRECTIONS = ("higher_is_better", "lower_is_better")
DETERMINISM_CLASSES = ("deterministic", "seeded", "nondeterministic")
CONTRACT_STANDINGS = (
    "unreviewed",
    "contested",
    "reproduced",
    "superseded",
)

#: Required top-level contract keys. Absence is an error, not a default.
REQUIRED_CONTRACT_FIELDS = (
    "schema_version",
    "subject",
    "archetype",
    "inputs",
    "fixtures",
    "runtime_requirements",
    "steps",
    "metrics",
    "assertions",
    "budgets",
    "outputs",
    "redaction",
    "determinism_class",
    "evaluator_requirement",
)

#: Required top-level result keys.
REQUIRED_RESULT_FIELDS = (
    "contract_digest",
    "subject_digest",
    "environment",
    "environment_digest",
    "assertion_vector",
    "metrics",
    "outcome",
    "artifacts",
    "resource_usage",
    "limitations",
)

#: Closed, named fields the environment digest is computed over —
#: never an opaque blob, never prose in ``limitations``.
ENVIRONMENT_DIGEST_FIELDS = (
    "harness_id",
    "harness_version",
    "model_id",
    "model_version",
)


@dataclass(frozen=True)
class Subject:
    type: str
    digest_constraint: str


@dataclass(frozen=True)
class Fixture:
    name: str
    digest: str


@dataclass(frozen=True)
class RuntimeRequirement:
    kind: str
    value: str


@dataclass(frozen=True)
class Step:
    id: str
    action: str
    params: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    kind: str
    direction: str
    unit: str | None = None


@dataclass(frozen=True)
class AssertionDefinition:
    id: str
    operator: str
    metric: str
    expected: str | int | float | bool | None


@dataclass(frozen=True)
class Budget:
    kind: str
    max_value: int | float


@dataclass(frozen=True)
class OutputSpec:
    name: str
    path: str


@dataclass(frozen=True)
class Redaction:
    mode: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluatorRequirement:
    kind: str
    digest: str


@dataclass(frozen=True)
class EvalContract:
    """Typed view of one validated contract."""

    schema_version: int
    subject: Subject
    archetype: str
    inputs: tuple[str, ...]
    fixtures: tuple[Fixture, ...]
    runtime_requirements: tuple[RuntimeRequirement, ...]
    steps: tuple[Step, ...]
    metrics: tuple[MetricDefinition, ...]
    assertions: tuple[AssertionDefinition, ...]
    budgets: tuple[Budget, ...]
    outputs: tuple[OutputSpec, ...]
    redaction: Redaction
    determinism_class: str
    evaluator_requirement: EvaluatorRequirement
    extensions: JsonObject = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        """The JSON object this model round-trips from."""
        from logion_eval_contract.parse import contract_to_json

        return contract_to_json(self)


@dataclass(frozen=True)
class AssertionOutcome:
    id: str
    operator: str
    passed: bool
    actual: str | int | float | bool | None = None


@dataclass(frozen=True)
class MetricValue:
    id: str
    kind: str
    direction: str
    value: int | float


@dataclass(frozen=True)
class ResultEnvironment:
    harness_id: str
    harness_version: str
    model_id: str
    model_version: str


@dataclass(frozen=True)
class EvalResult:
    """Typed view of one normalized run result."""

    contract_digest: str
    subject_digest: str
    environment: ResultEnvironment
    assertion_vector: tuple[AssertionOutcome, ...]
    metrics: tuple[MetricValue, ...]
    outcome: str
    artifacts: JsonObject
    resource_usage: JsonObject
    limitations: str
    contract_standing: str = "unreviewed"
    extensions: JsonObject = field(default_factory=dict)

    def environment_digest(self) -> str:
        """Digest over the closed named environment fields only."""
        from logion_eval_contract.canonical import short_sha256

        env: JsonObject = {
            "harness_id": self.environment.harness_id,
            "harness_version": self.environment.harness_version,
            "model_id": self.environment.model_id,
            "model_version": self.environment.model_version,
        }
        return short_sha256(env)

    def to_json(self) -> JsonObject:
        """The JSON object this model round-trips from."""
        from logion_eval_contract.normalize import result_to_json

        return result_to_json(self)
