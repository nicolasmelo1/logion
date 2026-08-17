# SPDX-License-Identifier: MIT
"""Reference-routing DSPy signature.

Decides whether the agent needs to load an on-demand reference
file (one per file under ``references/``) or stay
on the primary SKILL.md path.  This is *adjacent* to the
decision-policy signature, not part of it — two independent
optimisation targets sharing the renderer machinery.
"""

from __future__ import annotations

from typing import Literal, get_args

import dspy

from evals.optimizers.dspy.reference_routing_inventory import (
    REFERENCE_NAMES,
)

# Spelled out rather than built from REFERENCE_NAMES. ``Literal[tuple]``
# is valid at runtime but mypy rejects it, and dspy needs a real static
# type here. So this list is a *mirror* of the directory, not a second
# source of truth: REFERENCE_NAMES is derived from ``references/`` and
# the assert below fails immediately, with the exact edit to make, if
# the two ever disagree.
ReferenceName = Literal[
    "none",
    "account-and-identity",
    "admin-operations",
    "bounties",
    "course-review-queue",
    "creator-course-management",
    "credits-and-payments",
    "notifications-and-reports",
    "referrals",
    "troubleshooting",
    "use-observation-and-feedback",
]

_declared = set(get_args(ReferenceName))
_shipped = set(REFERENCE_NAMES)
if _declared != _shipped:  # pragma: no cover - fails at import time
    raise AssertionError(
        "ReferenceName has drifted from references/. "
        f"Add to the Literal: {sorted(_shipped - _declared)}. "
        f"Remove from the Literal: {sorted(_declared - _shipped)}."
    )


class ReferenceRoutingSignature(dspy.Signature):
    """Pick which on-demand reference file to load (or `none` to
    stay on the primary path) by applying SKILL.md's `## Reference
    index` section.  Emit only `ReferenceName` enum values; never
    invent a name.
    """

    user_prompt: str = dspy.InputField(desc="The raw user prompt.")
    installed_capabilities: str = dspy.InputField(
        desc="Comma-separated list of installed capability IDs."
    )
    current_recall_band: str = dspy.InputField(
        desc="One of HIGH, MEDIUM, LOW, NONE — recall guardrail."
    )

    reference: ReferenceName = dspy.OutputField(
        desc="The reference to load, or 'none'."
    )
    reason: str = dspy.OutputField(
        desc="One-sentence justification; empty when reference='none'."
    )


class ReferenceRoutingModule(dspy.Module):
    """Wraps the signature into a DSPy module for optimisation."""

    def __init__(self) -> None:
        super().__init__()
        self.predictor = dspy.Predict(ReferenceRoutingSignature)

    def forward(self, **kwargs: object) -> dspy.Prediction:
        return self.predictor(**kwargs)
