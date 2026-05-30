"""Phase 6.11: reference-routing DSPy signature.

Decides whether the agent needs to load an on-demand reference
file (one of the 8 canonical files under ``references/``) or stay
on the primary SKILL.md path.  This is *adjacent* to the
decision-policy signature, not part of it — two independent
optimisation targets sharing the phase-6.10 renderer machinery.
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
    "payments-and-checkout",
    "bounties",
    "course-review-queue",
    "admin-operations",
    "troubleshooting",
]


# The Literal above MUST stay in lock-step with REFERENCE_NAMES;
# the test suite asserts the parity.
assert set(REFERENCE_NAMES) == set(get_args(ReferenceName))


class ReferenceRoutingSignature(dspy.Signature):
    """Pick which on-demand reference file the agent should load
    to fulfil the user's request, or ``none`` to stay on the
    primary path.

    Constraints:
    - Only emit values from the ReferenceName enum.
    - Prefer ``none`` when uncertain; loading a reference costs
      context and the primary SKILL.md path already covers
      recall, listings, courses, skills install, and paid
      checkout.
    - If ``installed_capabilities`` already covers the user's
      task (e.g. ``email.summarize`` for an inbox-summary
      intent), prefer ``none`` over loading a reference.
    - ``current_recall_band`` mirrors phase 6.9: HIGH means a
      local skill already covers this — almost always return
      ``none``.
    - Reference names refer to files under ``references/``;
      never invent a new name.
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
