"""DSPy Signature for the bootstrap decision policy.

The signature defines the input/output contract that DSPy optimizers will
compile against. The decision policy takes a user prompt, installed
capability index, marketplace search results, and the current bootstrap
policy text — and produces a structured action decision.
"""

from __future__ import annotations

from typing import Literal

import dspy

ActionKind = Literal[
    "answer_directly",
    "search_marketplace",
    "inspect_course",
    "ask_before_install",
    "ask_before_checkout",
    "load_existing_skill",
]


class DecisionPolicySignature(dspy.Signature):
    """Decide which action the Logion bootstrap skill should take.

    Given the user prompt, the set of installed capabilities, available
    marketplace search results, and the current policy instructions,
    produce a structured decision with action, optional search query,
    selected courses, confirmation flag, and a short reason.
    """

    user_prompt: str = dspy.InputField(
        desc="The raw user prompt that triggered the skill."
    )
    installed_capabilities: str = dspy.InputField(
        desc="Comma-separated list of installed capability IDs."
    )
    marketplace_results: str = dspy.InputField(
        desc="Summary of marketplace search results or fake catalog "
        "candidates available for this query."
    )
    current_policy_text: str = dspy.InputField(
        desc="The current bootstrap policy instructions from SKILL.md."
    )

    action: ActionKind = dspy.OutputField(
        desc="The action the skill should take."
    )
    query: str = dspy.OutputField(
        desc="Optional search query for marketplace or recall lookup. "
        "Empty string if not applicable."
    )
    selected_course_ids: str = dspy.OutputField(
        desc="Comma-separated course IDs relevant to the action. "
        "Empty string if not applicable."
    )
    requires_user_confirmation: bool = dspy.OutputField(
        desc="True if the action requires explicit user confirmation "
        "before proceeding (e.g. install, paid checkout, permission "
        "expansion)."
    )
    reason: str = dspy.OutputField(
        desc="Short explanation of why this action was chosen."
    )


class DecisionPolicyModule(dspy.Module):
    """Wraps the signature into a DSPy module for optimization."""

    def __init__(self) -> None:
        super().__init__()
        self.predictor = dspy.Predict(DecisionPolicySignature)

    def forward(self, **kwargs: object) -> dspy.Prediction:
        return self.predictor(**kwargs)
