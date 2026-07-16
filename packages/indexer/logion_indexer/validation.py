"""Fragment validation: gate inferred maps through logion_skillmap.

Every ``inferred_map`` pushed to the marketplace must parse and validate
under the canonical 15.3 skillmap schema.  Validation is delegated
entirely to :mod:`logion_skillmap` — the indexer never re-implements the
schema.  A fragment that fails (or is null) causes its item to be dropped
with reason ``inferred_map_invalid`` and marks the run partial.
"""

from __future__ import annotations

import json

from logion_skillmap import (
    check_unknown_keys_raw,
    parse_package_map,
    validate_package_map,
)

INFERRED_MAP_INVALID = "inferred_map_invalid"

# Warnings that do not, on their own, make a fragment unpushable.
_BENIGN_CODES = frozenset({"package_map_commands_not_executed"})


def fragment_errors(inferred_map: dict | None) -> list[str]:
    """Return skillmap warning codes that invalidate *inferred_map*.

    An empty list means the fragment is valid and pushable.  A null
    fragment is itself invalid (every pushed item must carry a map).
    """
    if not isinstance(inferred_map, dict):
        return [INFERRED_MAP_INVALID]

    try:
        pm = parse_package_map(json.dumps(inferred_map))
    except (TypeError, ValueError):
        return [INFERRED_MAP_INVALID]

    warnings = list(validate_package_map(pm))
    warnings.extend(check_unknown_keys_raw(inferred_map))
    return [w.code for w in warnings if w.code not in _BENIGN_CODES]


def is_valid_fragment(inferred_map: dict | None) -> bool:
    """True when *inferred_map* parses and validates cleanly."""
    return not fragment_errors(inferred_map)
