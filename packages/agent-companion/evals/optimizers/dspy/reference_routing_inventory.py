# SPDX-License-Identifier: MIT
"""Canonical inventory for the reference-routing signature.

Kept dspy-free so tests + scenario loaders can import it without the
optional optimisation dependency.

The inventory is derived from ``references/`` rather than hand-listed.
Adding one reference file used to mean editing seven places: this tuple,
the ``Literal`` in ``reference_routing.py``, ``REQUIRED_FILES`` in
``package_skill.py``, a count assertion in the tests, the SKILL.md
index, the bundle layout table, and the routing scenarios. Six of those
are answerable from ``ls references/``. Only the routing scenarios and
the SKILL.md index entry are genuine content, and the tests now check
those against the directory instead of against a second hand-written
list.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
REFERENCES_DIR = PACKAGE_ROOT / "references"

#: The routing class for "stay on the primary SKILL.md path".
NO_REFERENCE = "none"


def reference_files() -> tuple[Path, ...]:
    """Every on-demand reference file that ships in the bundle."""
    if not REFERENCES_DIR.is_dir():
        raise FileNotFoundError(
            f"references directory is missing: {REFERENCES_DIR}"
        )
    return tuple(sorted(REFERENCES_DIR.glob("*.md")))


def reference_slugs() -> tuple[str, ...]:
    """Reference file stems, which are also the routing class names."""
    return tuple(path.stem for path in reference_files())


#: Single source of truth for the routing output enum: ``none`` first,
#: then one class per reference file in directory order.
REFERENCE_NAMES: tuple[str, ...] = (NO_REFERENCE, *reference_slugs())
