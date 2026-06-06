# SPDX-License-Identifier: MIT
"""Reference-routing DSPy signature.

Decides whether the agent needs to load an on-demand reference
file (one of the 8 canonical files under ``references/``) or stay
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

ReferenceName = Literal[
    "none",
    "creator-course-management",
    "account-and-identity",
    "notifications-and-reports",
    "credits-and-payments",
    "bounties",
    "course-review-queue",
    "admin-operations",
    "troubleshooting",
    "referrals",
]


# The Literal above MUST stay in lock-step with REFERENCE_NAMES;
# the test suite asserts the parity.
assert set(REFERENCE_NAMES) == set(get_args(ReferenceName))


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
