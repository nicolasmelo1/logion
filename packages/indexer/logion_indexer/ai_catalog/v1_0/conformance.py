# SPDX-License-Identifier: MIT
"""AI Catalog v1.0 conformance validation.

Separate from ARD conformance: AI Catalog and ARD are independent
specifications with their own error codes, version negotiation, and
fixture suites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from logion_indexer._json import JsonValue

from . import (
    KNOWN_TYPES,
    Catalog,
    CatalogEntry,
    ConformanceLevel,
)
from .codec import (
    AICatalogDecodeError,
    AICatalogVersionUnsupported,
    decode_catalog,
)

ConformanceResultLevel = Literal["pass", "fail"]


@dataclass(frozen=True)
class ConformanceResult:
    """Result of a conformance check."""

    level: ConformanceLevel
    result: ConformanceResultLevel
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.result == "pass"


def validate_document(
    doc: JsonValue,
    *,
    allow_unknown_types: bool = True,
) -> ConformanceResult:
    """Validate a raw JSON document for AI Catalog conformance.

    This is the entry point for ``validate-ai-catalog`` CLI command.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Step 1: decode (structural validation + version negotiation).
    try:
        catalog = decode_catalog(doc)
    except AICatalogVersionUnsupported as e:
        return ConformanceResult(
            level="minimal",
            result="fail",
            errors=(str(e),),
        )
    except AICatalogDecodeError as e:
        return ConformanceResult(
            level="minimal",
            result="fail",
            errors=(str(e),),
        )

    # Step 2: per-entry validation.
    seen_identifiers: dict[str, int] = {}
    for i, entry in enumerate(catalog.entries):
        entry_errors = _validate_entry(
            entry,
            index=i,
            allow_unknown_types=allow_unknown_types,
        )
        errors.extend(entry_errors)

        # Uniqueness: identifier must be unique (or identifier+version
        # if version is present).
        uniqueness_key = entry.identifier
        if entry.version:
            uniqueness_key = f"{entry.identifier}@{entry.version}"
        if uniqueness_key in seen_identifiers:
            errors.append(
                f"entry {i}: duplicate {uniqueness_key!r} "
                "(identifier must be unique, or identifier+version "
                "if version is present)"
            )
        seen_identifiers[uniqueness_key] = i

    # Step 3: determine conformance level.
    level = catalog.conformance_level

    if errors:
        return ConformanceResult(
            level=level,
            result="fail",
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    # Warn about unknown types when allow_unknown_types is True.
    for entry in catalog.entries:
        if entry.type not in KNOWN_TYPES:
            warnings.append(
                f"entry {entry.identifier!r}: unknown type "
                f"{entry.type!r} (preserved per must-ignore rules)"
            )

    return ConformanceResult(
        level=level,
        result="pass",
        warnings=tuple(warnings),
    )


def _validate_entry(
    entry: CatalogEntry,
    *,
    index: int,
    allow_unknown_types: bool,
) -> list[str]:
    """Validate a single catalog entry."""
    errors: list[str] = []

    # Identifier: must be non-empty.
    if not entry.identifier:
        errors.append(f"entry {index}: identifier must not be empty")

    # Type: must be non-empty.
    if not entry.type:
        errors.append(f"entry {index}: type must not be empty")

    # url/data exclusivity is already enforced by the codec, but
    # double-check for direct model construction.
    if entry.url is None and entry.data is None:
        errors.append(
            f"entry {index} ({entry.identifier!r}): must have 'url' or 'data'"
        )
    if entry.url is not None and entry.data is not None:
        errors.append(
            f"entry {index} ({entry.identifier!r}): "
            "'url' and 'data' are mutually exclusive"
        )

    # Nested catalog type is valid; warn about unknown types only
    # when allow_unknown_types is False (strict mode).
    if not allow_unknown_types and entry.type not in KNOWN_TYPES:
        errors.append(
            f"entry {index} ({entry.identifier!r}): "
            f"unknown type {entry.type!r} in strict mode"
        )

    return errors


def validate_catalog(catalog: Catalog) -> ConformanceResult:
    """Validate an already-decoded :class:`Catalog`."""
    errors: list[str] = []
    seen: set[str] = set()
    for i, entry in enumerate(catalog.entries):
        errors.extend(
            _validate_entry(entry, index=i, allow_unknown_types=True)
        )
        key = entry.identifier
        if entry.version:
            key = f"{entry.identifier}@{entry.version}"
        if key in seen:
            errors.append(f"entry {i}: duplicate {key!r}")
        seen.add(key)

    level = catalog.conformance_level
    if errors:
        return ConformanceResult(
            level=level, result="fail", errors=tuple(errors)
        )
    return ConformanceResult(level=level, result="pass")


__all__ = [
    "ConformanceResult",
    "ConformanceResultLevel",
    "validate_catalog",
    "validate_document",
]
