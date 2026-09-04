"""Parse and validate a contract or result document, failing closed.

YAML and JSON authoring forms normalize to the same JSON object before
any hashing happens, so a contract's digest is identical whether it
was written as YAML or JSON. Unknown top-level keys are rejected;
extension fields live only under ``extensions``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from logion_eval_contract._json import (
    JsonObject,
    JsonValue,
    opt_int,
    opt_str,
)
from logion_eval_contract.canonical import short_sha256
from logion_eval_contract.errors import (
    EvalBudgetInvalid,
    EvalContractInvalid,
    EvalSubjectMismatch,
)
from logion_eval_contract.models import (
    ASSERTION_OPERATORS,
    CONTRACT_SCHEMA_VERSION,
    DETERMINISM_CLASSES,
    METRIC_DIRECTIONS,
    METRIC_KINDS,
    REQUIRED_CONTRACT_FIELDS,
    AssertionDefinition,
    Budget,
    EvalContract,
    EvaluatorRequirement,
    Fixture,
    MetricDefinition,
    OutputSpec,
    Redaction,
    RuntimeRequirement,
    Step,
    Subject,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Path segment markers a contract output may never contain. ``..``
#: escapes its directory; an absolute path escapes the output root.
_PATH_FORBIDDEN_SEGMENT = ".."


def _require_mapping(value: JsonValue, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise EvalContractInvalid(f"{where} must be an object")
    return value


def _require_json_scalar(value: JsonValue, where: str) -> None:
    """Reject YAML-only scalar shapes: dates, non-finite numbers."""
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, float) and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        raise EvalContractInvalid(f"{where} must be a finite JSON number")
    if isinstance(value, (int, float)):
        return
    raise EvalContractInvalid(
        f"{where} must be a JSON-representable value, got"
        f" {type(value).__name__}"
    )


def _require_json_value(value: JsonValue, where: str) -> None:
    """Reject YAML-only shapes that cannot survive the JSON digest.

    ``yaml.safe_load`` produces values outside the JSON grammar —
    ``date``/``datetime`` scalars, non-string mapping keys, ``inf``/
    ``nan`` floats. The load docstring promises every parsed document
    round-trips through ``json.dumps``; anything else would crash the
    canonicalizer later (a 500) instead of failing validation (a 422),
    so the parser rejects it here, at the boundary.
    """
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_json_value(item, f"{where}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvalContractInvalid(
                    f"{where} has a non-string key: {key!r}"
                )
            _require_json_value(item, f"{where}.{key}")
        return
    _require_json_scalar(value, where)


def _require_list(value: JsonValue, where: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise EvalContractInvalid(f"{where} must be an array")
    return value


def _require_text(value: JsonValue, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvalContractInvalid(f"{where} must be a non-empty string")
    return value


def _reject_unknown_keys(
    payload: JsonObject, required: tuple[str, ...], where: str
) -> None:
    allowed = {*required, "extensions"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise EvalContractInvalid(
            f"{where} has unknown top-level keys: {', '.join(unknown)}"
        )


def _reject_section_keys(
    payload: JsonObject, allowed: set[str], where: str
) -> None:
    """Nested objects are closed exactly like the published schema."""
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise EvalContractInvalid(
            f"{where} has unknown keys: {', '.join(unknown)}"
        )


def _require_digest(value: JsonValue, where: str) -> str:
    text = _require_text(value, where)
    if not _SHA256_RE.match(text):
        raise EvalContractInvalid(
            f"{where} must be a lowercase sha256 hex digest"
        )
    return text


def _check_safe_path(value: str, where: str) -> None:
    """Reject paths that escape the run's output directory.

    ``Path.is_absolute()`` covers ``/etc/passwd``; a ``..`` segment
    covers traversal that stays nominally relative; leading ``~`` and
    ``$`` cover the home-relative and expansion forms a shell would
    send outside the workspace. A ``~`` or ``$`` *inside* one segment
    name is an ordinary character, not traversal.
    """
    candidate = Path(value)
    if (
        candidate.is_absolute()
        or _PATH_FORBIDDEN_SEGMENT in candidate.parts
        or value.startswith(("~", "$"))
    ):
        raise EvalContractInvalid(f"{where} must not contain path traversal")


def _parse_subject(payload: JsonObject) -> Subject:
    subject = _require_mapping(payload.get("subject"), "subject")
    _reject_section_keys(subject, {"type", "digest_constraint"}, "subject")
    subject_type = _require_text(subject.get("type"), "subject.type")
    constraint = _require_text(
        subject.get("digest_constraint"), "subject.digest_constraint"
    )
    if constraint != "exact":
        raise EvalContractInvalid("subject.digest_constraint must be 'exact'")
    return Subject(type=subject_type, digest_constraint=constraint)


def _parse_fixtures(payload: JsonObject) -> tuple[Fixture, ...]:
    fixtures = _require_list(payload.get("fixtures"), "fixtures")
    parsed: list[Fixture] = []
    seen: set[str] = set()
    for index, item in enumerate(fixtures):
        where = f"fixtures[{index}]"
        mapping = _require_mapping(item, where)
        _reject_section_keys(mapping, {"name", "digest"}, where)
        name = _require_text(mapping.get("name"), f"{where}.name")
        _check_safe_path(name, f"{where}.name")
        if name in seen:
            raise EvalContractInvalid(f"fixtures has duplicate name {name!r}")
        seen.add(name)
        digest = _require_digest(mapping.get("digest"), f"{where}.digest")
        parsed.append(Fixture(name=name, digest=digest))
    return tuple(parsed)


def _parse_runtime_requirements(
    payload: JsonObject,
) -> tuple[RuntimeRequirement, ...]:
    items = _require_list(
        payload.get("runtime_requirements"), "runtime_requirements"
    )
    parsed: list[RuntimeRequirement] = []
    for index, item in enumerate(items):
        where = f"runtime_requirements[{index}]"
        mapping = _require_mapping(item, where)
        _reject_section_keys(mapping, {"kind", "value"}, where)
        parsed.append(
            RuntimeRequirement(
                kind=_require_text(mapping.get("kind"), f"{where}.kind"),
                value=_require_text(mapping.get("value"), f"{where}.value"),
            )
        )
    return tuple(parsed)


def _parse_steps(payload: JsonObject) -> tuple[Step, ...]:
    steps = _require_list(payload.get("steps"), "steps")
    parsed: list[Step] = []
    seen: set[str] = set()
    for index, item in enumerate(steps):
        where = f"steps[{index}]"
        mapping = _require_mapping(item, where)
        step_id = _require_text(mapping.get("id"), f"{where}.id")
        if step_id in seen:
            raise EvalContractInvalid(f"steps has duplicate id {step_id!r}")
        seen.add(step_id)
        _reject_section_keys(mapping, {"id", "action", "params"}, where)
        params_value = mapping.get("params", {})
        params = _require_mapping(params_value, f"{where}.params")
        parsed.append(
            Step(
                id=step_id,
                action=_require_text(mapping.get("action"), f"{where}.action"),
                params=params,
            )
        )
    return tuple(parsed)


def _parse_metrics(payload: JsonObject) -> tuple[MetricDefinition, ...]:
    metrics = _require_list(payload.get("metrics"), "metrics")
    parsed: list[MetricDefinition] = []
    seen: set[str] = set()
    for index, item in enumerate(metrics):
        where = f"metrics[{index}]"
        mapping = _require_mapping(item, where)
        metric_id = _require_text(mapping.get("id"), f"{where}.id")
        if metric_id in seen:
            raise EvalContractInvalid(
                f"metrics has duplicate id {metric_id!r}"
            )
        seen.add(metric_id)
        _reject_section_keys(
            mapping, {"id", "kind", "direction", "unit"}, where
        )
        kind = _require_text(mapping.get("kind"), f"{where}.kind")
        if kind not in METRIC_KINDS:
            raise EvalContractInvalid(
                f"{where}.kind must be one of {METRIC_KINDS}"
            )
        direction = _require_text(
            mapping.get("direction"), f"{where}.direction"
        )
        if direction not in METRIC_DIRECTIONS:
            raise EvalContractInvalid(
                f"{where}.direction must be one of {METRIC_DIRECTIONS}"
            )
        unit = opt_str(mapping, "unit")
        parsed.append(
            MetricDefinition(
                id=metric_id, kind=kind, direction=direction, unit=unit
            )
        )
    return tuple(parsed)


def _parse_assertions(
    payload: JsonObject,
) -> tuple[AssertionDefinition, ...]:
    assertions = _require_list(payload.get("assertions"), "assertions")
    parsed: list[AssertionDefinition] = []
    seen: set[str] = set()
    for index, item in enumerate(assertions):
        where = f"assertions[{index}]"
        mapping = _require_mapping(item, where)
        assertion_id = _require_text(mapping.get("id"), f"{where}.id")
        if assertion_id in seen:
            raise EvalContractInvalid(
                f"assertions has duplicate id {assertion_id!r}"
            )
        seen.add(assertion_id)
        _reject_section_keys(
            mapping, {"id", "operator", "metric", "expected"}, where
        )
        operator = _require_text(mapping.get("operator"), f"{where}.operator")
        if operator not in ASSERTION_OPERATORS:
            raise EvalContractInvalid(
                f"{where}.operator must be one of {ASSERTION_OPERATORS}"
            )
        expected_value = mapping.get("expected")
        if isinstance(expected_value, (dict, list)):
            raise EvalContractInvalid(f"{where}.expected must be a scalar")
        expected: str | int | float | bool | None = (
            expected_value
            if isinstance(expected_value, (str, int, float, bool, type(None)))
            else None
        )
        if expected is None and expected_value is not None:
            raise EvalContractInvalid(f"{where}.expected must be a scalar")
        parsed.append(
            AssertionDefinition(
                id=assertion_id,
                operator=operator,
                metric=_require_text(mapping.get("metric"), f"{where}.metric"),
                expected=expected,
            )
        )
    return tuple(parsed)


def _parse_budgets(payload: JsonObject) -> tuple[Budget, ...]:
    budgets = _require_list(payload.get("budgets"), "budgets")
    parsed: list[Budget] = []
    for index, item in enumerate(budgets):
        where = f"budgets[{index}]"
        mapping = _require_mapping(item, where)
        _reject_section_keys(mapping, {"kind", "max_value"}, where)
        kind = _require_text(mapping.get("kind"), f"{where}.kind")
        max_value = mapping.get("max_value")
        if isinstance(max_value, bool) or not isinstance(
            max_value, (int, float)
        ):
            raise EvalContractInvalid(f"{where}.max_value must be a number")
        if max_value < 0:
            raise EvalBudgetInvalid(f"{where}.max_value must be non-negative")
        parsed.append(Budget(kind=kind, max_value=max_value))
    return tuple(parsed)


def _parse_outputs(payload: JsonObject) -> tuple[OutputSpec, ...]:
    outputs = _require_list(payload.get("outputs"), "outputs")
    parsed: list[OutputSpec] = []
    seen: set[str] = set()
    for index, item in enumerate(outputs):
        where = f"outputs[{index}]"
        mapping = _require_mapping(item, where)
        _reject_section_keys(mapping, {"name", "path"}, where)
        name = _require_text(mapping.get("name"), f"{where}.name")
        if name in seen:
            raise EvalContractInvalid(f"outputs has duplicate name {name!r}")
        seen.add(name)
        path = _require_text(mapping.get("path"), f"{where}.path")
        _check_safe_path(path, f"{where}.path")
        parsed.append(OutputSpec(name=name, path=path))
    return tuple(parsed)


def _parse_redaction(payload: JsonObject) -> Redaction:
    redaction = _require_mapping(payload.get("redaction"), "redaction")
    _reject_section_keys(redaction, {"mode", "fields"}, "redaction")
    mode = _require_text(redaction.get("mode"), "redaction.mode")
    if mode not in ("drop", "placeholder"):
        raise EvalContractInvalid(
            "redaction.mode must be 'drop' or 'placeholder'"
        )
    fields_value = redaction.get("fields", [])
    fields = _require_list(fields_value, "redaction.fields")
    for index, item in enumerate(fields):
        _require_text(item, f"redaction.fields[{index}]")
    return Redaction(mode=mode, fields=tuple(str(f) for f in fields))


def _parse_evaluator_requirement(
    payload: JsonObject,
) -> EvaluatorRequirement:
    evaluator = _require_mapping(
        payload.get("evaluator_requirement"), "evaluator_requirement"
    )
    _reject_section_keys(
        evaluator, {"kind", "digest"}, "evaluator_requirement"
    )
    kind = _require_text(evaluator.get("kind"), "evaluator_requirement.kind")
    if kind not in ("none", "builtin", "pinned"):
        raise EvalContractInvalid(
            "evaluator_requirement.kind must be 'none', 'builtin', or 'pinned'"
        )
    digest_value = evaluator.get("digest")
    digest: str = ""
    if kind == "pinned":
        digest = _require_digest(digest_value, "evaluator_requirement.digest")
    else:
        if digest_value is not None:
            raise EvalContractInvalid(
                "evaluator_requirement.digest is only valid when kind"
                " is 'pinned'"
            )
    return EvaluatorRequirement(kind=kind, digest=digest)


def _parse_extensions(payload: JsonObject, where: str) -> JsonObject:
    extensions_value = payload.get("extensions", {})
    return _require_mapping(extensions_value, f"{where}.extensions")


def parse_contract_document(
    payload: JsonObject, *, source_format: str = "json"
) -> EvalContract:
    """Validate one contract document into its typed model."""
    _require_json_value(payload, "eval contract")
    _reject_unknown_keys(
        payload, REQUIRED_CONTRACT_FIELDS, f"eval contract ({source_format})"
    )
    schema_version = opt_int(payload, "schema_version")
    if schema_version != CONTRACT_SCHEMA_VERSION:
        raise EvalContractInvalid(
            f"schema_version must be {CONTRACT_SCHEMA_VERSION},"
            f" got {schema_version!r}"
        )
    archetype = _require_text(payload.get("archetype"), "archetype")
    inputs = _require_list(payload.get("inputs"), "inputs")
    input_names: list[str] = []
    for index, item in enumerate(inputs):
        input_name = _require_text(item, f"inputs[{index}]")
        _check_safe_path(input_name, f"inputs[{index}]")
        input_names.append(input_name)
    determinism_class = _require_text(
        payload.get("determinism_class"), "determinism_class"
    )
    if determinism_class not in DETERMINISM_CLASSES:
        raise EvalContractInvalid(
            f"determinism_class must be one of {DETERMINISM_CLASSES}"
        )
    return EvalContract(
        schema_version=schema_version,
        subject=_parse_subject(payload),
        archetype=archetype,
        inputs=tuple(input_names),
        fixtures=_parse_fixtures(payload),
        runtime_requirements=_parse_runtime_requirements(payload),
        steps=_parse_steps(payload),
        metrics=_parse_metrics(payload),
        assertions=_parse_assertions(payload),
        budgets=_parse_budgets(payload),
        outputs=_parse_outputs(payload),
        redaction=_parse_redaction(payload),
        determinism_class=determinism_class,
        evaluator_requirement=_parse_evaluator_requirement(payload),
        extensions=_parse_extensions(payload, "eval contract"),
    )


def load_document(path: str | Path) -> tuple[JsonObject, str]:
    """Load a YAML or JSON file as its JSON object form.

    Returns ``(document, source_format)``. The normalization is total:
    any YAML document that parses also round-trips through
    :func:`json.dumps`, which is what makes the YAML and JSON digests
    identical.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        value: JsonValue = json.loads(text)
        _require_json_value(value, str(file_path))
        document = _require_mapping(value, str(file_path))
        return document, "json"
    if suffix in (".yaml", ".yml"):
        value = yaml.safe_load(text)
        _require_json_value(value, str(file_path))
        document = _require_mapping(value, str(file_path))
        return document, "yaml"
    raise EvalContractInvalid(
        f"unsupported contract file extension: {suffix!r}"
    )


