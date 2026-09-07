"""logion-eval-contract: the portable eval contract library.

The only parser, validator, canonicalizer, and result normalizer in
the system. The private backend imports a pinned released version; a
second implementation of canonicalization is the specific defect the
cross-repo digest-agreement assertion exists to catch.
"""

from __future__ import annotations

from logion_eval_contract._json import JsonObject, JsonValue
from logion_eval_contract.canonical import (
    canonicalize,
    canonicalize_text,
    is_round_trip_stable,
    short_sha256,
)
from logion_eval_contract.errors import (
    EvalBudgetInvalid,
    EvalContractError,
    EvalContractInvalid,
    EvalFixtureDigestMismatch,
    EvalRequirementUnsupported,
    EvalSubjectMismatch,
)
from logion_eval_contract.models import (
    ASSERTION_OPERATORS,
    CONTRACT_MEDIA_TYPE,
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_STANDINGS,
    DETERMINISM_CLASSES,
    ENVIRONMENT_DIGEST_FIELDS,
    METRIC_DIRECTIONS,
    METRIC_KINDS,
    OUTCOME_VALUES,
    RESULT_MEDIA_TYPE,
    EvalContract,
    EvalResult,
    ResultEnvironment,
)
from logion_eval_contract.normalize import (
    NORMALIZATION_VERSION,
    environment_digest_from,
    pair_key,
    parse_result_document,
    result_digest,
    result_media_type,
    result_to_json,
)
from logion_eval_contract.parse import (
    contract_digest,
    contract_to_json,
    load_document,
    parse_contract_document,
    parse_contract_file,
    validate_subject,
)

__version__ = "0.1.0.dev1"

__all__ = [
    "ASSERTION_OPERATORS",
    "CONTRACT_MEDIA_TYPE",
    "CONTRACT_SCHEMA_VERSION",
    "CONTRACT_STANDINGS",
    "DETERMINISM_CLASSES",
    "ENVIRONMENT_DIGEST_FIELDS",
    "METRIC_DIRECTIONS",
    "METRIC_KINDS",
    "NORMALIZATION_VERSION",
    "OUTCOME_VALUES",
    "RESULT_MEDIA_TYPE",
    "EvalBudgetInvalid",
    "EvalContract",
    "EvalContractError",
    "EvalContractInvalid",
    "EvalFixtureDigestMismatch",
    "EvalRequirementUnsupported",
    "EvalResult",
    "EvalSubjectMismatch",
    "JsonObject",
    "JsonValue",
    "ResultEnvironment",
    "__version__",
    "canonicalize",
    "canonicalize_text",
    "contract_digest",
    "contract_to_json",
    "environment_digest_from",
    "is_round_trip_stable",
    "load_document",
    "pair_key",
    "parse_contract_document",
    "parse_contract_file",
    "parse_result_document",
    "result_digest",
    "result_media_type",
    "result_to_json",
    "short_sha256",
    "validate_subject",
]
