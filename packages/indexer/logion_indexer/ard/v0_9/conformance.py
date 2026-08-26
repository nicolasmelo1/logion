# SPDX-License-Identifier: MIT
"""ARD v0.9 conformance validation.

Separate from AI Catalog conformance: ARD has its own error codes,
version negotiation, and fixture suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from logion_indexer._json import JsonValue, as_object

from . import (
    ARD_ERROR_CODES,
    SearchResponse,
)
from .codec import (
    ARDDecodeError,
    decode_search_response,
)

ConformanceResultLevel = Literal["pass", "fail"]


@dataclass(frozen=True)
class ARDConformanceResult:
    """Result of an ARD conformance check."""

    result: ConformanceResultLevel
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.result == "pass"


def validate_search_response(
    doc: JsonValue,
) -> ARDConformanceResult:
    """Validate a raw JSON document as an ARD search response.

    This is the entry point for ``validate-ard`` CLI command.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        response = decode_search_response(doc)
    except ARDDecodeError as e:
        return ARDConformanceResult(result="fail", errors=(str(e),))

    for i, result in enumerate(response.results):
        if not result.identifier:
            errors.append(f"result[{i}]: identifier must not be empty")
        if not result.type:
            errors.append(f"result[{i}]: type must not be empty")

        # Score is relevance only — never trust/safety.
        if result.score is not None:
            if not 0 <= result.score <= 100:
                errors.append(
                    f"result[{i}] ({result.identifier!r}): "
                    f"score {result.score} outside 0-100 range"
                )
            if result.score > 0:
                warnings.append(
                    f"result[{i}] ({result.identifier!r}): "
                    "score is relevance only, not trust/safety evidence"
                )

    for i, referral in enumerate(response.referrals):
        if not referral.identifier:
            errors.append(f"referral[{i}]: identifier must not be empty")
        if not referral.url:
            errors.append(f"referral[{i}]: url must not be empty")

    if errors:
        return ARDConformanceResult(
            result="fail",
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    return ARDConformanceResult(
        result="pass",
        warnings=tuple(warnings),
    )


def validate_error_response(
    doc: JsonValue,
    *,
    expected_http_status: int | None = None,  # noqa: ARG001
) -> ARDConformanceResult:
    """Validate an ARD error response (Appendix B)."""
    obj = as_object(doc, where="ard error response")
    code = obj.get("code") or obj.get("error")
    if not isinstance(code, str):
        return ARDConformanceResult(
            result="fail",
            errors=("error response missing 'code' field",),
        )
    if code not in ARD_ERROR_CODES:
        return ARDConformanceResult(
            result="fail",
            errors=(f"unknown ARD error code: {code!r}",),
        )
    return ARDConformanceResult(result="pass")


def validate_response(response: SearchResponse) -> ARDConformanceResult:
    """Validate an already-decoded :class:`SearchResponse`."""
    errors: list[str] = []
    for i, result in enumerate(response.results):
        if not result.identifier:
            errors.append(f"result[{i}]: identifier empty")
        if not result.type:
            errors.append(f"result[{i}]: type empty")
    if errors:
        return ARDConformanceResult(result="fail", errors=tuple(errors))
    return ARDConformanceResult(result="pass")


__all__ = [
    "ARDConformanceResult",
    "validate_error_response",
    "validate_response",
    "validate_search_response",
]
