"""Stable error codes for eval-contract validation failures.

The private backend maps these onto HTTP 422 responses keyed by the
same strings; the reference runner surfaces them on
``rejected_before_execution`` receipts. Both sides must use exactly
these codes — they are part of the wire contract.
"""

from __future__ import annotations


class EvalContractError(ValueError):
    """Base class: every failure carries one stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EvalContractInvalid(EvalContractError):
    """The document does not satisfy the schema or semantic rules."""

    def __init__(self, message: str) -> None:
        super().__init__("eval_contract_invalid", message)


class EvalSubjectMismatch(EvalContractError):
    """The subject presented does not match the contract's constraint."""

    def __init__(self, message: str) -> None:
        super().__init__("eval_subject_mismatch", message)


class EvalRequirementUnsupported(EvalContractError):
    """A runtime requirement no available environment provides."""

    def __init__(self, message: str) -> None:
        super().__init__("eval_requirement_unsupported", message)


class EvalFixtureDigestMismatch(EvalContractError):
    """A fixture's bytes do not hash to its declared digest."""

    def __init__(self, message: str) -> None:
        super().__init__("eval_fixture_digest_mismatch", message)


class EvalBudgetInvalid(EvalContractError):
    """A budget bound is present but outside its allowed range.

    Subclasses the base rather than ``EvalContractInvalid`` so the
    stable code is set once; the backend still returns 422 for it.
    """

    def __init__(self, message: str) -> None:
        super().__init__("eval_budget_invalid", message)