def parse_contract_file(path: str | Path) -> EvalContract:
    """Load and validate a contract written as YAML or JSON."""
    document, source_format = load_document(path)
    return parse_contract_document(document, source_format=source_format)


def contract_to_json(contract: EvalContract) -> JsonObject:
    """Round-trip a model back to its JSON document form."""
    document: JsonObject = {
        "schema_version": contract.schema_version,
        "subject": {
            "type": contract.subject.type,
            "digest_constraint": contract.subject.digest_constraint,
        },
        "archetype": contract.archetype,
        "inputs": list(contract.inputs),
        "fixtures": [
            {"name": fixture.name, "digest": fixture.digest}
            for fixture in contract.fixtures
        ],
        "runtime_requirements": [
            {"kind": req.kind, "value": req.value}
            for req in contract.runtime_requirements
        ],
        "steps": [
            {
                "id": step.id,
                "action": step.action,
                "params": step.params,
            }
            for step in contract.steps
        ],
        "metrics": [
            {
                "id": metric.id,
                "kind": metric.kind,
                "direction": metric.direction,
                **({"unit": metric.unit} if metric.unit else {}),
            }
            for metric in contract.metrics
        ],
        "assertions": [
            {
                "id": assertion.id,
                "operator": assertion.operator,
                "metric": assertion.metric,
                "expected": assertion.expected,
            }
            for assertion in contract.assertions
        ],
        "budgets": [
            {"kind": budget.kind, "max_value": budget.max_value}
            for budget in contract.budgets
        ],
        "outputs": [
            {"name": output.name, "path": output.path}
            for output in contract.outputs
        ],
        "redaction": {
            "mode": contract.redaction.mode,
            "fields": list(contract.redaction.fields),
        },
        "determinism_class": contract.determinism_class,
        "evaluator_requirement": {
            "kind": contract.evaluator_requirement.kind,
            **(
                {"digest": contract.evaluator_requirement.digest}
                if contract.evaluator_requirement.digest
                else {}
            ),
        },
    }
    if contract.extensions:
        document["extensions"] = contract.extensions
    return document


def contract_digest(contract: EvalContract) -> str:
    """SHA-256 over the JCS-canonical bytes of the JSON form."""
    return short_sha256(contract_to_json(contract))


def validate_subject(contract: EvalContract, subject_digest: str) -> None:
    """Fail when the presented subject does not satisfy the contract.

    The ``exact`` constraint binds the presented subject to the
    contract's declared inputs: the subject's content digest must be a
    lowercase sha256 hex string AND must be the declared digest of a
    fixture the contract names. A contract that declares no fixtures
    binds nothing, so only the digest form is checkable there.
    """
    if not _SHA256_RE.match(subject_digest):
        raise EvalSubjectMismatch(
            "subject digest must be a lowercase sha256 hex digest"
        )
    if contract.subject.digest_constraint != "exact":
        raise EvalSubjectMismatch(
            "unsupported subject digest constraint:"
            f" {contract.subject.digest_constraint}"
        )
    declared = {fixture.digest for fixture in contract.fixtures}
    if declared and subject_digest not in declared:
        raise EvalSubjectMismatch(
            "subject digest does not match any fixture the contract declares"
        )
